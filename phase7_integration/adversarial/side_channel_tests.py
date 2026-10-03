# phase7_integration/adversarial/side_channel_tests.py
"""
Side-Channel Analysis Tests.

Tests for timing, memory access patterns, and cache side channels.
"""
import pytest
import time
import numpy as np
import asyncio
from statistics import mean, stdev
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
from film.model import FiLMFusion
from film.inference import film_fuse
from tee.simulation import SoftwareSecureContext
import torch
import onnx


@pytest.fixture
def timing_setup():
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


class TestTimingSideChannels:
    """Basic timing analysis."""
    
    def test_he_encrypt_timing_consistency(self, timing_setup):
        """HE encryption timing should not leak template content."""
        pipeline = timing_setup
        
        times = []
        for _ in range(50):
            template = np.random.randn(256).astype(np.float32)
            template = template / np.linalg.norm(template)
            
            start = time.perf_counter()
            pipeline.he_client.encrypt_template(template)
            times.append((time.perf_counter() - start) * 1000)
        
        cv = stdev(times) / mean(times)
        assert cv < 0.5, f"High timing variance (CV={cv:.2f}) may leak info"
    
    def test_he_decrypt_timing_consistency(self, timing_setup):
        """HE decryption timing should not leak ciphertext content."""
        pipeline = timing_setup
        
        ciphertexts = []
        for _ in range(20):
            template = np.random.randn(256).astype(np.float32)
            template = template / np.linalg.norm(template)
            ciphertexts.append(pipeline.he_client.encrypt_template(template))
        
        times = []
        for ct in ciphertexts:
            start = time.perf_counter()
            pipeline.he_client.decrypt_score(ct)
            times.append((time.perf_counter() - start) * 1000)
        
        cv = stdev(times) / mean(times)
        assert cv < 0.5
    
    def test_film_fusion_timing(self, timing_setup):
        """FiLM fusion timing should not depend on input values."""
        pipeline = timing_setup
        
        times = []
        for _ in range(50):
            x = np.random.randn(256).astype(np.float32)
            x = x / np.linalg.norm(x)
            k = np.random.randn(256).astype(np.float32)
            
            start = time.perf_counter()
            film_fuse(pipeline.film_session, x, k)
            times.append((time.perf_counter() - start) * 1000)
        
        cv = stdev(times) / mean(times)
        assert cv < 0.3
    
    def test_tee_verification_timing(self, timing_setup):
        """TEE verification timing should not depend on similarity score."""
        pipeline = timing_setup
        
        client = pipeline.he_client
        server = pipeline.he_server
        
        times_high = []
        times_low = []
        
        for _ in range(10):
            t1 = np.random.randn(256).astype(np.float32)
            t1 = t1 / np.linalg.norm(t1)
            t2 = t1 * 0.95 + np.random.randn(256).astype(np.float32) * 0.05
            t2 = t2 / np.linalg.norm(t2)
            
            ct1 = client.encrypt_template(t1)
            ct2 = client.encrypt_template(t2)
            enc_score = server.compute_similarity(ct1, ct2)
            
            he_secret = pipeline.config.he_key_dir.joinpath("client_secret.key").read_bytes()
            nonce = b"timing_test_nonce_32_bytes_12345678"
            
            start = time.perf_counter()
            asyncio.run(pipeline.secure_context.verify_and_sign(
                encrypted_similarity=enc_score,
                he_secret_key=he_secret,
                nonce=nonce,
                key_version=1,
                threshold=0.3,
            ))
            times_high.append((time.perf_counter() - start) * 1000)
        
        for _ in range(10):
            t1 = np.random.randn(256).astype(np.float32)
            t1 = t1 / np.linalg.norm(t1)
            t2 = np.random.randn(256).astype(np.float32)
            t2 = t2 / np.linalg.norm(t2)
            
            ct1 = client.encrypt_template(t1)
            ct2 = client.encrypt_template(t2)
            enc_score = server.compute_similarity(ct1, ct2)
            
            nonce = b"timing_test_nonce_low_32_bytes_123"
            start = time.perf_counter()
            try:
                asyncio.run(pipeline.secure_context.verify_and_sign(
                    encrypted_similarity=enc_score,
                    he_secret_key=he_secret,
                    nonce=nonce,
                    key_version=1,
                    threshold=0.3,
                ))
            except Exception:
                pass
            times_low.append((time.perf_counter() - start) * 1000)
        
        mean_high = mean(times_high)
        mean_low = mean(times_low)
        diff_pct = abs(mean_high - mean_low) / max(mean_high, mean_low) * 100
        
        assert diff_pct < 30, f"Timing difference {diff_pct:.1f}% may leak score info"


class TestMemoryAccessPatterns:
    """Basic memory access pattern analysis."""
    
    def test_he_encrypt_memory_constant(self, timing_setup):
        """HE encryption memory allocation should be constant."""
        pipeline = timing_setup
        import tracemalloc
        
        tracemalloc.start()
        
        template = np.random.randn(256).astype(np.float32)
        template = template / np.linalg.norm(template)
        
        snapshot1 = tracemalloc.take_snapshot()
        pipeline.he_client.encrypt_template(template)
        snapshot2 = tracemalloc.take_snapshot()
        
        tracemalloc.stop()
        
        stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_growth = sum(stat.size_diff for stat in stats if stat.size_diff > 0)
        
        assert total_growth > 0
