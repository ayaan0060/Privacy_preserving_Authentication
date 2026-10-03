# phase6_tee/tests/test_key_release.py
"""
Key Release Protocol Tests.
"""
import pytest
import base64
import sys, os
from unittest.mock import Mock, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tee.key_release import (
    KeyReleaseProtocol, 
    KeyReleaseRequest, 
    KeyReleaseResponse,
    verify_key_release_response,
    parse_signed_payload,
    create_signed_payload,
)
from tee.interface import VerificationResult, DeviceIdentity
from tee.device_keys import DeviceKeyManager
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
import tempfile
from pathlib import Path
from datetime import datetime, timezone


@pytest.fixture
def device_keys():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield DeviceKeyManager(Path(tmpdir))


@pytest.fixture
def mock_secure_context(device_keys):
    ctx = Mock()
    ctx.verify_and_sign = AsyncMock()
    ctx.get_device_identity.return_value = DeviceIdentity(
        device_id=device_keys.get_device_id(),
        public_key=device_keys.get_public_key(),
        tee_type="simulation",
    )
    return ctx


@pytest.fixture
def protocol(mock_secure_context):
    return KeyReleaseProtocol(mock_secure_context)


class TestKeyReleaseProtocol:
    
    @pytest.mark.asyncio
    async def test_execute_release_success(self, protocol, device_keys):
        """Successful key release returns signed result."""
        payload = create_signed_payload(
            nonce=b"n" * 32,
            similarity_score=0.85,
            key_version=1,
            device_id=device_keys.get_device_id(),
            timestamp=datetime.now(timezone.utc),
            verified=True,
        )
        signature = device_keys.get_signing_key().sign(payload, ec.ECDSA(hashes.SHA256()))
        
        mock_result = VerificationResult(
            verified=True,
            similarity_score=0.85,
            key_version=1,
            timestamp=datetime.now(timezone.utc),
            signature=signature,
            signed_payload=payload,
        )
        protocol.secure_context.verify_and_sign.return_value = mock_result
        
        request = KeyReleaseRequest(
            encrypted_similarity=b"dummy",
            he_secret_key=b"dummy",
            nonce=b"n" * 32,
            key_version=1,
            threshold=0.3,
        )
        
        response = await protocol.execute_release(request)
        
        assert isinstance(response, KeyReleaseResponse)
        assert response.result.verified is True
        assert response.result.signature == signature
        assert response.device_identity.device_id == device_keys.get_device_id()
    
    @pytest.mark.asyncio
    async def test_execute_release_forwards_params(self, protocol):
        """Protocol forwards all params to secure context."""
        await protocol.execute_release(KeyReleaseRequest(
            encrypted_similarity=b"enc_score",
            he_secret_key=b"he_key",
            nonce=b"nonce123",
            key_version=5,
            threshold=0.4,
        ))
        
        protocol.secure_context.verify_and_sign.assert_called_once_with(
            encrypted_similarity=b"enc_score",
            he_secret_key=b"he_key",
            nonce=b"nonce123",
            key_version=5,
            threshold=0.4,
        )


class TestServerVerification:
    
    def test_verify_valid_response(self, device_keys):
        """Server accepts valid key release response."""
        payload = create_signed_payload(
            nonce=b"expected_nonce_32_bytes_long_!!",
            similarity_score=0.85,
            key_version=1,
            device_id=device_keys.get_device_id(),
            timestamp=datetime.now(timezone.utc),
            verified=True,
        )
        signature = device_keys.get_signing_key().sign(payload, ec.ECDSA(hashes.SHA256()))
        
        result = VerificationResult(
            verified=True,
            similarity_score=0.85,
            key_version=1,
            timestamp=datetime.now(timezone.utc),
            signature=signature,
            signed_payload=payload,
        )
        
        response = KeyReleaseResponse(
            result=result,
            device_identity=DeviceIdentity(
                device_id=device_keys.get_device_id(),
                public_key=device_keys.get_public_key(),
                tee_type="simulation",
            ),
        )
        
        valid, reason = verify_key_release_response(
            response=response,
            expected_nonce=b"expected_nonce_32_bytes_long_!!",
            expected_threshold=0.3,
        )
        
        assert valid is True
        assert reason == "Valid key release"
    
    def test_verify_invalid_signature(self, device_keys):
        """Server rejects invalid signature."""
        payload = create_signed_payload(
            nonce=b"expected_nonce_32_bytes_long_!!",
            similarity_score=0.85,
            key_version=1,
            device_id=device_keys.get_device_id(),
            timestamp=datetime.now(timezone.utc),
            verified=True,
        )
        signature = b"x" * 64
        
        result = VerificationResult(
            verified=True,
            similarity_score=0.85,
            key_version=1,
            timestamp=datetime.now(timezone.utc),
            signature=signature,
            signed_payload=payload,
        )
        
        response = KeyReleaseResponse(
            result=result,
            device_identity=DeviceIdentity(
                device_id=device_keys.get_device_id(),
                public_key=device_keys.get_public_key(),
                tee_type="simulation",
            ),
        )
        
        valid, reason = verify_key_release_response(
            response=response,
            expected_nonce=b"expected_nonce_32_bytes_long_!!",
            expected_threshold=0.3,
        )
        
        assert valid is False
        assert "signature" in reason.lower()
    
    def test_verify_nonce_mismatch(self, device_keys):
        """Server rejects nonce mismatch."""
        payload = create_signed_payload(
            nonce=b"wrong_nonce_32_bytes_long_____",
            similarity_score=0.85,
            key_version=1,
            device_id=device_keys.get_device_id(),
            timestamp=datetime.now(timezone.utc),
            verified=True,
        )
        signature = device_keys.get_signing_key().sign(payload, ec.ECDSA(hashes.SHA256()))
        
        result = VerificationResult(
            verified=True,
            similarity_score=0.85,
            key_version=1,
            timestamp=datetime.now(timezone.utc),
            signature=signature,
            signed_payload=payload,
        )
        
        response = KeyReleaseResponse(
            result=result,
            device_identity=DeviceIdentity(
                device_id=device_keys.get_device_id(),
                public_key=device_keys.get_public_key(),
                tee_type="simulation",
            ),
        )
        
        valid, reason = verify_key_release_response(
            response=response,
            expected_nonce=b"expected_nonce_32_bytes_long_!!",
            expected_threshold=0.3,
        )
        
        assert valid is False
        assert "nonce mismatch" in reason.lower()
    
    def test_verify_score_below_threshold_in_payload(self, device_keys):
        """Server rejects if payload score < threshold."""
        payload = create_signed_payload(
            nonce=b"expected_nonce_32_bytes_long_!!",
            similarity_score=0.15,
            key_version=1,
            device_id=device_keys.get_device_id(),
            timestamp=datetime.now(timezone.utc),
            verified=True,
        )
        signature = device_keys.get_signing_key().sign(payload, ec.ECDSA(hashes.SHA256()))
        
        result = VerificationResult(
            verified=True,
            similarity_score=0.15,
            key_version=1,
            timestamp=datetime.now(timezone.utc),
            signature=signature,
            signed_payload=payload,
        )
        
        response = KeyReleaseResponse(
            result=result,
            device_identity=DeviceIdentity(
                device_id=device_keys.get_device_id(),
                public_key=device_keys.get_public_key(),
                tee_type="simulation",
            ),
        )
        
        valid, reason = verify_key_release_response(
            response=response,
            expected_nonce=b"expected_nonce_32_bytes_long_!!",
            expected_threshold=0.3,
        )
        
        assert valid is False
        assert "threshold" in reason.lower()


class TestPayloadParsing:
    
    def test_parse_signed_payload(self, device_keys):
        """Payload parsing extracts all fields correctly."""
        device_id = device_keys.get_device_id()
        timestamp = datetime.now(timezone.utc)
        
        payload = create_signed_payload(
            nonce=b"n" * 32,
            similarity_score=0.85,
            key_version=3,
            device_id=device_id,
            timestamp=timestamp,
            verified=True,
        )
        
        parsed = parse_signed_payload(payload)
        
        assert parsed['nonce'] == b"n" * 32
        assert abs(parsed['similarity_score'] - 0.85) < 1e-10
        assert parsed['key_version'] == 3
        assert parsed['device_id'] == device_id
        assert abs((parsed['timestamp'] - timestamp).total_seconds()) < 1
        assert parsed['verified'] is True
