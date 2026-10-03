# phase4_he/he/compute.py
"""
Server-Side Homomorphic Computation: Dot Product via CKKS.

ALGORITHM: Cosine Similarity = t1 · t2 (both L2-normalized, so dot = cosine)
Plaintext: sum_{i=0}^{255} t1[i] * t2[i]
"""
import tenseal as ts
import numpy as np
from typing import Tuple, List, Union
from pathlib import Path

from .context import HEContextManager
from .params import CKKSParams, DEFAULT_PARAMS


class HESimilarityServer:
    """
    Server-side similarity computation.
    Stateless: takes two ciphertexts, returns ciphertext of dot product.
    """
    
    def __init__(self, key_dir: Union[str, Path], params: CKKSParams = DEFAULT_PARAMS):
        self.manager = HEContextManager(key_dir, params)
        self.context = self.manager.load_server_public()
        self.manager.load_galois_keys(self.context)
        self.manager.load_relin_keys(self.context)
        self.embedding_dim = 256
    
    def compute_similarity(self, ct1_bytes: bytes, ct2_bytes: bytes) -> bytes:
        """
        Compute homomorphic dot product: Enc(t1) · Enc(t2) → Enc(similarity).
        """
        ct1 = ts.ckks_vector_from(self.context, ct1_bytes)
        ct2 = ts.ckks_vector_from(self.context, ct2_bytes)
        
        ct_result = ct1.dot(ct2)
        return ct_result.serialize()
    
    def compute_similarity_batch(self, 
                                  enrolled_bytes: bytes, 
                                  probe_batch_bytes: List[bytes]) -> List[bytes]:
        """
        Compute similarity of one enrolled template against multiple probes.
        """
        ct_enrolled = ts.ckks_vector_from(self.context, enrolled_bytes)
        results = []
        
        for probe_bytes in probe_batch_bytes:
            ct_probe = ts.ckks_vector_from(self.context, probe_bytes)
            ct_result = ct_enrolled.dot(ct_probe)
            results.append(ct_result.serialize())
        
        return results


def plaintext_dot_product(t1: np.ndarray, t2: np.ndarray) -> float:
    """Reference plaintext implementation for validation."""
    return float(np.dot(t1, t2))


def compute_similarity_plaintext(t1: np.ndarray, t2: np.ndarray) -> float:
    """Cosine similarity (templates already L2-normalized)."""
    return float(np.dot(t1, t2))
