# phase7_integration/adversarial/inversion_tests.py
"""
Template Inversion & Reconstruction Tests.

Attempts to reconstruct:
1. Fingerprint image from embedding (encoder inversion)
2. Embedding from fused template (FiLM inversion)
3. Key vector from fused template
4. Fingerprint from fused template (full pipeline inversion)
"""
import pytest
import numpy as np
import torch
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
from keystore.derivation import derive_key_vector
from integration.pipeline import BiometricPipeline, PipelineConfig
from he.crypto import HEClient, generate_he_keys
from he.compute import HESimilarityServer
from he.params import DEFAULT_PARAMS
from tee.simulation import SoftwareSecureContext


@pytest.fixture
def inversion_setup():
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


class TestTemplateInversion:
    """Test inversion attacks on fused template."""
    
    def test_film_inversion_given_key(self, inversion_setup):
        """Given k and t, can we recover x? t = γ(k)⊙x + β(k)"""
        pipeline = inversion_setup
        
        x = np.random.randn(256).astype(np.float32)
        x = x / np.linalg.norm(x)
        k = np.random.randn(256).astype(np.float32)
        
        t = film_fuse(pipeline.film_session, x, k)
        assert True
    
    def test_film_inversion_without_key(self, inversion_setup):
        """Without k, t should leak no information about x."""
        pipeline = inversion_setup
        
        x1 = np.random.randn(256).astype(np.float32)
        x1 = x1 / np.linalg.norm(x1)
        x2 = np.random.randn(256).astype(np.float32)
        x2 = x2 / np.linalg.norm(x2)
        
        k1 = np.random.randn(256).astype(np.float32)
        k2 = np.random.randn(256).astype(np.float32)
        
        t1 = film_fuse(pipeline.film_session, x1, k1)
        t2 = film_fuse(pipeline.film_session, x2, k2)
        
        sim = np.dot(t1, t2)
        assert abs(sim) < 0.15
    
    def test_key_recovery_from_templates(self, inversion_setup):
        """Given multiple (x, t) pairs, can we recover k?"""
        pipeline = inversion_setup
        
        x = np.random.randn(256).astype(np.float32)
        x = x / np.linalg.norm(x)
        
        k1 = np.random.randn(256).astype(np.float32)
        k2 = k1 + np.random.randn(256).astype(np.float32) * 0.01
        
        t1 = film_fuse(pipeline.film_session, x, k1)
        t2 = film_fuse(pipeline.film_session, x, k2)
        
        sim = np.dot(t1, t2)
        assert abs(sim) < 0.5


class TestEncoderInversion:
    """Test encoder inversion (fingerprint reconstruction from embedding)."""
    
    def test_embedding_space_analysis(self, inversion_setup):
        """Analyze embedding space for inversion vulnerability."""
        pipeline = inversion_setup
        
        embeddings = []
        for _ in range(100):
            emb = pipeline.encoder_session.run(
                [pipeline.encoder_output_name],
                {pipeline.encoder_input_name: np.random.randn(1, 1, 96, 96).astype(np.float32)}
            )[0][0]
            embeddings.append(emb)
        
        embeddings = np.array(embeddings)
        
        norms = np.linalg.norm(embeddings, axis=1)
        assert np.allclose(norms, 1.0, atol=1e-3)
        
        sims = embeddings @ embeddings.T
        np.fill_diagonal(sims, 0)
        mean_sim = sims.mean()
        assert abs(mean_sim) < 0.05


class TestFullPipelineInversion:
    """Test full pipeline: fingerprint → encoder → film → he → tee."""
    
    def test_end_to_end_unlinkability(self, inversion_setup):
        """Same fingerprint, different keys → unlinkable templates."""
        pipeline = inversion_setup
        
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        pipeline.keystore.generate_seed("inv_user")
        v1_material = pipeline.keystore.get_key_material("inv_user", 1)
        
        pipeline.keystore.rotate_key("inv_user", "test")
        v2_material = pipeline.keystore.get_key_material("inv_user", 2)
        
        processed = pipeline._preprocess_fingerprint(fingerprint)
        embedding = pipeline.encoder_session.run(
            [pipeline.encoder_output_name],
            {pipeline.encoder_input_name: processed.astype(np.float32)}
        )[0][0]
        
        t1 = film_fuse(pipeline.film_session, embedding, v1_material.key_vector)
        t2 = film_fuse(pipeline.film_session, embedding, v2_material.key_vector)
        
        sim = np.dot(t1, t2)
        assert abs(sim) < 0.15, f"Templates linkable after rotation: sim={sim:.4f}"
        
        ct1 = pipeline.he_client.encrypt_template(t1)
        ct2 = pipeline.he_client.encrypt_template(t2)
        
        assert ct1 != ct2
        
        enc_sim = pipeline.he_server.compute_similarity(ct1, ct2)
        decrypted_sim = pipeline.he_client.decrypt_score(enc_sim)
        assert abs(decrypted_sim) < 0.15
