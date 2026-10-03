# phase7_integration/tests/test_e2e_flow.py
"""
End-to-End Integration Tests.

Complete flow: Enroll → Verify → Rotate → Verify (old fails, new works)
"""
import pytest
import asyncio
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
from he.crypto import generate_he_keys
from he.params import DEFAULT_PARAMS
from film.model import FiLMFusion
import torch


@pytest.fixture
def e2e_pipeline():
    with tempfile.TemporaryDirectory() as device_dir, \
         tempfile.TemporaryDirectory() as he_dir, \
         tempfile.TemporaryDirectory() as keystore_dir, \
         tempfile.TemporaryDirectory() as film_dir:
        
        generate_he_keys(Path(he_dir), DEFAULT_PARAMS)
        
        from film.model import FiLMFusionExport
        film_model = FiLMFusionExport(embedding_dim=256)
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
                batch = x.shape[0] if hasattr(x, 'shape') else 1
                import hashlib
                seed = int(hashlib.sha256(x.tobytes()).hexdigest()[:8], 16)
                rng = np.random.default_rng(seed)
                emb = rng.standard_normal((batch, 256)).astype(np.float32)
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
        pipeline.film_session = film_model
        pipeline.encoder_session = MockEncoderSession()
        pipeline.encoder_input_name = "input"
        pipeline.encoder_output_name = "output"
        
        yield pipeline
        pipeline.close()


class TestE2EFlow:
    
    @pytest.mark.asyncio
    async def test_enroll_verify_success(self, e2e_pipeline):
        """Basic enroll → verify with same fingerprint succeeds."""
        user_id = "e2e_user"
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        enroll_result = await e2e_pipeline.enroll(user_id, fingerprint)
        assert enroll_result.key_version == 1
        
        verify_result = await e2e_pipeline.verify(user_id, fingerprint)
        
        assert verify_result.verified is True
        assert verify_result.similarity_score > 0.5  # same template, should be high
        assert verify_result.session_token is not None
        assert verify_result.key_release_valid is True
    
    @pytest.mark.asyncio
    async def test_verify_different_fingerprint_fails(self, e2e_pipeline):
        """Different fingerprint should fail verification."""
        user_id = "diff_fp_user"
        fingerprint1 = np.zeros((200, 200), dtype=np.uint8)
        fingerprint1[:100, :] = 255
        fingerprint2 = np.zeros((200, 200), dtype=np.uint8)
        fingerprint2[:, :100] = 255
        
        await e2e_pipeline.enroll(user_id, fingerprint1)
        result = await e2e_pipeline.verify(user_id, fingerprint2)
        
        assert result.verified is False
        assert result.session_token is None
    
    @pytest.mark.asyncio
    async def test_key_rotation_invalidates_old(self, e2e_pipeline):
        """After rotation, old key cannot verify."""
        user_id = "rotate_user"
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        enroll_v1 = await e2e_pipeline.enroll(user_id, fingerprint)
        assert enroll_v1.key_version == 1
        
        e2e_pipeline.keystore.rotate_key(user_id, "test_rotation")
        e2e_pipeline.secure_context.revoke_key_version(1)
        e2e_pipeline.secure_context.set_active_key_version(2)
        
        with pytest.raises(Exception):
            await e2e_pipeline.verify(user_id, fingerprint, key_version=1)
        
        enroll_v2 = await e2e_pipeline.enroll(user_id, fingerprint, key_version=2)
        assert enroll_v2.key_version == 2
        
        verify_v2 = await e2e_pipeline.verify(user_id, fingerprint, key_version=2)
        assert verify_v2.key_version == 2
    
    @pytest.mark.asyncio
    async def test_concurrent_verifications(self, e2e_pipeline):
        """Multiple concurrent verifications should work."""
        user_id = "concurrent_user"
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        await e2e_pipeline.enroll(user_id, fingerprint)
        
        tasks = [e2e_pipeline.verify(user_id, fingerprint) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        for r in results:
            assert r.verified is True
            assert r.key_version == 1
    
    @pytest.mark.asyncio
    async def test_full_latency_breakdown(self, e2e_pipeline):
        """Verify latency measurement works."""
        user_id = "latency_user"
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        await e2e_pipeline.enroll(user_id, fingerprint)
        result = await e2e_pipeline.verify(user_id, fingerprint)
        
        required_phases = [
            'client_pipeline_ms',
            'he_encrypt_probe_ms', 
            'he_compute_ms',
            'tee_key_release_ms',
            'server_verify_ms',
            'total_ms',
        ]
        
        for phase in required_phases:
            assert phase in result.latency_ms
            assert result.latency_ms[phase] > 0
        
        assert result.latency_ms['total_ms'] < 5000
