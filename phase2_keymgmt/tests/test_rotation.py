# phase2_keymgmt/tests/test_rotation.py
"""
Revocation effectiveness proof: old key → unlinkable template.
"""
import pytest
import numpy as np
import sys, os
from unittest.mock import Mock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from keystore.software import SoftwareSecureKeyStore
from keystore.rotation import verify_revocation_effectiveness
from keystore.derivation import derive_key_vector

@pytest.fixture
def store():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        yield SoftwareSecureKeyStore(
            storage_dir=tmpdir,
            master_key=b"test_master_key_32_bytes_long!!",
            pbkdf2_iterations=1000,
            use_mlock=False,
        )

@pytest.fixture
def mock_encoder():
    """Mock Phase 1 encoder returning fixed dense L2-normalized test embedding."""
    encoder = Mock()
    rng = np.random.default_rng(42)
    test_emb = rng.normal(size=256).astype(np.float32)
    test_emb = test_emb / np.linalg.norm(test_emb)
    encoder.generate_test_embedding.return_value = test_emb
    return encoder

@pytest.fixture
def mock_film():
    """Mock FiLM fusion: t = gamma * x + beta, then L2 normalize."""
    film = Mock()
    def fuse(x, k):
        gamma = 1.0 + k
        beta = k
        t = gamma * x + beta
        norm = np.linalg.norm(t)
        if norm > 0:
            t = t / norm
        return t
    film.fuse.side_effect = fuse
    return film

def test_revocation_effectiveness(store, mock_encoder, mock_film):
    """Core test: rotated key produces unlinkable template."""
    user_id = "revoke_test_user"
    
    # Enroll with v1
    v1 = store.generate_seed(user_id)
    mat1 = store.get_key_material(user_id, v1.version)
    
    # Rotate to v2
    v2 = store.rotate_key(user_id, "compromise")
    mat2 = store.get_key_material(user_id, v2.version)
    
    # Verify revocation
    effective = verify_revocation_effectiveness(
        store, user_id, v1.version, v2.version,
        mock_encoder, mock_film
    )
    
    assert effective, "Revocation failed: old and new templates are linkable!"

def test_multiple_rotations_uncorrelated(store, mock_encoder, mock_film):
    """Each rotation produces independent template space."""
    user_id = "multi_rotate_user"
    
    versions = []
    materials = []
    
    for i in range(5):
        if i == 0:
            v = store.generate_seed(user_id)
        else:
            v = store.rotate_key(user_id, f"rotation_{i}")
        versions.append(v)
        materials.append(store.get_key_material(user_id, v.version))
    
    # All pairwise similarities should be near-zero
    test_emb = mock_encoder.generate_test_embedding()
    templates = [mock_film.fuse(test_emb, m.key_vector) for m in materials]
    
    for i in range(len(templates)):
        for j in range(i+1, len(templates)):
            sim = np.dot(templates[i], templates[j])
            assert abs(sim) < 0.20, f"Templates v{i+1} and v{j+1} correlated: {sim:.4f}"

def test_same_embedding_different_keys_uncorrelated():
    """Unit test: same x, different k → uncorrelated t."""
    rng = np.random.default_rng(42)
    x = rng.normal(size=256).astype(np.float32)
    x = x / np.linalg.norm(x)
    
    k1 = derive_key_vector(b"seed1_32_bytes_long_for_testing!")
    k2 = derive_key_vector(b"seed2_32_bytes_long_for_testing!")
    
    # Simple FiLM
    def film_fuse(x, k):
        gamma = 1.0 + k
        beta = k
        t = gamma * x + beta
        return t / np.linalg.norm(t)
    
    t1 = film_fuse(x, k1)
    t2 = film_fuse(x, k2)
    
    sim = np.dot(t1, t2)
    assert abs(sim) < 0.15, f"Same embedding, different keys correlated: {sim:.4f}"
