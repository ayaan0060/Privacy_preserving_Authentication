# phase4_he/he/crypto.py
"""
Core CKKS Cryptographic Operations.

- Key generation (via ContextManager)
- Encryption: plaintext vector → CKKS ciphertext
- Decryption: ciphertext → plaintext vector
- Encoding: real vector → CKKS plaintext (batching)
"""
import numpy as np
import tenseal as ts
from typing import List, Union
from pathlib import Path

from .context import HEContextManager, get_context_sizes
from .params import CKKSParams, DEFAULT_PARAMS


class HEClient:
    """
    Client-side HE operations.
    Holds secret key → can encrypt templates and decrypt similarity scores.
    """
    
    def __init__(self, key_dir: Union[str, Path], params: CKKSParams = DEFAULT_PARAMS):
        self.manager = HEContextManager(key_dir, params)
        self.context = self.manager.load_client_secret()
        self.embedding_dim = params.max_slots  # 4096, but we use 256
    
    def encrypt_template(self, template: np.ndarray) -> bytes:
        """
        Encrypt fused template t (256-dim, L2-normalized, [-1,1]).
        
        Returns: serialized ciphertext (bytes)
        """
        if template.shape != (256,):
            raise ValueError(f"Template must be (256,), got {template.shape}")
        if template.dtype != np.float32 and template.dtype != np.float64:
            template = template.astype(np.float64)
        
        plaintext = template.astype(np.float64)
        ckks_vector = ts.ckks_vector(self.context, plaintext)
        return ckks_vector.serialize()
    
    def encrypt_batch(self, templates: np.ndarray) -> List[bytes]:
        """Encrypt multiple templates (N, 256) → list of ciphertexts."""
        return [self.encrypt_template(t) for t in templates]
    
    def decrypt_score(self, ciphertext_bytes: bytes) -> float:
        """
        Decrypt homomorphic similarity score.
        
        Returns: single float (cosine similarity in [-1, 1])
        """
        ckks_vector = ts.ckks_vector_from(self.context, ciphertext_bytes)
        decrypted = ckks_vector.decrypt()
        
        # Result is in first slot (real part)
        score = float(decrypted[0].real) if hasattr(decrypted[0], 'real') else float(decrypted[0])
        return score
    
    def decrypt_vector(self, ciphertext_bytes: bytes, length: int = 256) -> np.ndarray:
        """Decrypt full vector (for debugging)."""
        ckks_vector = ts.ckks_vector_from(self.context, ciphertext_bytes)
        decrypted = ckks_vector.decrypt()
        return np.array([c.real if hasattr(c, 'real') else c for c in decrypted[:length]], dtype=np.float32)


class HEServer:
    """
    Server-side HE operations.
    ONLY has public context → can compute on ciphertexts, CANNOT decrypt.
    """
    
    def __init__(self, key_dir: Union[str, Path], params: CKKSParams = DEFAULT_PARAMS):
        self.manager = HEContextManager(key_dir, params)
        self.context = self.manager.load_server_public()
        
        self.manager.load_galois_keys(self.context)
        self.manager.load_relin_keys(self.context)
    
    def deserialize_ciphertext(self, ciphertext_bytes: bytes) -> ts.CKKSVector:
        """Deserialize ciphertext from bytes."""
        return ts.ckks_vector_from(self.context, ciphertext_bytes)
    
    def serialize_ciphertext(self, ckks_vector: ts.CKKSVector) -> bytes:
        """Serialize ciphertext to bytes."""
        return ckks_vector.serialize()


def generate_he_keys(key_dir: Union[str, Path], params: CKKSParams = DEFAULT_PARAMS, force: bool = False):
    """One-time key generation."""
    manager = HEContextManager(key_dir, params)
    return manager.generate_keys(force=force)


def get_he_context_sizes(key_dir: Union[str, Path]) -> dict:
    """Get serialized key sizes."""
    manager = HEContextManager(key_dir)
    context = manager.load_client_secret()
    return get_context_sizes(context)
