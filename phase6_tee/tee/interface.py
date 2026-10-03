# phase6_tee/tee/interface.py
"""
SecureContext — Abstract Base Class defining the TEE trust boundary.

PRODUCTION IMPLEMENTATIONS:
- Android: StrongBox/Keystore (hardware-isolated keystore)
- iOS: Secure Enclave + LocalAuthentication
- Linux: OP-TEE Trusted Application
- Server: HSM via PKCS#11 / Cloud KMS

SIMULATION (simulation.py): Software-only with mlock/zeroize best effort.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime, timezone


@dataclass(frozen=True)
class VerificationResult:
    """Result of secure verification."""
    verified: bool
    similarity_score: float
    key_version: int
    timestamp: datetime
    signature: Optional[bytes] = None
    signed_payload: Optional[bytes] = None


@dataclass(frozen=True)
class DeviceIdentity:
    """Device identity for attestation."""
    device_id: str
    public_key: bytes
    attestation_cert: Optional[bytes] = None
    tee_type: str = "unknown"


class SecureContext(ABC):
    """
    Hardware-isolated secure context for biometric verification decision.
    """
    
    @abstractmethod
    async def verify_and_sign(
        self,
        encrypted_similarity: bytes,
        he_secret_key: bytes,
        nonce: bytes,
        key_version: int,
        threshold: float,
    ) -> VerificationResult:
        """Core key-release operation inside secure boundary."""
        ...
    
    @abstractmethod
    def get_device_identity(self) -> DeviceIdentity:
        """Get device identity for server registration/attestation."""
        ...
    
    @abstractmethod
    def health_check(self) -> bool:
        """Verify secure context is operational."""
        ...
    
    @abstractmethod
    def close(self) -> None:
        """Cleanup: zeroize keys, release resources."""
        ...


class SecureContextError(Exception): pass
class NonceReplayError(SecureContextError): pass
class NonceExpiredError(SecureContextError): pass
class KeyRevokedError(SecureContextError): pass
class ThresholdNotMetError(SecureContextError): pass
class HardwareUnavailableError(SecureContextError): pass
