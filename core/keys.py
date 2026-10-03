# core/keys.py
"""
Cryptographically secure key derivation and pseudorandom matrix generation
for cancelable biometric template protection.

Architecture:
- Master seed (256-bit entropy)
- HKDF-SHA256 (RFC 5869) with domain separation: info = f"{user_id}|v{version}"
- CSPRNG DRBG: AES-256-CTR keystream
- Box-Muller transformation for exact Gaussian sampling
- QR decomposition with Mezzadri (2007) sign correction for Haar-distributed orthogonal matrices
"""

from typing import Tuple
import numpy as np
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def derive_hkdf_bytes(master_seed: bytes, user_id: str, version: int, length: int) -> bytes:
    """Derives deterministic pseudorandom bytes using HKDF-SHA256."""
    info = f"{user_id}|v{version}".encode('utf-8')
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=None,
        info=info
    )
    return hkdf.derive(master_seed)


class CryptoDRBG:
    """CSPRNG stream generator based on AES-256-CTR keyed by HKDF output."""
    def __init__(self, key_bytes: bytes):
        if len(key_bytes) != 32:
            raise ValueError(f"AES-256 requires a 32-byte key, got {len(key_bytes)} bytes.")
        nonce = b'\x00' * 16
        cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce))
        self.encryptor = cipher.encryptor()

    def get_bytes(self, n: int) -> bytes:
        return self.encryptor.update(b'\x00' * n)

    def get_uniform_floats(self, n: int) -> np.ndarray:
        """Returns n float64 values uniformly distributed in (0, 1)."""
        raw_bytes = self.get_bytes(n * 8)
        u_ints = np.frombuffer(raw_bytes, dtype=np.uint64)
        # Map uint64 to strictly open interval (0, 1)
        return (u_ints.astype(np.float64) + 1.0) / (float(2**64) + 2.0)

    def get_gaussian_floats(self, n: int) -> np.ndarray:
        """Returns n standard normal N(0, 1) float32 values via Box-Muller transform."""
        n_pairs = (n + 1) // 2
        u = self.get_uniform_floats(n_pairs * 2)
        u1 = u[0::2]
        u2 = u[1::2]
        r = np.sqrt(-2.0 * np.log(u1))
        theta = 2.0 * np.pi * u2
        z1 = r * np.cos(theta)
        z2 = r * np.sin(theta)
        res = np.empty(n_pairs * 2, dtype=np.float32)
        res[0::2] = z1.astype(np.float32)
        res[1::2] = z2.astype(np.float32)
        return res[:n]


def derive_haar_matrix(master_seed: bytes, user_id: str, version: int, dim: int = 256) -> np.ndarray:
    """
    Generates a Haar-distributed orthogonal matrix Q in O(dim) using QR decomposition
    with Mezzadri (2007) diagonal sign correction.
    """
    key_bytes = derive_hkdf_bytes(master_seed, user_id, version, 32)
    drbg = CryptoDRBG(key_bytes)
    g_floats = drbg.get_gaussian_floats(dim * dim)
    G = g_floats.reshape(dim, dim)
    
    Q, R = np.linalg.qr(G)
    # Mezzadri sign correction: multiply column i by sign(R[i, i])
    d = np.diag(R)
    ph = np.sign(d)
    ph[ph == 0] = 1.0
    Q = Q * ph
    Q = Q.astype(np.float32)
    
    # Assert strict numerical isometry
    diff = np.max(np.abs(Q.T @ Q - np.eye(dim, dtype=np.float32)))
    if diff > 1e-5:
        raise ValueError(f"Orthogonality check failed: max |Q^T Q - I| = {diff:.2e} > 1e-5")
    return Q


def derive_film_key(master_seed: bytes, user_id: str, version: int, dim: int = 256) -> np.ndarray:
    """Derives a continuous key vector k in [-1.0, 1.0]^dim for FiLM conditioning."""
    key_bytes = derive_hkdf_bytes(master_seed, user_id, version, 32)
    drbg = CryptoDRBG(key_bytes)
    u = drbg.get_uniform_floats(dim)
    # Map (0, 1) -> [-1.0, 1.0]
    k = (u * 2.0 - 1.0).astype(np.float32)
    return k


def derive_bipolar_signs(master_seed: bytes, user_id: str, version: int, dim: int = 256) -> np.ndarray:
    """Derives discrete sign vector s in {-1.0, +1.0}^dim."""
    k = derive_film_key(master_seed, user_id, version, dim)
    signs = np.where(k >= 0.0, 1.0, -1.0).astype(np.float32)
    return signs


def derive_permutation(master_seed: bytes, user_id: str, version: int, dim: int = 256) -> np.ndarray:
    """Derives a pseudorandom permutation of indices {0, ..., dim-1} via Fisher-Yates."""
    key_bytes = derive_hkdf_bytes(master_seed, user_id, version, 32)
    drbg = CryptoDRBG(key_bytes)
    perm = np.arange(dim, dtype=np.int64)
    # Fisher-Yates shuffle
    u = drbg.get_uniform_floats(dim)
    for i in range(dim - 1, 0, -1):
        j = int(np.floor(u[i] * (i + 1)))
        perm[i], perm[j] = perm[j], perm[i]
    return perm


def derive_iom_matrices(
    master_seed: bytes,
    user_id: str,
    version: int,
    num_groups: int = 64,
    group_size: int = 8,
    dim: int = 256
) -> np.ndarray:
    """
    Derives Gaussian projection weights for Index-of-Max (IoM) hashing.
    Returns: array of shape (num_groups, group_size, dim) with standard normal weights.
    """
    key_bytes = derive_hkdf_bytes(master_seed, user_id, version, 32)
    drbg = CryptoDRBG(key_bytes)
    total_weights = num_groups * group_size * dim
    w_floats = drbg.get_gaussian_floats(total_weights)
    return w_floats.reshape(num_groups, group_size, dim)
