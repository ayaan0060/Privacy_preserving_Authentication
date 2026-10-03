# phase2_keymgmt/keystore/rotation.py
"""
Key rotation policies and revocation verification.
"""
import numpy as np
from typing import List, Optional
from datetime import datetime, timezone

from .models import KeyVersion, KeyRecord
from .interface import SecureKeyStore, KeyRevokedError

class RotationPolicy:
    """Configurable rotation policies."""
    
    def __init__(
        self,
        max_age_days: Optional[int] = 90,
        max_verifications: Optional[int] = None,
        compromise_threshold: float = 0.0,  # Risk score trigger
    ):
        self.max_age_days = max_age_days
        self.max_verifications = max_verifications
        self.compromise_threshold = compromise_threshold
    
    def should_rotate(self, version: KeyVersion, verification_count: int = 0) -> tuple[bool, str]:
        """Returns (should_rotate, reason)."""
        if self.max_age_days:
            age = (datetime.now(timezone.utc) - version.created_at).days
            if age >= self.max_age_days:
                return True, f"max_age_exceeded ({age} days)"
        
        if self.max_verifications and verification_count >= self.max_verifications:
            return True, f"max_verifications_exceeded ({verification_count})"
        
        return False, "ok"


def verify_revocation_effectiveness(
    store: SecureKeyStore,
    user_id: str,
    old_version: int,
    new_version: int,
    encoder,  # Phase 1 encoder
    film_fusion,  # Phase 3 FiLM (or mock)
) -> bool:
    """
    PROOF: After rotation, old key cannot produce matching template.
    
    This is the core "cancelable biometric" guarantee test.
    Returns True if revocation is effective (old key → no match).
    """
    # Get old and new key material
    old_material = store.get_key_material(user_id, old_version)
    new_material = store.get_key_material(user_id, new_version)
    
    # Generate a test embedding (or use fixed test vector)
    test_embedding = encoder.generate_test_embedding()  # Mock or real
    
    # Fuse with old key
    old_template = film_fusion.fuse(test_embedding, old_material.key_vector)
    
    # Fuse with new key
    new_template = film_fusion.fuse(test_embedding, new_material.key_vector)
    
    # Compute similarity
    similarity = np.dot(old_template, new_template)  # Both L2 normalized
    
    # Revocation effective if similarity is near-random (≈0 for 256-d)
    # Threshold: 3 standard deviations of random 256-d cosine (~0.15)
    REVOCATION_THRESHOLD = 0.15
    
    is_effective = abs(similarity) < REVOCATION_THRESHOLD
    
    print(f"[REVOCATION TEST] Old v{old_version} vs New v{new_version}: "
          f"cosine={similarity:.4f} (threshold={REVOCATION_THRESHOLD}) "
          f"{'PASS' if is_effective else 'FAIL'}")
    
    return is_effective
