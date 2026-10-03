# phase2_keymgmt/keystore/interface.py
"""
SecureKeyStore — Abstract Base Class defining the trust boundary.
PRODUCTION IMPLEMENTATIONS swap this backend:
  - Android: Keystore/StrongBox (hardware-backed)
  - iOS: Secure Enclave + Keychain
  - Server: HSM via PKCS#11 or Cloud KMS
  - TEE: OP-TEE Trusted Application

DEV IMPLEMENTATION (software.py) simulates the boundary with mlock/zeroize.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
import numpy as np

from .models import KeyRecord, KeyVersion, DerivedKeyMaterial, UserID, KeyID

class SecureKeyStore(ABC):
    """
    Cryptographic key lifecycle within a secure boundary.
    
    Security properties (MUST hold for all implementations):
    1. Plaintext seed/key_vector NEVER leaves this class's memory boundary.
    2. All persistence is encrypted (AEAD) with keys derived from user auth + hardware key.
    3. Rotation invalidates old key material — old templates become unverifiable.
    4. mlock()/zeroize() best effort for in-memory secrets.
    """
    
    @abstractmethod
    def generate_seed(self, user_id: UserID) -> KeyVersion:
        """
        Generate new 32-byte seed for user, derive key_vector, store encrypted.
        Returns the new KeyVersion.
        Raises: KeyExistsError if user has active key and force=False.
        """
        ...
    
    @abstractmethod
    def rotate_key(self, user_id: UserID, reason: str = "scheduled_rotation") -> KeyVersion:
        """
        Revoke current active key, generate new one.
        Old key_version is marked revoked (cannot derive key_vector).
        In-flight verifications using old key have grace_period_hours to complete.
        Returns new KeyVersion.
        """
        ...
    
    @abstractmethod
    def get_key_material(self, user_id: UserID, version: Optional[int] = None) -> DerivedKeyMaterial:
        """
        Retrieve DECrypted key material for use in FiLM fusion.
        If version=None, returns current active version.
        Raises: KeyNotFoundError, KeyRevokedError.
        
        CALLER MUST: Use immediately, then allow zeroize (drop reference).
        """
        ...
    
    @abstractmethod
    def get_public_key_he(self, user_id: UserID, version: Optional[int] = None) -> bytes:
        """Retrieve CKKS public key (plaintext, not secret)."""
        ...
    
    @abstractmethod
    def list_versions(self, user_id: UserID) -> List[KeyVersion]:
        """List all key versions for user (metadata only, no secrets)."""
        ...
    
    @abstractmethod
    def delete_user(self, user_id: UserID) -> bool:
        """Purge all key material for user (GDPR right to erasure)."""
        ...
    
    @abstractmethod
    def health_check(self) -> bool:
        """Verify backend is operational (HSM reachable, TEE responsive, etc.)."""
        ...

# --- Exceptions ---
class KeyStoreError(Exception): pass
class KeyNotFoundError(KeyStoreError): pass
class KeyRevokedError(KeyStoreError): pass
class KeyExistsError(KeyStoreError): pass
class BackendUnavailableError(KeyStoreError): pass
