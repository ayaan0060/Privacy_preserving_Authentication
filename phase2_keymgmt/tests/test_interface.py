# phase2_keymgmt/tests/test_interface.py
"""
ABC compliance tests — any SecureKeyStore implementation must pass these.
"""
import pytest
import numpy as np
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from keystore.interface import SecureKeyStore, KeyNotFoundError, KeyRevokedError, KeyExistsError
from keystore.models import KeyVersion, DerivedKeyMaterial

class TestSecureKeyStoreContract:
    """Test suite run against ANY SecureKeyStore implementation."""
    
    @pytest.fixture
    def store(self) -> SecureKeyStore:
        from keystore.software import SoftwareSecureKeyStore
        import tempfile
        tmp_dir = tempfile.mkdtemp()
        return SoftwareSecureKeyStore(tmp_dir, grace_period_hours=0)
    
    @pytest.fixture
    def user_id(self) -> str:
        return "test_user_" + str(np.random.randint(10000))
    
    def test_generate_and_retrieve(self, store: SecureKeyStore, user_id: str):
        version = store.generate_seed(user_id)
        assert isinstance(version, KeyVersion)
        assert version.version == 1
        assert version.is_active
        
        material = store.get_key_material(user_id)
        assert isinstance(material, DerivedKeyMaterial)
        assert material.seed is not None
        assert len(material.seed) == 32
        assert material.key_vector.shape == (256,)
        assert material.key_vector.dtype == np.float32
        assert material.key_vector.min() >= -1.0 - 1e-5
        assert material.key_vector.max() <= 1.0 + 1e-5
        assert material.version.version == 1
    
    def test_deterministic_derivation(self, store: SecureKeyStore, user_id: str):
        """Same version always returns same key_vector."""
        store.generate_seed(user_id)
        mat1 = store.get_key_material(user_id)
        mat2 = store.get_key_material(user_id)
        assert np.allclose(mat1.key_vector, mat2.key_vector)
        assert mat1.seed == mat2.seed
    
    def test_rotate_key_revokes_old(self, store: SecureKeyStore, user_id: str):
        v1 = store.generate_seed(user_id)
        assert v1.version == 1
        
        v2 = store.rotate_key(user_id, "test_rotation")
        assert v2.version == 2
        
        # Old version should be revoked (after grace period)
        versions = store.list_versions(user_id)
        v1_record = next(v for v in versions if v.version == 1)
        assert not v1_record.is_active
        assert v1_record.revoked_reason == "test_rotation"
        
        # New version should be active
        v2_record = next(v for v in versions if v.version == 2)
        assert v2_record.is_active
    
    def test_get_revoked_key_raises(self, store: SecureKeyStore, user_id: str):
        store.generate_seed(user_id)
        store.rotate_key(user_id, "test")
        
        # Immediately after rotation, grace period may allow access
        # But we can test the revoked version directly
        with pytest.raises((KeyRevokedError, KeyNotFoundError)):
            store.get_key_material(user_id, version=1)
    
    def test_list_versions(self, store: SecureKeyStore, user_id: str):
        store.generate_seed(user_id)
        store.rotate_key(user_id)
        store.rotate_key(user_id)
        
        versions = store.list_versions(user_id)
        assert len(versions) == 3
        assert versions[0].version == 1
        assert versions[1].version == 2
        assert versions[2].version == 3
        assert not versions[0].is_active
        assert not versions[1].is_active
        assert versions[2].is_active
    
    def test_delete_user(self, store: SecureKeyStore, user_id: str):
        store.generate_seed(user_id)
        assert store.delete_user(user_id) is True
        assert store.delete_user(user_id) is False  # Already deleted
        
        with pytest.raises(KeyNotFoundError):
            store.get_key_material(user_id)
    
    def test_public_key_he_retrieval(self, store: SecureKeyStore, user_id: str):
        store.generate_seed(user_id)
        pk = store.get_public_key_he(user_id)
        assert isinstance(pk, bytes)
        assert len(pk) == 32  # Placeholder length
    
    def test_health_check(self, store: SecureKeyStore):
        assert store.health_check() is True
