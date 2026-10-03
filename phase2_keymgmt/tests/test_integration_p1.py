# phase2_keymgmt/tests/test_integration_p1.py
"""
Integration test: Phase 1 encoder output + Phase 2 key → FiLM input.
Verifies dimensional compatibility and value ranges.
"""
import pytest
import numpy as np
import torch
import tempfile
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from keystore.software import SoftwareSecureKeyStore
from keystore.derivation import derive_key_vector

# Mock Phase 1 encoder interface
class MockEncoder:
    """Simulates Phase 1 FingerprintEncoder output."""
    def __init__(self, embedding_dim=256):
        self.embedding_dim = embedding_dim
    
    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        # Return L2-normalized random embeddings
        batch = x.shape[0]
        emb = torch.randn(batch, self.embedding_dim)
        return torch.nn.functional.normalize(emb, p=2, dim=1)
    
    def get_embedding_dim(self) -> int:
        return self.embedding_dim

def test_encoder_key_dimension_match():
    """Encoder embedding_dim == key_vector length."""
    encoder = MockEncoder(embedding_dim=256)
    seed = b"test_seed_32_bytes_for_dim_check"
    key_vector = derive_key_vector(seed, length=256)
    
    assert encoder.get_embedding_dim() == len(key_vector) == 256

def test_encoder_output_range_matches_key_range():
    """Encoder outputs in [-1,1] (L2 norm), key_vector in [-1,1]."""
    encoder = MockEncoder(embedding_dim=256)
    x = torch.randn(1, 1, 96, 96)
    emb = encoder(x).numpy()[0]
    
    # L2 normalized → each component in [-1, 1]
    assert emb.min() >= -1.0
    assert emb.max() <= 1.0
    
    seed = b"test_seed_32_bytes_for_rangechk!"
    kv = derive_key_vector(seed, length=256, range_min=-1.0, range_max=1.0)
    
    assert kv.min() >= -1.0
    assert kv.max() <= 1.0

def test_film_input_compatibility():
    """FiLM expects (embedding_dim,) for both x and k."""
    encoder = MockEncoder(embedding_dim=256)
    store = SoftwareSecureKeyStore(
        storage_dir=tempfile.mkdtemp(),
        master_key=b"test_master_key_32_bytes_long!!",
        pbkdf2_iterations=1000,
        use_mlock=False,
    )
    
    user_id = "compat_user"
    store.generate_seed(user_id)
    material = store.get_key_material(user_id)
    
    # Simulate enrollment
    x = encoder(torch.randn(1, 1, 96, 96)).numpy()[0]  # (256,)
    k = material.key_vector  # (256,)
    
    assert x.shape == (256,)
    assert k.shape == (256,)
    assert x.dtype == np.float32
    assert k.dtype == np.float32
    
    # FiLM operation (element-wise)
    gamma = 1.0 + 0.1 * k
    beta = 0.1 * k
    t = gamma * x + beta
    t = t / np.linalg.norm(t)
    
    assert t.shape == (256,)
    assert np.isclose(np.linalg.norm(t), 1.0)
