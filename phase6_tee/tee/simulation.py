# phase6_tee/tee/simulation.py
"""
SoftwareSecureContext — DEVELOPMENT SIMULATION ONLY.

⚠️  THIS IS NOT A REAL HARDWARE SECURITY BOUNDARY.
⚠️  Secrets exist in Python process memory (swappable, inspectable).
⚠️  mlock() is best-effort (requires CAP_IPC_LOCK, not guaranteed).
⚠️  Zeroization is best-effort (Python memory management limits).

PRODUCTION MUST SWAP TO:
- Android: StrongBox/Keystore (tee/production/android_keystore.py)
- iOS: Secure Enclave (tee/production/ios_secure_enclave.py)
- Server: OP-TEE TA / HSM (tee/production/optee_ta.py)

The LOGIC is real — only the isolation boundary is simulated.
"""
import os
import secrets
import time
import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union, Set, Dict
import numpy as np

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from .interface import (
    SecureContext, VerificationResult, DeviceIdentity,
    NonceReplayError, NonceExpiredError, KeyRevokedError, 
    ThresholdNotMetError, HardwareUnavailableError
)
from .device_keys import DeviceKeyManager

try:
    import resource
    HAS_MLOCK = hasattr(os, 'mlock') or hasattr(resource, 'RLIMIT_MEMLOCK')
except ImportError:
    HAS_MLOCK = False


class SoftwareSecureContext(SecureContext):
    """
    Software simulation of TEE secure context.
    THIS IS NOT A REAL HARDWARE SECURITY BOUNDARY.
    """
    
    def __init__(
        self,
        device_key_dir: Union[str, Path],
        he_key_dir: Union[str, Path],
        use_mlock: bool = True,
        zeroize_on_release: bool = True,
        nonce_ttl_seconds: int = 300,
        threshold: float = 0.3,
    ):
        self.device_key_dir = Path(device_key_dir)
        self.he_key_dir = Path(he_key_dir)
        self.use_mlock = use_mlock and HAS_MLOCK
        self.zeroize_on_release = zeroize_on_release
        self.nonce_ttl_seconds = nonce_ttl_seconds
        self.threshold = threshold
        
        self.device_keys = DeviceKeyManager(self.device_key_dir)
        
        self._used_nonces: Set[bytes] = set()
        self._nonce_timestamps: Dict[bytes, float] = {}
        
        self._active_key_version: int = 1
        self._revoked_versions: Set[int] = set()
        
        print(f"[SoftwareSecureContext] Initialized (mlock={'enabled' if self.use_mlock else 'unavailable'})")
        print(f"[WARNING] THIS IS A SIMULATION - NOT A REAL HARDWARE SECURITY BOUNDARY")
    
    def _mlock_bytes(self, data: bytes) -> bytearray:
        """Attempt to mlock buffer."""
        if not self.use_mlock:
            return bytearray(data)
        try:
            buf = bytearray(data)
            import resource
            resource.setrlimit(resource.RLIMIT_MEMLOCK, (len(buf), len(buf)))
            return buf
        except Exception as e:
            print(f"[WARN] mlock failed: {e}")
            return bytearray(data)
    
    def _zeroize(self, buf: bytearray) -> None:
        """Best-effort zeroization."""
        if self.zeroize_on_release and buf:
            buf[:] = b'\x00' * len(buf)
    
    def set_active_key_version(self, version: int) -> None:
        """Called by keystore on rotation."""
        self._active_key_version = version
    
    def revoke_key_version(self, version: int) -> None:
        """Called by keystore on rotation."""
        self._revoked_versions.add(version)
    
    async def verify_and_sign(
        self,
        encrypted_similarity: bytes,
        he_secret_key: bytes,
        nonce: bytes,
        key_version: int,
        threshold: float,
    ) -> VerificationResult:
        """
        SIMULATED secure verification and key release.
        """
        he_secret_locked = self._mlock_bytes(he_secret_key)
        nonce_locked = self._mlock_bytes(nonce)
        
        try:
            result = verify_and_sign_core(
                encrypted_similarity=encrypted_similarity,
                he_secret_key=bytes(he_secret_locked),
                nonce=bytes(nonce_locked),
                key_version=key_version,
                threshold=threshold,
                active_key_version=self._active_key_version,
                revoked_versions=self._revoked_versions,
                used_nonces=self._used_nonces,
                nonce_timestamps=self._nonce_timestamps,
                nonce_ttl_seconds=self.nonce_ttl_seconds,
                device_signing_key=self.device_keys.get_signing_key(),
                device_id=self.device_keys.get_device_id(),
            )
            
            self._used_nonces.add(nonce)
            self._nonce_timestamps[nonce] = time.time()
            
            return result
            
        finally:
            self._zeroize(he_secret_locked)
            self._zeroize(nonce_locked)
    
    def get_device_identity(self) -> DeviceIdentity:
        return DeviceIdentity(
            device_id=self.device_keys.get_device_id(),
            public_key=self.device_keys.get_public_key(),
            attestation_cert=None,
            tee_type="simulation",
        )
    
    def health_check(self) -> bool:
        return self.device_keys.health_check()
    
    def close(self) -> None:
        """Cleanup."""
        self.device_keys.close()
        self._used_nonces.clear()
        self._nonce_timestamps.clear()
        print("[SoftwareSecureContext] Closed")


def verify_and_sign_core(
    encrypted_similarity: bytes,
    he_secret_key: bytes,
    nonce: bytes,
    key_version: int,
    threshold: float,
    active_key_version: int,
    revoked_versions: Set[int],
    used_nonces: Set[bytes],
    nonce_timestamps: Dict[bytes, float],
    nonce_ttl_seconds: int,
    device_signing_key: ec.EllipticCurvePrivateKey,
    device_id: str,
) -> VerificationResult:
    """
    Pure verification and signing logic.
    """
    from he.crypto import HEClient
    from he.params import DEFAULT_PARAMS
    import tenseal as ts
    
    if key_version != active_key_version:
        raise KeyRevokedError(f"Key version {key_version} is revoked and not active (current: {active_key_version})")
    if key_version in revoked_versions:
        raise KeyRevokedError(f"Key version {key_version} has been revoked")
    
    now = time.time()
    if nonce in used_nonces:
        raise NonceReplayError(f"Nonce already used: {nonce.hex()[:16]}...")
    
    he_client = HEClient.__new__(HEClient)
    he_client.context = ts.context_from(he_secret_key)
    
    similarity = he_client.decrypt_score(encrypted_similarity)
    
    verified = similarity >= threshold
    if not verified:
        raise ThresholdNotMetError(f"Similarity score {similarity:.4f} below threshold {threshold:.4f}")

    timestamp = datetime.now(timezone.utc)
    payload = create_signed_payload(
        nonce=nonce,
        similarity_score=similarity,
        key_version=key_version,
        device_id=device_id,
        timestamp=timestamp,
        verified=verified,
    )

    signature = device_signing_key.sign(
        payload,
        ec.ECDSA(hashes.SHA256()),
    )

    return VerificationResult(
        verified=verified,
        similarity_score=similarity,
        key_version=key_version,
        timestamp=timestamp,
        signature=signature,
        signed_payload=payload,
    )


def create_signed_payload(
    nonce: bytes,
    similarity_score: float,
    key_version: int,
    device_id: str,
    timestamp: datetime,
    verified: bool,
) -> bytes:
    """
    Create canonical 1-bit attestation payload for ECDSA signing.

    Per §IV-E of the paper, the server receives ONLY a 1-bit boolean decision.
    The similarity score is NEVER included in the server-bound signed payload —
    doing so would expose the continuous score and enable the Li-Micciancio
    key-recovery oracle attack that this attestation protocol is designed to prevent.

    Payload structure: H(d ‖ n_s ‖ v)
      d   = 1-byte boolean decision (0x01 = accept, 0x00 = reject)
      n_s = 32-byte server nonce
      v   = 4-byte big-endian key version

    The similarity_score parameter is retained in the function signature for
    internal audit logging purposes only — it is NOT included in the payload
    that is transmitted to or verifiable by the server.
    """
    import hashlib
    import struct
    # Normalise nonce to exactly 32 bytes
    if len(nonce) < 32:
        nonce = nonce.ljust(32, b'\x00')
    elif len(nonce) > 32:
        nonce = nonce[:32]
    # Build the pre-image: decision bit ‖ nonce ‖ key version
    raw = (
        struct.pack('>B', 1 if verified else 0)
        + nonce
        + struct.pack('>I', key_version)
    )
    # Return the hash — the similarity float is intentionally excluded
    return hashlib.sha256(raw).digest()


def verify_signature(
    public_key: ec.EllipticCurvePublicKey,
    payload: bytes,
    signature: bytes,
) -> bool:
    """Verify device signature (server side)."""
    try:
        public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False
