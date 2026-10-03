# phase2_keymgmt/src/crypto/interfaces.py
"""
SecureKeyStore Interface — THE CONTRACT FOR HARDWARE SWAP.
Phase 2 provides 'SoftwareKeyStore' (SIMULATED).
Phase 6 (Production) swaps in 'AndroidStrongBoxStore', 'iOSSecureEnclaveStore', 'HSMStore'.
NO OTHER CODE IMPORTS THE CONCRETE IMPLEMENTATION DIRECTLY.
Dependency Injection is used everywhere.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import time

@dataclass(frozen=True)
class KeyRecord:
    """Metadata stored alongside the encrypted seed blob."""
    user_id: str
    version: int              # Monotonically increasing integer
    created_at: float         # Unix timestamp
    is_revoked: bool
    # Hardware-specific metadata (e.g., key handle, attestation cert) goes in 'metadata'
    metadata: Dict[str, Any] 

class SecureKeyStore(ABC):
    """
    Abstract interface for a tamper-resistant key store.
    Security Properties Required by Implementation:
    1. Confidentiality: Seed bytes NEVER leave this boundary in plaintext.
    2. Integrity: Version rollback detection (monotonic counter or signed metadata).
    3. Atomicity: Rotation (Generate New + Revoke Old) is atomic or transactional.
    4. Binding: Keys bound to device/user (hardware binding preferred).
    """

    @abstractmethod
    def initialize_user(self, user_id: str) -> KeyRecord:
        """
        Generates a fresh 32-byte seed inside the secure boundary.
        Returns metadata (version=1). Seed NEVER returned.
        Raises: UserExistsError, HardwareError.
        """
        pass

    @abstractmethod
    def get_active_seed_handle(self, user_id: str) -> "SeedHandle":
        """
        Returns a HANDLE (context manager) to the active seed for derivation.
        The seed bytes are exposed ONLY inside the 'with' block (or via callback)
        and zeroized on exit.
        Raises: KeyNotFoundError, KeyRevokedError.
        """
        pass

    @abstractmethod
    def rotate_key(self, user_id: str) -> KeyRecord:
        """
        Atomic Revocation + Generation.
        1. Marks current active key 'revoked'.
        2. Generates new seed (version + 1).
        3. Returns new KeyRecord.
        Old seed MUST become unusable for derivation immediately.
        Raises: KeyNotFoundError, HardwareError.
        """
        pass

    @abstractmethod
    def get_key_history(self, user_id: str) -> List[KeyRecord]:
        """Audit trail: all versions (active + revoked)."""
        pass

    @abstractmethod
    def delete_user(self, user_id: str) -> bool:
        """GDPR/Right to be Forgotten. Wipes all key material."""
        pass

# --- Custom Exceptions ---
class KeyStoreError(Exception): pass
class UserExistsError(KeyStoreError): pass
class KeyNotFoundError(KeyStoreError): pass
class KeyRevokedError(KeyStoreError): pass
class HardwareError(KeyStoreError): pass

# --- Seed Handle Pattern (Prevents accidental leakage) ---
class SeedHandle:
    """
    RAII Wrapper for Seed Access.
    Usage:
        with store.get_active_seed_handle(user_id) as handle:
            seed_bytes = handle.seed  # Only valid INSIDE block
            k = derive_key(seed_bytes, ...)
        # Seed zeroized here automatically
    """
    def __init__(self, seed_bytes: bytes, record: KeyRecord, zeroizer=None):
        self._seed = seed_bytes
        self.record = record
        self._zeroizer = zeroizer # Callable to zero the buffer
        self._entered = False

    @property
    def seed(self) -> bytes:
        if not self._entered:
            raise RuntimeError("SeedHandle accessed outside context manager")
        return self._seed

    def __enter__(self):
        self._entered = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._entered = False
        if self._zeroizer:
            self._zeroizer(self._seed)
        self._seed = b'' # Drop ref
