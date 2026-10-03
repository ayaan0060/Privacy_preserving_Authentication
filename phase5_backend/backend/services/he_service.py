# phase5_backend/backend/services/he_service.py
"""
HE Service: Wrapper around Phase 4 HE operations.
Provides high-level enrollment/verification with error handling.
"""
import base64
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict
import sys, os

# Add Phase 4 to sys.path if available
phase4_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "phase4_he"))
if phase4_path not in sys.path:
    sys.path.insert(0, phase4_path)

from he.crypto import HEClient, HEServer, generate_he_keys
from he.compute import HESimilarityServer
from he.params import DEFAULT_PARAMS

from ..config import get_settings


class HEService:
    def __init__(self):
        self.settings = get_settings()
        self.key_dir = Path(self.settings.he.key_dir)
        self._client: Optional[HEClient] = None
        self._server: Optional[HESimilarityServer] = None
    
    def _get_client(self) -> HEClient:
        if self._client is None:
            if not (self.key_dir / "client_secret.key").exists():
                generate_he_keys(self.key_dir, DEFAULT_PARAMS)
            self._client = HEClient(self.key_dir, DEFAULT_PARAMS)
        return self._client
    
    def _get_server(self) -> HESimilarityServer:
        if self._server is None:
            if not (self.key_dir / "client_secret.key").exists():
                generate_he_keys(self.key_dir, DEFAULT_PARAMS)
            self._server = HESimilarityServer(self.key_dir, DEFAULT_PARAMS)
        return self._server
    
    def decrypt_template(self, ciphertext_b64: str) -> np.ndarray:
        """Decrypt full template (for debugging/admin only)."""
        client = self._get_client()
        ct_bytes = base64.b64decode(ciphertext_b64)
        return client.decrypt_vector(ct_bytes, length=256)
    
    def verify_similarity(
        self, 
        enrolled_ct_b64: str, 
        probe_ct_b64: str
    ) -> float:
        """
        Compute homomorphic similarity between enrolled and probe templates.
        Returns plaintext similarity score.
        """
        client = self._get_client()
        server = self._get_server()
        
        enrolled_ct = base64.b64decode(enrolled_ct_b64)
        probe_ct = base64.b64decode(probe_ct_b64)
        
        result_ct = server.compute_similarity(enrolled_ct, probe_ct)
        score = client.decrypt_score(result_ct)
        return score
    
    def compute_encrypted_similarity(
        self,
        enrolled_ct_b64: str,
        probe_ct_b64: str
    ) -> bytes:
        """
        Compute homomorphic similarity between enrolled and probe templates.
        Returns encrypted score ciphertext bytes without decrypting.
        """
        server = self._get_server()
        enrolled_ct = base64.b64decode(enrolled_ct_b64)
        probe_ct = base64.b64decode(probe_ct_b64)
        return server.compute_similarity(enrolled_ct, probe_ct)
    
    def get_key_sizes(self) -> Dict:
        """Get HE key sizes for monitoring."""
        from he.context import get_context_sizes
        client = self._get_client()
        return get_context_sizes(client.context)


he_service = HEService()
