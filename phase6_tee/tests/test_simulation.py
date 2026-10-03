# phase6_tee/tests/test_simulation.py
import pytest
import asyncio
import numpy as np
from pathlib import Path
import tempfile
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
phase4_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "phase4_he"))
if phase4_path not in sys.path:
    sys.path.insert(0, phase4_path)

from tee.simulation import SoftwareSecureContext, verify_and_sign_core, create_signed_payload
from tee.device_keys import DeviceKeyManager
from tee.interface import NonceReplayError, NonceExpiredError, KeyRevokedError, ThresholdNotMetError
from he.crypto import HEClient, generate_he_keys
from he.params import DEFAULT_PARAMS


@pytest.fixture
def temp_dirs():
    with tempfile.TemporaryDirectory() as device_dir, \
         tempfile.TemporaryDirectory() as he_dir:
        yield Path(device_dir), Path(he_dir)


@pytest.fixture
def he_keys(temp_dirs):
    _, he_dir = temp_dirs
    generate_he_keys(he_dir, DEFAULT_PARAMS)
    return he_dir


@pytest.fixture
def secure_context(temp_dirs, he_keys):
    device_dir, _ = temp_dirs
    ctx = SoftwareSecureContext(
        device_key_dir=device_dir,
        he_key_dir=he_keys,
        use_mlock=False,
        zeroize_on_release=True,
    )
    yield ctx
    ctx.close()


@pytest.fixture
def device_keys(temp_dirs):
    device_dir, _ = temp_dirs
    return DeviceKeyManager(device_dir)


class TestSoftwareSecureContext:
    
    @pytest.mark.asyncio
    async def test_verify_and_sign_success(self, secure_context, he_keys):
        """Valid score above threshold → signature returned."""
        client = HEClient(he_keys, DEFAULT_PARAMS)
        t1 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        t2 = t1 * 0.9 + np.random.randn(256).astype(np.float32) * 0.1
        t2 = t2 / np.linalg.norm(t2)
        
        ct1 = client.encrypt_template(t1)
        ct2 = client.encrypt_template(t2)
        
        from he.compute import HESimilarityServer
        server = HESimilarityServer(he_keys, DEFAULT_PARAMS)
        enc_score = server.compute_similarity(ct1, ct2)
        
        nonce = b"test_nonce_32_bytes_long_12345678"
        result = await secure_context.verify_and_sign(
            encrypted_similarity=enc_score,
            he_secret_key=he_keys.joinpath("client_secret.key").read_bytes(),
            nonce=nonce,
            key_version=1,
            threshold=0.3,
        )
        
        assert result.verified is True
        assert result.signature is not None
        assert result.signed_payload is not None
        assert result.similarity_score >= 0.3
    
    @pytest.mark.asyncio
    async def test_verify_and_sign_threshold_fail(self, secure_context, he_keys):
        """Score below threshold → ThresholdNotMetError."""
        client = HEClient(he_keys, DEFAULT_PARAMS)
        t1 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        t2 = np.random.randn(256).astype(np.float32)
        t2 = t2 / np.linalg.norm(t2)
        
        ct1 = client.encrypt_template(t1)
        ct2 = client.encrypt_template(t2)
        
        from he.compute import HESimilarityServer
        server = HESimilarityServer(he_keys, DEFAULT_PARAMS)
        enc_score = server.compute_similarity(ct1, ct2)
        
        nonce = b"test_nonce_32_bytes_low_score!!"
        
        with pytest.raises(ThresholdNotMetError):
            await secure_context.verify_and_sign(
                encrypted_similarity=enc_score,
                he_secret_key=he_keys.joinpath("client_secret.key").read_bytes(),
                nonce=nonce,
                key_version=1,
                threshold=0.5,
            )
    
    @pytest.mark.asyncio
    async def test_nonce_replay_prevention(self, secure_context, he_keys):
        """Same nonce used twice → NonceReplayError."""
        client = HEClient(he_keys, DEFAULT_PARAMS)
        t1 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        
        ct1 = client.encrypt_template(t1)
        ct2 = client.encrypt_template(t1)
        
        from he.compute import HESimilarityServer
        server = HESimilarityServer(he_keys, DEFAULT_PARAMS)
        enc_score = server.compute_similarity(ct1, ct2)
        
        nonce = b"replay_test_nonce_32_bytes_123456"
        
        await secure_context.verify_and_sign(
            encrypted_similarity=enc_score,
            he_secret_key=he_keys.joinpath("client_secret.key").read_bytes(),
            nonce=nonce,
            key_version=1,
            threshold=0.3,
        )
        
        with pytest.raises(NonceReplayError):
            await secure_context.verify_and_sign(
                encrypted_similarity=enc_score,
                he_secret_key=he_keys.joinpath("client_secret.key").read_bytes(),
                nonce=nonce,
                key_version=1,
                threshold=0.3,
            )
    
    @pytest.mark.asyncio
    async def test_key_version_revoked(self, secure_context, he_keys):
        """Revoked key version → KeyRevokedError."""
        secure_context.revoke_key_version(1)
        
        client = HEClient(he_keys, DEFAULT_PARAMS)
        t1 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        
        ct1 = client.encrypt_template(t1)
        ct2 = client.encrypt_template(t1)
        
        from he.compute import HESimilarityServer
        server = HESimilarityServer(he_keys, DEFAULT_PARAMS)
        enc_score = server.compute_similarity(ct1, ct2)
        
        nonce = b"revoked_version_test_32_bytes_!!"
        
        with pytest.raises(KeyRevokedError):
            await secure_context.verify_and_sign(
                encrypted_similarity=enc_score,
                he_secret_key=he_keys.joinpath("client_secret.key").read_bytes(),
                nonce=nonce,
                key_version=1,
                threshold=0.3,
            )
    
    @pytest.mark.asyncio
    async def test_key_version_mismatch(self, secure_context, he_keys):
        """Wrong key version → KeyRevokedError."""
        client = HEClient(he_keys, DEFAULT_PARAMS)
        t1 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        
        ct1 = client.encrypt_template(t1)
        ct2 = client.encrypt_template(t1)
        
        from he.compute import HESimilarityServer
        server = HESimilarityServer(he_keys, DEFAULT_PARAMS)
        enc_score = server.compute_similarity(ct1, ct2)
        
        nonce = b"version_mismatch_test_32_bytes_!!"
        
        with pytest.raises(KeyRevokedError):
            await secure_context.verify_and_sign(
                encrypted_similarity=enc_score,
                he_secret_key=he_keys.joinpath("client_secret.key").read_bytes(),
                nonce=nonce,
                key_version=999,
                threshold=0.3,
            )


class TestCoreLogic:
    """Test pure core logic (verify_and_sign_core) without simulation overhead."""
    
    def test_create_signed_payload_format(self):
        payload = create_signed_payload(
            nonce=b"x" * 32,
            similarity_score=0.85,
            key_version=3,
            device_id="test_device",
            timestamp=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            verified=True,
        )
        assert len(payload) >= 32 + 8 + 4 + 2 + len("test_device") + 20 + 1
        assert payload[:32] == b"x" * 32
    
    def test_verify_signature_valid(self, device_keys):
        payload = b"test_payload"
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        signature = device_keys.get_signing_key().sign(
            payload,
            ec.ECDSA(hashes.SHA256())
        )
        from tee.simulation import verify_signature
        assert verify_signature(device_keys.get_public_key(), payload, signature) is True
    
    def test_verify_signature_invalid(self, device_keys):
        payload = b"test_payload"
        wrong_signature = b"x" * 64
        from tee.simulation import verify_signature
        assert verify_signature(device_keys.get_public_key(), payload, wrong_signature) is False


class TestDeviceKeys:
    
    def test_key_generation(self, device_keys):
        assert device_keys.get_signing_key() is not None
        assert device_keys.get_public_key() is not None
        assert device_keys.get_device_id().startswith("dev_")
    
    def test_key_persistence(self, temp_dirs):
        device_dir, _ = temp_dirs
        
        mgr1 = DeviceKeyManager(device_dir)
        device_id1 = mgr1.get_device_id()
        pub1 = mgr1.get_public_key_pem()
        mgr1.close()
        
        mgr2 = DeviceKeyManager(device_dir)
        device_id2 = mgr2.get_device_id()
        pub2 = mgr2.get_public_key_pem()
        
        assert device_id1 == device_id2
        assert pub1 == pub2
    
    def test_key_rotation(self, device_keys):
        old_id = device_keys.get_device_id()
        old_pub = device_keys.get_public_key_pem()
        
        new_id = device_keys.rotate_key()
        
        assert new_id != old_id
        assert device_keys.get_public_key_pem() != old_pub
        assert device_keys.get_device_id() == new_id
