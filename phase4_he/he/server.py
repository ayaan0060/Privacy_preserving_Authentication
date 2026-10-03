# phase4_he/he/server.py
"""
Server API: Homomorphic Similarity Computation.

SERVER TRUST BOUNDARY:
- Holds ONLY public key (cannot decrypt)
- Stores encrypted templates
- Computes similarity on ciphertexts
- Returns encrypted score
"""
import numpy as np
from typing import List, Tuple, Union, Dict
from pathlib import Path

from .crypto import HEServer
from .compute import HESimilarityServer
from .params import CKKSParams, DEFAULT_PARAMS


class BiometricHEServer:
    """
    High-level server for homomorphic verification.
    
    Database schema (per user):
    - user_id
    - enrolled_ct: BLOB (encrypted template)
    - pk_he: BLOB (client public key)
    - key_version: int
    """
    
    def __init__(self, key_dir: Union[str, Path] = "./exports/he_keys",
                 params: CKKSParams = DEFAULT_PARAMS):
        self.server = HESimilarityServer(key_dir, params)
        self.key_dir = Path(key_dir)
        self._storage: Dict[str, dict] = {}
    
    def store_enrollment(self, user_id: str, enrolled_ct_bytes: bytes, 
                         pk_he_bytes: bytes, key_version: int):
        """Store encrypted template (simulates DB write)."""
        self._storage[user_id] = {
            "enrolled_ct": enrolled_ct_bytes,
            "pk_he": pk_he_bytes,
            "key_version": key_version,
        }
    
    def get_enrollment(self, user_id: str) -> dict:
        """Retrieve enrollment (simulates DB read)."""
        if user_id not in self._storage:
            raise KeyError(f"No enrollment for user {user_id}")
        return self._storage[user_id]
    
    def compute_verification(self, user_id: str, probe_ct_bytes: bytes) -> bytes:
        """
        Compute homomorphic similarity: Enc(enrolled) · Enc(probe) → Enc(score).
        
        Returns encrypted similarity score (client decrypts).
        """
        enrollment = self.get_enrollment(user_id)
        enrolled_ct = enrollment["enrolled_ct"]
        
        result_ct = self.server.compute_similarity(enrolled_ct, probe_ct_bytes)
        return result_ct
    
    def compute_verification_batch(self, user_id: str, 
                                    probe_ct_batch: List[bytes]) -> List[bytes]:
        """Batch verification against one enrolled template."""
        enrollment = self.get_enrollment(user_id)
        enrolled_ct = enrollment["enrolled_ct"]
        
        return self.server.compute_similarity_batch(enrolled_ct, probe_ct_batch)
