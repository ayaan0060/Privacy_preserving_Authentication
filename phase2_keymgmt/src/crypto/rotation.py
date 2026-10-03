# phase2_keymgmt/src/crypto/rotation.py
"""
Key Rotation & Revocation Logic.
Implements the 'Cancelable' property: Compromised template -> Rotate Key -> New Unlinkable Template.
Old templates become mathematically useless (unlinkable) without the old seed.
"""
import numpy as np
from typing import Protocol, Tuple, List
from .interfaces import SecureKeyStore, KeyRecord, KeyNotFoundError, KeyRevokedError
from .hkdf import derive_key_vector
import logging

log = logging.getLogger(__name__)

# NOTE: load_config removed — KeyManager receives a pre-loaded config dict.


class KeyManager:
    """
    High-level Key Lifecycle Manager.
    Depends ONLY on SecureKeyStore interface.
    """
    def __init__(self, store: SecureKeyStore, config: dict):
        self.store = store
        self.config = config
        self.crypto_cfg = config['crypto']
        self.domain_tag = config['project']['domain_separation_tag']

    def enroll_user(self, user_id: str) -> KeyRecord:
        """Initial Enrollment: Generate Seed v1."""
        log.info(f"Enrolling user: {user_id}")
        record = self.store.initialize_user(user_id)
        log.info(f"User {user_id} enrolled with key version {record.version}")
        return record

    def get_fusion_key(self, user_id: str) -> Tuple[np.ndarray, KeyRecord]:
        """
        Retrieves active seed and derives FiLM Key Vector 'k'.
        Returns (k_vector, KeyRecord).
        Seed is zeroized immediately after derivation.
        """
        # Use SeedHandle context manager for secure access
        with self.store.get_active_seed_handle(user_id) as handle:
            seed = handle.seed
            record = handle.record

            # Derive k
            k = derive_key_vector(
                seed=seed,
                domain_tag=self.domain_tag,
                user_id=user_id,
                key_version=record.version,
                dim=self.crypto_cfg['key_vector_dim'],
                dtype=self.crypto_cfg['key_vector_dtype'],
                target_range=tuple(self.crypto_cfg['rescale_range'])
            )
        return k, record

    def revoke_and_reissue(self, user_id: str) -> KeyRecord:
        """
        CORE CANCELABLE OPERATION.
        1. Atomically revoke current key (mark revoked).
        2. Generate new seed (version + 1).
        3. Return new KeyRecord.

        SECURITY PROPERTY:
        - Old templates `t_old = FiLM(x, k_old)` are computationally unlinkable to
          new templates `t_new = FiLM(x, k_new)` because `k_old` and `k_new` are
          independent HKDF outputs (different `key_version` in `info`).
        - Old seed is destroyed (or marked unusable) inside SecureKeyStore.
        """
        log.warning(f"KEY ROTATION INITIATED for user: {user_id}")
        new_record = self.store.rotate_key(user_id)
        log.info(f"User {user_id} rotated to key version {new_record.version}")
        return new_record

    def get_audit_trail(self, user_id: str) -> List[KeyRecord]:
        return self.store.get_key_history(user_id)
