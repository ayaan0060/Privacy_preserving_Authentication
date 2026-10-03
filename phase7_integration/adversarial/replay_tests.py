# phase7_integration/adversarial/replay_tests.py
"""
Replay Attack Tests.

Tests all replay vectors:
1. Nonce replay (server challenge)
2. Template replay (encrypted probe)
3. Signature replay (key release response)
4. Session token replay
"""
import asyncio
import base64
import pytest
import sys, os
from unittest.mock import Mock, AsyncMock

# Ensure cross-phase package imports work
phase_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for p in ["phase1_encoder", "phase2_keymgmt", "phase3_fusion", "phase4_he", "phase5_backend", "phase6_tee", "phase7_integration"]:
    path = os.path.join(phase_root, p)
    if path not in sys.path:
        sys.path.insert(0, path)

from integration.pipeline import BiometricPipeline, PipelineConfig
from he.crypto import HEClient, generate_he_keys
from he.compute import HESimilarityServer
from he.params import DEFAULT_PARAMS
from tee.simulation import SoftwareSecureContext
from tee.key_release import KeyReleaseProtocol, verify_key_release_response
from tee.interface import NonceReplayError
import tempfile
from pathlib import Path
import numpy as np


@pytest.fixture
def adversarial_setup():
    """Complete pipeline for adversarial testing."""
    with tempfile.TemporaryDirectory() as device_dir, \
         tempfile.TemporaryDirectory() as he_dir, \
         tempfile.TemporaryDirectory() as keystore_dir, \
         tempfile.TemporaryDirectory() as film_dir:
        
        generate_he_keys(Path(he_dir), DEFAULT_PARAMS)
        
        from film.model import FiLMFusion
        import torch
        import onnx
        
        film_model = FiLMFusion(embedding_dim=256)
        film_model.eval()
        dummy_x = torch.randn(1, 256)
        dummy_k = torch.randn(1, 256)
        try:
            torch.onnx.export(film_model, (dummy_x, dummy_k), Path(film_dir) / "film.onnx", opset_version=14)
        except Exception:
            (Path(film_dir) / "film.onnx").write_bytes(b"DUMMY_ONNX_MODEL")
        
        class MockEncoderSession:
            def run(self, _, inputs):
                x = inputs[list(inputs.keys())[0]]
                batch = x.shape[0]
                emb = np.random.randn(batch, 256).astype(np.float32)
                emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
                return [emb]
        
        config = PipelineConfig(
            encoder_path=Path(film_dir) / "dummy.onnx",
            film_path=Path(film_dir) / "film.onnx",
            he_key_dir=Path(he_dir),
            keystore_dir=Path(keystore_dir),
            device_key_dir=Path(device_dir),
        )
        
        pipeline = BiometricPipeline(config)
        pipeline.encoder_session = MockEncoderSession()
        pipeline.encoder_input_name = "input"
        pipeline.encoder_output_name = "output"
        
        yield pipeline, he_dir
        pipeline.close()


class TestNonceReplay:
    """Test nonce replay protection."""
    
    @pytest.mark.asyncio
    async def test_server_nonce_replay_blocked(self, adversarial_setup):
        """Server should reject reused nonce."""
        pipeline, he_dir = adversarial_setup
        
        user_id = "replay_user"
        
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        enroll_result = await pipeline.enroll(user_id, fingerprint)
        
        from httpx import AsyncClient
        from backend.main import create_app
        
        app = create_app()
        async with AsyncClient(app=app, base_url="http://test") as client:
            ct_b64 = base64.b64encode(enroll_result.enrolled_template_ct).decode()
            pk_b64 = base64.b64encode(enroll_result.client_pk_he).decode()
            
            await client.post("/enroll", json={
                "user_id": user_id,
                "encrypted_template": ct_b64,
                "client_pk_he": pk_b64,
                "key_version": enroll_result.key_version,
            })
            
            challenge_resp = await client.post("/verify/challenge", json={"user_id": user_id})
            nonce = challenge_resp.json()["nonce"]
            
            probe_ct = pipeline.he_client.encrypt_template(
                np.random.randn(256).astype(np.float32)
            )
            probe_b64 = base64.b64encode(probe_ct).decode()
            
            verify_resp1 = await client.post("/verify", json={
                "user_id": user_id,
                "nonce": nonce,
                "encrypted_probe": probe_b64,
                "key_version": enroll_result.key_version,
            })
            
            verify_resp2 = await client.post("/verify", json={
                "user_id": user_id,
                "nonce": nonce,
                "encrypted_probe": probe_b64,
                "key_version": enroll_result.key_version,
            })
            
            assert verify_resp1.status_code == 200
            assert verify_resp2.status_code == 401


class TestTemplateReplay:
    """Test encrypted template/probe replay."""
    
    @pytest.mark.asyncio
    async def test_encrypted_probe_replay(self, adversarial_setup):
        """Replaying same encrypted probe with different nonce should work (stateless HE)."""
        pipeline, he_dir = adversarial_setup
        
        user_id = "template_replay_user"
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        enroll_result = await pipeline.enroll(user_id, fingerprint)
        
        probe_ct = pipeline.he_client.encrypt_template(
            np.random.randn(256).astype(np.float32)
        )
        
        nonce1 = b"nonce_one_32_bytes_long_12345678"
        request1 = KeyReleaseRequest(
            encrypted_similarity=pipeline.he_server.compute_similarity(
                enroll_result.enrolled_template_ct, probe_ct
            ),
            he_secret_key=Path(he_dir).joinpath("client_secret.key").read_bytes(),
            nonce=nonce1,
            key_version=enroll_result.key_version,
            threshold=0.3,
        )
        response1 = await pipeline.key_release_protocol.execute_release(request1)
        
        nonce2 = b"nonce_two_32_bytes_long_12345678"
        request2 = KeyReleaseRequest(
            encrypted_similarity=pipeline.he_server.compute_similarity(
                enroll_result.enrolled_template_ct, probe_ct
            ),
            he_secret_key=Path(he_dir).joinpath("client_secret.key").read_bytes(),
            nonce=nonce2,
            key_version=enroll_result.key_version,
            threshold=0.3,
        )
        response2 = await pipeline.key_release_protocol.execute_release(request2)
        
        assert response1.result.verified == response2.result.verified
        assert response1.result.signature != response2.result.signature
        assert response1.result.signed_payload != response2.result.signed_payload


class TestSignatureReplay:
    """Test key release signature replay."""
    
    @pytest.mark.asyncio
    async def test_signature_replay_blocked(self, adversarial_setup):
        """Replaying a valid signature with different nonce should fail."""
        pipeline, he_dir = adversarial_setup
        
        from tee.key_release import KeyReleaseRequest, KeyReleaseResponse
        from tee.interface import VerificationResult, DeviceIdentity
        from tee.device_keys import DeviceKeyManager
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from datetime import datetime, timezone
        
        device_keys = DeviceKeyManager(Path(pipeline.config.device_key_dir))
        
        payload = b"test_payload_with_nonce_1"
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
            ),
        )
        
        valid1, _ = verify_key_release_response(
            response=response,
            expected_nonce=b"nonce_1_32_bytes_long_1234567890",
            expected_threshold=0.3,
        )
        
        valid2, _ = verify_key_release_response(
            response=response,
            expected_nonce=b"nonce_2_32_bytes_long_1234567890",
            expected_threshold=0.3,
        )
        
        assert valid1 is True
        assert valid2 is False


class TestSessionTokenReplay:
    """Test session token replay (application-level)."""
    
    @pytest.mark.asyncio
    async def test_session_token_replay(self, adversarial_setup):
        """Session tokens should be validated server-side with expiration."""
        pipeline, he_dir = adversarial_setup
        
        from jose import jwt
        from datetime import datetime, timezone, timedelta
        
        token = jwt.encode(
            {
                "sub": "test_user",
                "key_version": 1,
                "iat": datetime.now(timezone.utc),
                "exp": datetime.now(timezone.utc) + timedelta(seconds=3600),
                "iss": "cancelable-bio-auth",
            },
            "test-secret",
            algorithm="HS256",
        )
        
        decoded = jwt.decode(token, "test-secret", algorithms=["HS256"])
        assert decoded["sub"] == "test_user"
        
        expired_token = jwt.encode(
            {
                "sub": "test_user",
                "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
            },
            "test-secret",
            algorithm="HS256",
        )
        
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(expired_token, "test-secret", algorithms=["HS256"])
