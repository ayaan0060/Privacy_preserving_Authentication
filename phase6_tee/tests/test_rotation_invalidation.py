# phase6_tee/tests/test_rotation_invalidation.py
"""
Key Rotation Invalidation Tests.
"""
import pytest
import asyncio
import sys, os
from unittest.mock import Mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
phase4_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "phase4_he"))
if phase4_path not in sys.path:
    sys.path.insert(0, phase4_path)

from tee.simulation import SoftwareSecureContext
from tee.interface import KeyRevokedError
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


class TestRotationInvalidation:
    
    @pytest.mark.asyncio
    async def test_rotated_key_rejected(self, secure_context_with_he):
        """After rotation, old key version rejected by secure context."""
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
        nonce = b"rotation_test_nonce_32_bytes_1234"
        
        result = await ctx.verify_and_sign(
            encrypted_similarity=enc_score,
            he_secret_key=he_secret,
            nonce=nonce,
            key_version=1,
            threshold=0.3,
        )
        assert result.verified is True
        assert result.key_version == 1
        
        ctx.revoke_key_version(1)
        ctx.set_active_key_version(2)
        
        nonce2 = b"rotation_test_nonce_32_bytes_5678"
        with pytest.raises(KeyRevokedError) as exc_info:
            await ctx.verify_and_sign(
                encrypted_similarity=enc_score,
                he_secret_key=he_secret,
                nonce=nonce2,
                key_version=1,
                threshold=0.3,
            )
        
        assert "revoked" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_new_key_version_accepted(self, secure_context_with_he):
        """After rotation, new key version accepted."""
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
        
        ctx.revoke_key_version(1)
        ctx.set_active_key_version(2)
        
        nonce = b"new_version_nonce_32_bytes_long_!!"
        result = await ctx.verify_and_sign(
            encrypted_similarity=enc_score,
            he_secret_key=he_secret,
            nonce=nonce,
            key_version=2,
            threshold=0.3,
        )
        
        assert result.verified is True
        assert result.key_version == 2
    
    @pytest.mark.asyncio
    async def test_version_mismatch_rejected(self, secure_context_with_he):
        """Version not matching active version rejected."""
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
        
        nonce = b"mismatch_version_32_bytes_long____"
        with pytest.raises(KeyRevokedError):
            await ctx.verify_and_sign(
                encrypted_similarity=enc_score,
                he_secret_key=he_secret,
                nonce=nonce,
                key_version=999,
                threshold=0.3,
            )
