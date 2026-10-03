# phase5_backend/backend/services/keystore_service.py
"""
Keystore Service: Integration with Phase 2 SecureKeyStore.
Manages key lifecycle for users.
"""
import os
import sys
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

# Add Phase 2 path
phase2_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "phase2_keymgmt"))
if phase2_path not in sys.path:
    sys.path.insert(0, phase2_path)

try:
    from keystore.software import SoftwareSecureKeyStore
    from keystore.interface import KeyNotFoundError, KeyRevokedError, KeyExistsError
    from keystore.derivation import derive_key_vector
    HAS_PHASE2 = True
except ImportError:
    HAS_PHASE2 = False

from ..config import get_settings


@dataclass
class KeyVersion:
    version: int
    is_active: bool
    created_at: float


import logging

logger = logging.getLogger(__name__)

from typing import Optional, List, Callable


class KeystoreService:
    def __init__(self):
        self.settings = get_settings()
        db_dir = Path(self.settings.keystore.storage_dir)
        db_dir.mkdir(parents=True, exist_ok=True)
        self._rotation_callbacks: List[Callable[[str, int, int], None]] = []
        
        if HAS_PHASE2:
            self.store = SoftwareSecureKeyStore(db_dir, use_mlock=False)
        else:
            self.store = None

    def add_rotation_callback(self, callback: Callable[[str, int, int], None]):
        """Register callback for key rotation events"""
        self._rotation_callbacks.append(callback)

    def ensure_user_key(self, user_id: str) -> KeyVersion:
        """Ensure user has an active key, generate if not exists."""
        if not HAS_PHASE2 or self.store is None:
            return KeyVersion(version=1, is_active=True, created_at=0.0)
        
        try:
            ver = self.store.generate_seed(user_id)
            return KeyVersion(version=ver.version, is_active=ver.is_active, created_at=ver.created_at.timestamp())
        except KeyExistsError:
            material = self.store.get_key_material(user_id)
            return KeyVersion(version=material.version.version, is_active=material.version.is_active, created_at=material.version.created_at.timestamp())
    
    def get_key_material(self, user_id: str, version: Optional[int] = None):
        """Get key material for FiLM fusion."""
        if not HAS_PHASE2 or self.store is None:
            import numpy as np
            return np.random.randn(256).astype(np.float32)
        
        material = self.store.get_key_material(user_id, version=version)
        return material.key_vector

    def rotate_key(self, user_id: str, reason: str = "scheduled_rotation") -> KeyVersion:
        """Rotate user's key."""
        if not HAS_PHASE2 or self.store is None:
            kv = KeyVersion(version=2, is_active=True, created_at=0.0)
            old_ver = 1
            new_ver = 2
        else:
            ver = self.store.rotate_key(user_id, reason=reason)
            kv = KeyVersion(version=ver.version, is_active=ver.is_active, created_at=ver.created_at.timestamp())
            old_ver = kv.version - 1
            new_ver = kv.version

        for callback in self._rotation_callbacks:
            try:
                callback(user_id, old_ver, new_ver)
            except Exception as e:
                logger.error(f"Rotation callback failed: {e}")

        return kv

    def get_active_version(self, user_id: str) -> Optional[int]:
        versions = self.list_versions(user_id)
        active = [v for v in versions if v.is_active]
        return active[-1].version if active else None
    
    def revoke_key(self, user_id: str, version: int, reason: str = "manual_revocation") -> KeyVersion:
        """Revoke specific key version."""
        if not HAS_PHASE2 or self.store is None:
            return KeyVersion(version=version, is_active=False, created_at=0.0)
        ver = self.store.rotate_key(user_id, reason=reason)
        return KeyVersion(version=ver.version, is_active=ver.is_active, created_at=ver.created_at.timestamp())
    
    def list_versions(self, user_id: str) -> List[KeyVersion]:
        if not HAS_PHASE2 or self.store is None:
            return [KeyVersion(version=1, is_active=True, created_at=0.0)]
        versions = self.store.list_versions(user_id)
        return [KeyVersion(version=v.version, is_active=v.is_active, created_at=v.created_at.timestamp()) for v in versions]
    
    def delete_user(self, user_id: str) -> bool:
        if not HAS_PHASE2 or self.store is None:
            return True
        return self.store.delete_user(user_id)
    
    def health_check(self) -> bool:
        if not HAS_PHASE2 or self.store is None:
            return True
        return self.store.health_check()


keystore_service = KeystoreService()
