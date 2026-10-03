# phase4_he/tests/test_crypto.py
import pytest
import numpy as np
import tempfile
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from he.crypto import HEClient, generate_he_keys
from he.params import DEFAULT_PARAMS

@pytest.fixture
def key_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def client(key_dir):
    generate_he_keys(key_dir, DEFAULT_PARAMS)
    return HEClient(key_dir, DEFAULT_PARAMS)

def test_encrypt_decrypt_roundtrip(client):
    template = np.random.randn(256).astype(np.float32)
    template = template / np.linalg.norm(template)
    
    ct_bytes = client.encrypt_template(template)
    assert len(ct_bytes) > 0
    
    decrypted = client.decrypt_vector(ct_bytes, length=256)
    rel_error = np.abs(decrypted - template) / (np.abs(template) + 1e-10)
    assert np.max(rel_error) < 1e-3, f"Max relative error {np.max(rel_error):.2e}"

def test_decrypt_score(client):
    template = np.random.randn(256).astype(np.float32)
    template = template / np.linalg.norm(template)
    
    ct_bytes = client.encrypt_template(template)
    score = client.decrypt_score(ct_bytes)
    assert abs(score - template[0]) < 1e-3

def test_wrong_dimension_raises(client):
    template = np.random.randn(128).astype(np.float32)
    with pytest.raises(ValueError):
        client.encrypt_template(template)

def test_different_templates_different_ciphertexts(client):
    t1 = np.random.randn(256).astype(np.float32)
    t2 = np.random.randn(256).astype(np.float32)
    t1 = t1 / np.linalg.norm(t1)
    t2 = t2 / np.linalg.norm(t2)
    
    ct1 = client.encrypt_template(t1)
    ct2 = client.encrypt_template(t2)
    assert ct1 != ct2
