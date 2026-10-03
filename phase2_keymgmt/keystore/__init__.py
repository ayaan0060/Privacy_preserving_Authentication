# phase2_keymgmt/keystore/__init__.py
from .models import KeyRecord, KeyVersion, DerivedKeyMaterial, UserID, KeyID
from .interface import (
    SecureKeyStore,
    KeyStoreError,
    KeyNotFoundError,
    KeyRevokedError,
    KeyExistsError,
    BackendUnavailableError,
)
from .software import SoftwareSecureKeyStore
from .derivation import derive_key_vector, hkdf_sha256, verify_key_vector_consistency
from .rotation import RotationPolicy, verify_revocation_effectiveness

__all__ = [
    "KeyRecord",
    "KeyVersion",
    "DerivedKeyMaterial",
    "UserID",
    "KeyID",
    "SecureKeyStore",
    "KeyStoreError",
    "KeyNotFoundError",
    "KeyRevokedError",
    "KeyExistsError",
    "BackendUnavailableError",
    "SoftwareSecureKeyStore",
    "derive_key_vector",
    "hkdf_sha256",
    "verify_key_vector_consistency",
    "RotationPolicy",
    "verify_revocation_effectiveness",
]
