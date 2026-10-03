# phase4_he/tests/test_compute.py
import pytest
import numpy as np
import tempfile
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from he.compute import HESimilarityServer, plaintext_dot_product
from he.crypto import HEClient, generate_he_keys
from he.params import DEFAULT_PARAMS

@pytest.fixture
def key_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def server_and_client(key_dir):
    generate_he_keys(key_dir, DEFAULT_PARAMS)
    server = HESimilarityServer(key_dir, DEFAULT_PARAMS)
    client = HEClient(key_dir, DEFAULT_PARAMS)
    return server, client

def test_homomorphic_dot_vs_plaintext(server_and_client):
    server, client = server_and_client
    
    for _ in range(50):
        t1 = np.random.randn(256).astype(np.float32)
        t2 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        t2 = t2 / np.linalg.norm(t2)
        
        ct1 = client.encrypt_template(t1)
        ct2 = client.encrypt_template(t2)
        
        ct_result = server.compute_similarity(ct1, ct2)
        he_score = client.decrypt_score(ct_result)
        pt_score = plaintext_dot_product(t1, t2)
        
        rel_error = abs(he_score - pt_score) / (abs(pt_score) + 1e-3)
        assert rel_error < 1e-2, f"Rel error {rel_error:.2e} > 1e-2: HE={he_score:.6f}, PT={pt_score:.6f}"

def test_self_similarity_is_one(server_and_client):
    server, client = server_and_client
    
    t = np.random.randn(256).astype(np.float32)
    t = t / np.linalg.norm(t)
    
    ct = client.encrypt_template(t)
    ct_result = server.compute_similarity(ct, ct)
    score = client.decrypt_score(ct_result)
    
    assert abs(score - 1.0) < 1e-3

def test_orthogonal_templates_near_zero(server_and_client):
    server, client = server_and_client
    
    t1 = np.zeros(256, dtype=np.float32)
    t1[0] = 1.0
    t2 = np.zeros(256, dtype=np.float32)
    t2[1] = 1.0
    
    ct1 = client.encrypt_template(t1)
    ct2 = client.encrypt_template(t2)
    
    ct_result = server.compute_similarity(ct1, ct2)
    score = client.decrypt_score(ct_result)
    
    assert abs(score) < 1e-3

def test_batch_computation(server_and_client):
    server, client = server_and_client
    
    t_enroll = np.random.randn(256).astype(np.float32)
    t_enroll = t_enroll / np.linalg.norm(t_enroll)
    enrolled_ct = client.encrypt_template(t_enroll)
    
    probes = []
    for _ in range(10):
        t = np.random.randn(256).astype(np.float32)
        t = t / np.linalg.norm(t)
        probes.append(client.encrypt_template(t))
    
    results = server.compute_similarity_batch(enrolled_ct, probes)
    
    assert len(results) == 10
    for ct_result in results:
        score = client.decrypt_score(ct_result)
        assert -1 <= score <= 1
