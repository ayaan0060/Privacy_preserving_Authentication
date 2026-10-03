# phase4_he/he/client.py
"""
Client API: Enrollment & Verification Flow.

CLIENT TRUST BOUNDARY:
- Generates/holds HE secret key
- Encrypts fused template t
- Decrypts similarity score
- NEVER sends plaintext biometric or template
"""
import numpy as np
from typing import Tuple, Union
from pathlib import Path

from .crypto import HEClient
from .params import CKKSParams, DEFAULT_PARAMS


class BiometricHEClient:
    """
    High-level client for cancelable biometric authentication.
    
    Flow:
    1. enroll(fused_template) → encrypted_template, public_key
    2. verify(encrypted_template, probe_fused_template) → similarity_score
    """
    
    def __init__(self, key_dir: Union[str, Path] = "./exports/he_keys", 
                 params: CKKSParams = DEFAULT_PARAMS):
        self.client = HEClient(key_dir, params)
        self.key_dir = Path(key_dir)
    
    def enroll(self, fused_template: np.ndarray) -> Tuple[bytes, bytes]:
        """
        Enrollment: encrypt fused template for server storage.
        
        Returns:
            (encrypted_template_bytes, client_public_key_bytes)
        """
        encrypted = self.client.encrypt_template(fused_template)
        public_key = self.key_dir.joinpath("client_public.key").read_bytes()
        return encrypted, public_key
    
    def verify(self, enrolled_ct_bytes: bytes, probe_fused_template: np.ndarray) -> float:
        """
        Verification: encrypt probe, send to server, decrypt result.
        """
        probe_ct = self.client.encrypt_template(probe_fused_template)
        
        from .compute import HESimilarityServer
        server = HESimilarityServer(self.key_dir)
        result_ct = server.compute_similarity(enrolled_ct_bytes, probe_ct)
        
        similarity = self.client.decrypt_score(result_ct)
        return similarity
    
    def get_public_key(self) -> bytes:
        """Get client public key for server."""
        return self.key_dir.joinpath("client_public.key").read_bytes()
