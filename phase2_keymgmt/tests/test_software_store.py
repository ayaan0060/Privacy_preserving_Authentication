# phase2_keymgmt/tests/test_software_store.py
"""
SoftwareSecureKeyStore specific tests: persistence, encryption, mlock.
"""
import pytest
import numpy as np
import tempfile
import shutil
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from keystore.software import SoftwareSecureKeyStore
from keystore.interface import KeyExistsError

@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield SoftwareSecureKeyStore(
            storage_dir=tmpdir,
            master_key=b"test_master_key_32_bytes_long!!",  # 32 bytes
            pbkdf2_iterations=1000,  # Fast for tests
            use_mlock=False,  # CI may not have CAP_IPC_LOCK
        )

def test_persistence_across_instances(store, user_id="persist_user"):
    """Data survives store restart."""
    store.generate_seed(user_id)
    mat1 = store.get_key_material(user_id)
    
    # Create new store instance pointing to same dir
    new_store = SoftwareSecureKeyStore(
        storage_dir=store.storage_dir,
        master_key=b"test_master_key_32_bytes_long!!",
        pbkdf2_iterations=1000,
        use_mlock=False,
    )
    
    mat2 = new_store.get_key_material(user_id)
    assert mat1.seed == mat2.seed
    assert np.allclose(mat1.key_vector, mat2.key_vector)

def test_wrong_master_key_fails(store, user_id="wrong_key_user"):
    store.generate_seed(user_id)
    
    # New store with different master key
    bad_store = SoftwareSecureKeyStore(
        storage_dir=store.storage_dir,
        master_key=b"wrong_master_key_32_bytes_long!!",
        pbkdf2_iterations=1000,
        use_mlock=False,
    )
    
    with pytest.raises(Exception):  # AEAD decryption fails
        bad_store.get_key_material(user_id)

def test_concurrent_access(store, user_id="concurrent_user"):
    """Thread safety."""
    import threading
    import time
    
    store.generate_seed(user_id)
    errors = []
    
    def reader():
        try:
            for _ in range(100):
                store.get_key_material(user_id)
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)
    
    threads = [threading.Thread(target=reader) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    assert len(errors) == 0

def test_max_versions_enforced(store):
    """Rotation respects max_versions."""
    store.max_versions = 3
    user_id = "max_ver_user"
    
    for i in range(5):
        if i == 0:
            store.generate_seed(user_id)
        else:
            store.rotate_key(user_id, f"rotation_{i}")
    
    versions = store.list_versions(user_id)
    active = [v for v in versions if v.is_active]
    assert len(active) == 1
    assert active[0].version == 5

def test_grace_period_metadata(store):
    """Grace period timestamp recorded on rotation."""
    user_id = "grace_user"
    store.generate_seed(user_id)
    store.rotate_key(user_id, "test")
    
    meta = store._load_meta(user_id)
    v1 = next(v for v in meta["versions"] if v["version"] == 1)
    assert "grace_period_ends" in v1
    assert v1["grace_period_ends"] > 0
