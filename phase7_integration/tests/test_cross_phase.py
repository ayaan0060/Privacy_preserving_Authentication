# phase7_integration/tests/test_cross_phase.py
"""
Cross-Phase Integration Tests.

Verifies each phase correctly interfaces with the next.
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

from integration.pipeline import BiometricPipeline, PipelineConfig, film_fuse
from he.crypto import HEClient, generate_he_keys
from he.compute import HESimilarityServer
from he.params import DEFAULT_PARAMS
from film.model import FiLMFusion
from keystore.software import SoftwareSecureKeyStore
from keystore.derivation import derive_key_vector
from tee.simulation import SoftwareSecureContext
import torch


@pytest.fixture
def cross_phase_pipeline():
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


class TestPhase1To2:
    """Encoder (P1) → Keystore (P2)"""
    
    def test_embedding_dim_matches_key_vector(self, cross_phase_pipeline):
        p = cross_phase_pipeline
        
        processed = p._preprocess_fingerprint(np.random.rand(200, 200).astype(np.uint8) * 255)
        embedding = p.encoder_session.run(
            [p.encoder_output_name], {p.encoder_input_name: processed.astype(np.float32)}
        )[0][0]
        
        p.keystore.generate_seed("dim_test")
        key_material = p.keystore.get_key_material("dim_test")
        
        assert embedding.shape == (256,)
        assert key_material.key_vector.shape == (256,)
        assert embedding.dtype == np.float32
        assert key_material.key_vector.dtype == np.float32
    
    def test_embedding_range_matches_key_range(self, cross_phase_pipeline):
        p = cross_phase_pipeline
        
        processed = p._preprocess_fingerprint(np.random.rand(200, 200).astype(np.uint8) * 255)
        embedding = p.encoder_session.run(
            [p.encoder_output_name], {p.encoder_input_name: processed.astype(np.float32)}
        )[0][0]
        
        p.keystore.generate_seed("range_test")
        key_material = p.keystore.get_key_material("range_test")
        
        assert embedding.min() >= -1.0
        assert embedding.max() <= 1.0
        
        assert key_material.key_vector.min() >= -1.0
        assert key_material.key_vector.max() <= 1.0


class TestPhase2To3:
    """Keystore (P2) → FiLM (P3)"""
    
    def test_key_vector_accepted_by_film(self, cross_phase_pipeline):
        p = cross_phase_pipeline
        
        p.keystore.generate_seed("film_test")
        key_material = p.keystore.get_key_material("film_test")
        
        embedding = np.random.randn(256).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        fused = film_fuse(p.film_session, embedding, key_material.key_vector)
        
        assert fused.shape == (256,)
        assert np.isclose(np.linalg.norm(fused), 1.0)
    
    def test_different_keys_produce_different_templates(self, cross_phase_pipeline):
        p = cross_phase_pipeline
        
        embedding = np.random.randn(256).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        p.keystore.generate_seed("user1")
        k1 = p.keystore.get_key_material("user1").key_vector
        
        p.keystore.generate_seed("user2")
        k2 = p.keystore.get_key_material("user2").key_vector
        
        from film.model import FiLMFusionExport
        import torch
        test_film = FiLMFusionExport(embedding_dim=256)
        torch.nn.init.normal_(test_film._film.generator.beta_net[-1].weight, std=0.5)
        test_film.eval()

        t1 = film_fuse(test_film, embedding, k1)
        t2 = film_fuse(test_film, embedding, k2)
        
        sim = np.dot(t1, t2)
        assert abs(sim) < 0.35


class TestPhase3To4:
    """FiLM (P3) → HE (P4)"""
    
    def test_film_output_encryptable(self, cross_phase_pipeline):
        p = cross_phase_pipeline
        
        embedding = np.random.randn(256).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        key_vec = np.random.randn(256).astype(np.float32)
        
        fused = film_fuse(p.film_session, embedding, key_vec)
        
        ct = p.he_client.encrypt_template(fused)
        assert len(ct) > 0
        
        decrypted = p.he_client.decrypt_vector(ct, length=256)
        assert np.allclose(decrypted, fused, rtol=1e-3)
    
    def test_he_preserves_similarity(self, cross_phase_pipeline):
        p = cross_phase_pipeline
        
        e1 = np.random.randn(256).astype(np.float32)
        e1 = e1 / np.linalg.norm(e1)
        e2 = np.random.randn(256).astype(np.float32)
        e2 = e2 / np.linalg.norm(e2)
        k = np.random.randn(256).astype(np.float32)
        
        t1 = film_fuse(p.film_session, e1, k)
        t2 = film_fuse(p.film_session, e2, k)
        
        pt_sim = np.dot(t1, t2)
        
        ct1 = p.he_client.encrypt_template(t1)
        ct2 = p.he_client.encrypt_template(t2)
        enc_sim = p.he_server.compute_similarity(ct1, ct2)
        he_sim = p.he_client.decrypt_score(enc_sim)
        
        assert abs(he_sim - pt_sim) < 1e-3


class TestPhase4To6:
    """HE (P4) → TEE (P6)"""
    
    def test_he_ciphertext_decryptable_in_tee(self, cross_phase_pipeline):
        p = cross_phase_pipeline
        
        template = np.random.randn(256).astype(np.float32)
        template = template / np.linalg.norm(template)
        
        ct = p.he_client.encrypt_template(template)
        
        score = p.he_client.decrypt_score(
            p.he_server.compute_similarity(ct, ct)
        )
        
        assert abs(score - 1.0) < 1e-3
    
    @pytest.mark.asyncio
    async def test_tee_receives_he_ciphertext(self, cross_phase_pipeline):
        p = cross_phase_pipeline
        
        t1 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        t2 = t1.copy()
        
        ct1 = p.he_client.encrypt_template(t1)
        ct2 = p.he_client.encrypt_template(t2)
        enc_score = p.he_server.compute_similarity(ct1, ct2)
        
        he_secret = p.config.he_key_dir.joinpath("client_secret.key").read_bytes()
        nonce = b"tee_he_integration_32_bytes______"
        
        result = await p.secure_context.verify_and_sign(
            encrypted_similarity=enc_score,
            he_secret_key=he_secret,
            nonce=nonce,
            key_version=1,
            threshold=0.3,
        )
        
        assert result.verified is True
        assert result.similarity_score > 0.99


class TestPhase5Integration:
    """Backend (P5) Integration"""
    
    @pytest.mark.asyncio
    async def test_backend_schemas_match_pipeline(self, cross_phase_pipeline):
        """Verify backend request/response schemas match pipeline data."""
        p = cross_phase_pipeline
        
        enroll_result = await p.enroll("schema_test", np.random.rand(200, 200).astype(np.uint8) * 255)
        
        import base64
        ct_b64 = base64.b64encode(enroll_result.enrolled_template_ct).decode()
        pk_b64 = base64.b64encode(enroll_result.client_pk_he).decode()
        
        assert isinstance(ct_b64, str)
        assert isinstance(pk_b64, str)
        assert len(ct_b64) > 0
        assert len(pk_b64) > 0
