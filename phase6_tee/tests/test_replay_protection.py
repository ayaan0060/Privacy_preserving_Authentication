# phase6_tee/tests/test_replay_protection.py
"""
Replay Attack Protection Tests.
"""
import pytest
import asyncio
import sys, os
from unittest.mock import Mock, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
phase4_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "phase4_he"))
if phase4_path not in sys.path:
    sys.path.insert(0, phase4_path)

from tee.simulation import SoftwareSecureContext
from tee.interface import NonceReplayError
from tee.device_keys import DeviceKeyManager
from he.crypto import HEClient, generate_he_keys
from he.compute import HESimilarityServer
from he.params import DEFAULT_PARAMS
import tempfile
from pathlib import Path
import numpy as np


@pytest.fixture
def secure_context_with_he():
    with tempfile.TemporaryDirectory() as device_dir, \
         tempfile.TemporaryDirectory() as he_dir:
        generate_he_keys(Path(he_dir), DEFAULT_PARAMS)
        ctx = SoftwareSecureContext(
            device_key_dir=Path(device_dir),
            he_key_dir=Path(he_dir),
            use_mlock=False,
        )
        yield ctx, he_dir
        ctx.close()


class TestReplayProtection:
    
    @pytest.mark.asyncio
    async def test_same_nonce_twice_fails(self, secure_context_with_he):
        """Using same nonce twice raises NonceReplayError."""
        ctx, he_dir = secure_context_with_he
        
        client = HEClient(Path(he_dir), DEFAULT_PARAMS)
        server = HESimilarityServer(Path(he_dir), DEFAULT_PARAMS)
        
        t1 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        t2 = t1 * 0.9 + np.random.randn(256).astype(np.float32) * 0.1
        t2 = t2 / np.linalg.norm(t2)
        
        ct1 = client.encrypt_template(t1)
        ct2 = client.encrypt_template(t2)
        enc_score = server.compute_similarity(ct1, ct2)
        
        he_secret = Path(he_dir).joinpath("client_secret.key").read_bytes()
        nonce = b"replay_test_nonce_32_bytes_123456"
        
        result1 = await ctx.verify_and_sign(
            encrypted_similarity=enc_score,
            he_secret_key=he_secret,
            nonce=nonce,
            key_version=1,
            threshold=0.3,
        )
        assert result1.verified is True
        
        with pytest.raises(NonceReplayError):
            await ctx.verify_and_sign(
                encrypted_similarity=enc_score,
                he_secret_key=he_secret,
                nonce=nonce,
                key_version=1,
                threshold=0.3,
            )
    
    @pytest.mark.asyncio
    async def test_different_nonces_succeed(self, secure_context_with_he):
        """Different nonces work independently."""
        ctx, he_dir = secure_context_with_he
        
        client = HEClient(Path(he_dir), DEFAULT_PARAMS)
        server = HESimilarityServer(Path(he_dir), DEFAULT_PARAMS)
        
        t1 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        t2 = t1 * 0.9 + np.random.randn(256).astype(np.float32) * 0.1
        t2 = t2 / np.linalg.norm(t2)
        
        ct1 = client.encrypt_template(t1)
        ct2 = client.encrypt_template(t2)
        enc_score = server.compute_similarity(ct1, ct2)
        
        he_secret = Path(he_dir).joinpath("client_secret.key").read_bytes()
        
        nonce1 = b"nonce_one_32_bytes_long_12345678"
        result1 = await ctx.verify_and_sign(
            encrypted_similarity=enc_score,
            he_secret_key=he_secret,
            nonce=nonce1,
            key_version=1,
            threshold=0.3,
        )
        assert result1.verified is True
        
        nonce2 = b"nonce_two_32_bytes_long_12345678"
        result2 = await ctx.verify_and_sign(
            encrypted_similarity=enc_score,
            he_secret_key=he_secret,
            nonce=nonce2,
            key_version=1,
            threshold=0.3,
        )
        assert result2.verified is True
        
        assert result1.signature != result2.signature
        assert result1.signed_payload != result2.signed_payload
    
    @pytest.mark.asyncio
    async def test_nonce_persistence_across_context(self, secure_context_with_he):
        """Nonce tracking persists for context lifetime."""
        ctx, he_dir = secure_context_with_he
        
        client = HEClient(Path(he_dir), DEFAULT_PARAMS)
        server = HESimilarityServer(Path(he_dir), DEFAULT_PARAMS)
        
        t1 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        t2 = t1.copy()
        
        ct1 = client.encrypt_template(t1)
        ct2 = client.encrypt_template(t2)
        enc_score = server.compute_similarity(ct1, ct2)
        
        he_secret = Path(he_dir).joinpath("client_secret.key").read_bytes()
        nonce = b"persist_test_nonce_32_bytes_1234"
        
        await ctx.verify_and_sign(
            encrypted_similarity=enc_score,
            he_secret_key=he_secret,
            nonce=nonce,
            key_version=1,
            threshold=0.3,
        )
        
        assert nonce in ctx._used_nonces
        assert nonce in ctx._nonce_timestamps
    
    @pytest.mark.asyncio
    async def test_concurrent_nonce_handling(self, secure_context_with_he):
        """Concurrent verifications with different nonces."""
        ctx, he_dir = secure_context_with_he
        
        client = HEClient(Path(he_dir), DEFAULT_PARAMS)
        server = HESimilarityServer(Path(he_dir), DEFAULT_PARAMS)
        
        t1 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        t2 = t1.copy()
        
        ct1 = client.encrypt_template(t1)
        ct2 = client.encrypt_template(t2)
        enc_score = server.compute_similarity(ct1, ct2)
        
        he_secret = Path(he_dir).joinpath("client_secret.key").read_bytes()
        
        async def verify(nonce_suffix: int):
            nonce = f"concurrent_{nonce_suffix:02d}_32_bytes_long!!".encode()
            return await ctx.verify_and_sign(
                encrypted_similarity=enc_score,
                he_secret_key=he_secret,
                nonce=nonce,
                key_version=1,
                threshold=0.3,
            )
        
        tasks = [verify(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        for r in results:
            assert r.verified is True
        
        assert len(ctx._used_nonces) == 10
