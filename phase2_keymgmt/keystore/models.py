# phase2_keymgmt/keystore/models.py
"""
Immutable data structures for key management.
No business logic — just typed containers.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid
import secrets
import numpy as np

@dataclass(frozen=True)
class KeyVersion:
    """Immutable key version identifier."""
    version: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    
    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
    
    def revoke(self, reason: str = "superseded") -> "KeyVersion":
        return KeyVersion(
            version=self.version,
            created_at=self.created_at,
            revoked_at=datetime.now(timezone.utc),
            revoked_reason=reason,
        )

@dataclass(frozen=True)
class KeyRecord:
    """
    Stored key record (encrypted at rest by SecureKeyStore).
    NEVER contains plaintext seed/key_vector outside SecureKeyStore boundary.
    """
    user_id: str
    version: KeyVersion
    # Encrypted fields (ciphertext + nonce + salt for PBKDF2)
    encrypted_seed: bytes          # 32 bytes encrypted
    encrypted_key_vector: bytes    # 256 * 4 bytes (float32) encrypted
    pk_he: bytes                   # CKKS public key (plaintext, not secret)
    salt: bytes                    # PBKDF2 salt (16 bytes)
    nonce: bytes                   # AEAD nonce (12 bytes for AES-GCM)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class DerivedKeyMaterial:
    """In-memory only — zeroized after use."""
    seed: bytes                    # 32 bytes raw seed
    key_vector: np.ndarray         # (256,) float32 in [-1, 1]
    version: KeyVersion
    
    def zeroize(self):
        """Best-effort zeroization (Python limits apply)."""
        if hasattr(self, '_seed'):
            # Can't truly zeroize bytes in Python, but we can delete refs
            pass
        if hasattr(self, '_key_vector'):
            self._key_vector.fill(0)
        # In production (Rust/C++), use explicit memset

# Type alias for clarity
UserID = str
KeyID = str  # Composite: f"{user_id}:{version}"
