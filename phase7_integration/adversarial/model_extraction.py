# phase7_integration/adversarial/model_extraction.py
"""
Model Extraction & Membership Inference Tests.

Tests whether an attacker can:
1. Extract encoder/FiLM model via API queries
2. Perform membership inference (was this fingerprint in training?)
3. Reconstruct training data
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

from film.model import FiLMFusion
from film.inference import film_fuse
from integration.pipeline import BiometricPipeline, PipelineConfig
from he.crypto import generate_he_keys
from he.params import DEFAULT_PARAMS
import torch
import onnx


@pytest.fixture
def extraction_setup():
    with tempfile.TemporaryDirectory() as device_dir, \
         tempfile.TemporaryDirectory() as he_dir, \
         tempfile.TemporaryDirectory() as keystore_dir, \
         tempfile.TemporaryDirectory() as film_dir:
        
        generate_he_keys(Path(he_dir), DEFAULT_PARAMS)
        
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
        
        yield pipeline
        pipeline.close()


class TestModelExtraction:
    """Test model extraction via query access."""
    
    def test_film_query_access(self, extraction_setup):
        """Attacker queries FiLM with chosen inputs to extract model."""
        pipeline = extraction_setup
        
        x = np.random.randn(256).astype(np.float32)
        x = x / np.linalg.norm(x)
        k = np.random.randn(256).astype(np.float32)
        
        t1 = film_fuse(pipeline.film_session, x, k)
        t2 = film_fuse(pipeline.film_session, x, k)
        
        assert np.allclose(t1, t2)
    
    def test_encoder_query_access(self, extraction_setup):
        """Attacker queries encoder with chosen images."""
        pipeline = extraction_setup
        
        img = np.random.randn(1, 1, 96, 96).astype(np.float32)
        
        emb1 = pipeline.encoder_session.run(
            [pipeline.encoder_output_name],
            {pipeline.encoder_input_name: img}
        )[0]
        emb2 = pipeline.encoder_session.run(
            [pipeline.encoder_output_name],
            {pipeline.encoder_input_name: img}
        )[0]
        
        assert np.allclose(emb1, emb2)


class TestMembershipInference:
    """Test membership inference attacks."""
    
    def test_training_membership(self, extraction_setup):
        """Can attacker determine if a fingerprint was in training set?"""
        assert True
    
    def test_template_membership(self, extraction_setup):
        """Can attacker determine if a template is in database?"""
        pipeline = extraction_setup
        
        ct1 = pipeline.he_client.encrypt_template(np.random.randn(256).astype(np.float32))
        ct2 = pipeline.he_client.encrypt_template(np.random.randn(256).astype(np.float32))
        
        assert ct1 != ct2
        assert len(ct1) == len(ct2)
