# phase4_he/tests/test_integration_p3.py
"""
Integration: Phase 3 FiLM output → Phase 4 HE encrypt → compute → decrypt.
"""
import pytest
import numpy as np
import tempfile
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

class MockFiLM:
    def __init__(self):
        self.embedding_dim = 256
    
    def fuse(self, x, k):
        gamma = 1.0 + k
        beta = k
        t = gamma * x + beta
        return t / np.linalg.norm(t)

def mock_key_vector():
    return np.random.randn(256).astype(np.float32) * 0.5

from he.crypto import HEClient, generate_he_keys
from he.compute import HESimilarityServer, plaintext_dot_product
from he.params import DEFAULT_PARAMS

@pytest.fixture
def he_setup():
    with tempfile.TemporaryDirectory() as tmpdir:
        generate_he_keys(tmpdir, DEFAULT_PARAMS)
        client = HEClient(tmpdir, DEFAULT_PARAMS)
        server = HESimilarityServer(tmpdir, DEFAULT_PARAMS)
        yield client, server

def test_film_output_he_encrypt_decrypt(he_setup):
    client, server = he_setup
    film = MockFiLM()
    
    x = np.random.randn(256).astype(np.float32)
    x = x / np.linalg.norm(x)
    k = mock_key_vector()
    
    t = film.fuse(x, k)
    assert t.shape == (256,)
    assert np.isclose(np.linalg.norm(t), 1.0, atol=1e-5)
    
    ct = client.encrypt_template(t)
    ct_self = server.compute_similarity(ct, ct)
    score = client.decrypt_score(ct_self)
    
    assert abs(score - 1.0) < 1e-3

def test_full_verification_flow(he_setup):
    client, server = he_setup
    film = MockFiLM()
    
    x_enroll = np.random.randn(256).astype(np.float32)
    x_enroll = x_enroll / np.linalg.norm(x_enroll)
    k_enroll = mock_key_vector()
    t_enroll = film.fuse(x_enroll, k_enroll)
    
    enrolled_ct = client.encrypt_template(t_enroll)
    
    x_probe = np.random.randn(256).astype(np.float32)
    x_probe = x_probe / np.linalg.norm(x_probe)
    t_probe = film.fuse(x_probe, k_enroll)
    
    probe_ct = client.encrypt_template(t_probe)
    result_ct = server.compute_similarity(enrolled_ct, probe_ct)
    score = client.decrypt_score(result_ct)
    
    pt_score = plaintext_dot_product(t_enroll, t_probe)
    
    assert abs(score - pt_score) < 1e-3
    assert -1 <= score <= 1

def test_key_rotation_changes_template(he_setup):
    """Verify that key rotation produces different encrypted template."""
    client, server = he_setup
    film = MockFiLM()
    
    x = np.random.randn(256).astype(np.float32)
    x = x / np.linalg.norm(x)
    
    k1 = mock_key_vector()
    t1 = film.fuse(x, k1)
    ct1 = client.encrypt_template(t1)
    
    k2 = mock_key_vector()
    t2 = film.fuse(x, k2)
    ct2 = client.encrypt_template(t2)
    
    ct_cross = server.compute_similarity(ct1, ct2)
    score = client.decrypt_score(ct_cross)
    
    assert abs(score) < 0.15, f"Key rotation ineffective: cross-similarity={score:.4f}"
