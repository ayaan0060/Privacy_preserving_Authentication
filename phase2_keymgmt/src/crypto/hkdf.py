# phase2_keymgmt/src/crypto/hkdf.py
"""
HKDF-SHA256 Key Derivation for Cancelable Biometrics.
Implements RFC 5869.
Derives a 256-dim float32 vector 'k' in [-1, 1] from 32-byte seed.
"""
import hashlib
import hmac
import struct
import math
import numpy as np
from typing import Tuple
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

# --- Constants ---
HKDF_HASH_ALG = hashes.SHA256()
BACKEND = default_backend()

def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    """HKDF-Extract: PRK = HMAC-Hash(salt, IKM)"""
    if salt is None:
        salt = b'\x00' * HKDF_HASH_ALG.digest_size
    return hmac.new(salt, ikm, hashlib.sha256).digest()

def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """HKDF-Expand: OKM = T(1) | T(2) | ... where T(i) = HMAC(PRK, T(i-1) | info | i)"""
    hash_len = HKDF_HASH_ALG.digest_size
    n = math.ceil(length / hash_len)
    if n > 255:
        raise ValueError("OKM length too large for HKDF (max 255 * HashLen)")
    
    okm = bytearray()
    t = b''
    for i in range(1, n + 1):
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm.extend(t)
    return bytes(okm[:length])

def derive_key_vector(
    seed: bytes, 
    domain_tag: str, 
    user_id: str, 
    key_version: int,
    dim: int = 256,
    dtype: str = "float32",
    target_range: Tuple[float, float] = (-1.0, 1.0)
) -> np.ndarray:
    """
    Derives the FiLM Key Vector 'k'.
    
    WHY THIS CONSTRUCTION?
    1. Domain Separation: `info` binds key to App, Component, User, Version.
       Changing ANY parameter yields unlinkable keys (Cancelability).
    2. HKDF-SHA256: Standard, NIST SP 800-56C approved, resistant to length extension.
    3. Rescaling: Encoder embeddings are L2-normalized (on unit hypersphere).
       FiLM Gamma/Beta prediction works best if 'k' matches the *distribution* of embeddings.
       Uniform [-1, 1] matches the dynamic range of normalized embeddings (which live in [-1, 1]).
    """
    # 1. Input Validation
    if len(seed) != 32:
        raise ValueError("Seed must be 32 bytes (256 bits)")
    
    # 2. Construct Info String (Domain Separation)
    info = f"{domain_tag}|{user_id}|{key_version}|FiLM_KeyVector".encode('utf-8')
    
    # 3. HKDF Extract (Salt=None -> zeros per RFC 5869)
    prk = hkdf_extract(salt=None, ikm=seed)
    
    # 4. HKDF Expand
    okm_len = dim * 4
    okm = hkdf_expand(prk, info, okm_len)
    
    # 5. Deserialize & Rescale
    fmt = f"<{dim}I" # Little-endian uint32 array
    uint_vals = struct.unpack(fmt, okm)
    
    # Convert to float32 in [0, 1)
    float_vals = [v / 4294967296.0 for v in uint_vals]
    
    # Scale to target_range [min, max]
    min_v, max_v = target_range
    scale = max_v - min_v
    rescaled = [(v * scale) + min_v for v in float_vals]
    
    return np.array(rescaled, dtype=np.float32)

def verify_derivation_deterministic(seed: bytes, params: dict, expected_k: np.ndarray, tol: float = 1e-6) -> bool:
    """Verifies derivation is pure function of inputs."""
    k = derive_key_vector(seed, **params)
    assert np.allclose(k, expected_k, atol=tol), "Derivation non-deterministic or mismatch"
    return True
