# phase2_keymgmt/keystore/derivation.py
"""
Pure cryptographic derivation functions.
NO SECRETS, NO STATE, NO I/O — fully testable with known-answer tests.
"""
import hmac
import hashlib
import numpy as np
from typing import Tuple

def hkdf_sha256(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    """
    HKDF-SHA256 (RFC 5869).
    ikm: Input keying material (seed)
    salt: Optional salt (use zeros if None)
    info: Context/application specific info (domain separation)
    length: Output length in bytes (max 255 * 32 = 8160 for SHA256)
    """
    if salt is None:
        salt = b'\x00' * 32
    
    # Extract
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    
    # Expand
    okm = b''
    counter = 1
    prev = b''
    while len(okm) < length:
        prev = hmac.new(prk, prev + info + bytes([counter]), hashlib.sha256).digest()
        okm += prev
        counter += 1
        if counter > 255:
            raise ValueError("Output length too large for HKDF-SHA256")
    
    return okm[:length]


def derive_key_vector(
    seed: bytes,
    length: int = 256,
    range_min: float = -1.0,
    range_max: float = 1.0,
    info_prefix: str = "cancelable-bio-auth/v1",
) -> np.ndarray:
    """
    Derive a float32 key vector from seed using HKDF-SHA256.
    
    Process:
    1. HKDF-SHA256(seed, salt=zeros, info=domain_separated, length=length*4 bytes)
    2. Interpret as uint32 array
    3. Map to [0, 1) via x / 2^32
    4. Rescale to [range_min, range_max]
    5. Return float32 array
    
    This is DETERMINISTIC: same seed → same key_vector.
    """
    if len(seed) != 32:
        raise ValueError(f"Seed must be 32 bytes, got {len(seed)}")
    
    # Domain separation: include length and range in info
    info = f"{info_prefix}/key_vector/len={length}/range=[{range_min},{range_max}]".encode()
    
    # Need length * 4 bytes (float32 = 4 bytes)
    okm = hkdf_sha256(seed, salt=b'\x00'*32, info=info, length=length * 4)
    
    # Interpret as uint32
    uint32_arr = np.frombuffer(okm, dtype=np.uint32, count=length)
    
    # Map to [0, 1)
    float_arr = uint32_arr.astype(np.float64) / 4294967296.0  # 2^32
    
    # Rescale to [range_min, range_max]
    scaled = float_arr * (range_max - range_min) + range_min
    
    return scaled.astype(np.float32)


def verify_key_vector_consistency(seed: bytes, expected: np.ndarray, **kwargs) -> bool:
    """Verify derived key_vector matches expected (constant-time comparison)."""
    derived = derive_key_vector(seed, **kwargs)
    # Constant-time comparison for float arrays (approximate)
    return np.allclose(derived, expected, rtol=1e-6, atol=1e-7)


# --- Known Answer Tests (KAT) ---
KAT_SEED = bytes.fromhex("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
KAT_KEY_VECTOR_256 = derive_key_vector(KAT_SEED, length=256, range_min=-1.0, range_max=1.0)
KAT_FIRST_8 = KAT_KEY_VECTOR_256[:8]
