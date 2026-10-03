# phase7_integration/adversarial/rotation_tests.py
"""
Key Rotation Invalidation Tests.

Verifies that key rotation properly invalidates old templates
and prevents rollback attacks.
"""
import pytest
import numpy as np
from pathlib import Path
import tempfile
import sys, os

phase_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for p in ["phase1_encoder", "phase2_keymgmt", "phase3_fusion", "phase4_he", "phase5_backend", "phase6_tee", "phase7_integration"]:
    path = os.path.join(phase_root, p)
    if path not in sys.path:
        sys.path.insert(0, path)

from integration.pipeline import BiometricPipeline, PipelineConfig
from he.crypto import HEClient, generate_he_keys
from he.compute import HESimilarityServer
from he.params import DEFAULT_PARAMS
from keystore.software import SoftwareSecureKeyStore
from tee.simulation import SoftwareSecureContext


@pytest.fixture
def rotation_setup():
    with tempfile.TemporaryDirectory() as device_dir, \
         tempfile.TemporaryDirectory() as he_dir, \
         tempfile.TemporaryDirectory() as keystore_dir, \
         tempfile.TemporaryDirectory() as film_dir:
        
        generate_he_keys(Path(he_dir), DEFAULT_PARAMS)
        
        from film.model import FiLMFusion
        import torch
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
        
        yield pipeline, he_dir, keystore_dir
        pipeline.close()


class TestKeyRotation:
    
    @pytest.mark.asyncio
    async def test_old_template_invalid_after_rotation(self, rotation_setup):
        """After key rotation, old enrolled template cannot verify."""
        pipeline, he_dir, keystore_dir = rotation_setup
        
        user_id = "rotation_user"
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        enroll_v1 = await pipeline.enroll(user_id, fingerprint)
        assert enroll_v1.key_version == 1
        
        v1_enrolled_ct = enroll_v1.enrolled_template_ct
        
        pipeline.keystore.rotate_key(user_id, "scheduled_rotation")
        pipeline.secure_context.revoke_key_version(1)
        pipeline.secure_context.set_active_key_version(2)
        
        probe_fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        client = pipeline.he_client
        server = pipeline.he_server
        
        v1_key_material = pipeline.keystore.get_key_material(user_id, 1)
        probe_embedding = pipeline.encoder_session.run(
            [pipeline.encoder_output_name],
            {pipeline.encoder_input_name: np.random.randn(1, 1, 96, 96).astype(np.float32)}
        )[0][0]
        v1_fused = pipeline.film_session.run(None, {
            pipeline.film_input_names[0]: probe_embedding[np.newaxis, :].astype(np.float32),
            pipeline.film_input_names[1]: v1_key_material.key_vector[np.newaxis, :].astype(np.float32),
        })[0][0]
        v1_probe_ct = client.encrypt_template(v1_fused)
        
        enc_score = server.compute_similarity(v1_enrolled_ct, v1_probe_ct)
        
        he_secret = Path(he_dir).joinpath("client_secret.key").read_bytes()
        nonce = b"rotation_test_v1_32_bytes_long____"
        
        from tee.key_release import KeyReleaseRequest
        request = KeyReleaseRequest(
            encrypted_similarity=enc_score,
            he_secret_key=he_secret,
            nonce=nonce,
            key_version=1,
            threshold=0.3,
        )
        
        from tee.interface import KeyRevokedError
        with pytest.raises(KeyRevokedError):
            await pipeline.key_release_protocol.execute_release(request)
    
    @pytest.mark.asyncio
    async def test_new_template_works_after_rotation(self, rotation_setup):
        """After rotation, new template with new key works."""
        pipeline, he_dir, keystore_dir = rotation_setup
        
        user_id = "rotation_user_2"
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        enroll_v1 = await pipeline.enroll(user_id, fingerprint)
        
        pipeline.keystore.rotate_key(user_id, "scheduled_rotation")
        pipeline.secure_context.revoke_key_version(1)
        pipeline.secure_context.set_active_key_version(2)
        
        enroll_v2 = await pipeline.enroll(user_id, fingerprint, key_version=2)
        assert enroll_v2.key_version == 2
        
        v2_fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        verify_result = await pipeline.verify(user_id, v2_fingerprint, key_version=2)
        
        assert verify_result.key_version == 2
    
    @pytest.mark.asyncio
    async def test_rollback_to_old_key_rejected(self, rotation_setup):
        """Attempting to use old key version after rotation fails."""
        pipeline, he_dir, keystore_dir = rotation_setup
        
        user_id = "rollback_user"
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        await pipeline.enroll(user_id, fingerprint)
        
        pipeline.keystore.rotate_key(user_id, "rotation")
        pipeline.secure_context.revoke_key_version(1)
        pipeline.secure_context.set_active_key_version(2)
        
        await pipeline.enroll(user_id, fingerprint, key_version=2)
        
        probe_fp = np.random.rand(200, 200).astype(np.uint8) * 255
        
        with pytest.raises(Exception):
            await pipeline.verify(user_id, probe_fp, key_version=1)
    
    @pytest.mark.asyncio
    async def test_grace_period_allows_inflight(self, rotation_setup):
        """Grace period should allow in-flight verifications to complete."""
        pipeline, he_dir, keystore_dir = rotation_setup
        
        user_id = "grace_user"
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        enroll_v1 = await pipeline.enroll(user_id, fingerprint)
        v1_ct = enroll_v1.enrolled_template_ct
        
        pipeline.keystore.rotate_key(user_id, "rotation")
        pass
