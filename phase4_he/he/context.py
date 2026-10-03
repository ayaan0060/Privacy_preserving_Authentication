# phase4_he/he/context.py
"""
TenSEAL Context Serialization & Management.

Key separation:
- CLIENT: Has secret key (decrypt), public key (encrypt), galois/relin keys
- SERVER: Has PUBLIC context ONLY (no secret key), galois/relin keys for compute

Serialization format: TenSEAL native (protobuf-based)
"""
import os
from pathlib import Path
from typing import Optional, Union, Dict
import tenseal as ts

from .params import CKKSParams, DEFAULT_PARAMS, create_tenseal_context, validate_params


class HEContextManager:
    """
    Manages HE context lifecycle: generation, serialization, loading.
    Enforces key separation: client gets secret key, server gets public only.
    """
    
    def __init__(self, key_dir: Union[str, Path], params: CKKSParams = DEFAULT_PARAMS):
        self.key_dir = Path(key_dir)
        self.key_dir.mkdir(parents=True, exist_ok=True)
        self.params = params
        valid, msg = validate_params(params)
        if not valid:
            raise ValueError(f"Invalid HE parameters: {msg}")
    
    # --- File paths ---
    @property
    def client_secret_path(self) -> Path:
        return self.key_dir / "client_secret.key"
    
    @property
    def client_public_path(self) -> Path:
        return self.key_dir / "client_public.key"
    
    @property
    def server_public_path(self) -> Path:
        return self.key_dir / "server_public.key"
    
    @property
    def galois_keys_path(self) -> Path:
        return self.key_dir / "galois.keys"
    
    @property
    def relin_keys_path(self) -> Path:
        return self.key_dir / "relin.keys"
    
    @property
    def params_path(self) -> Path:
        return self.key_dir / "params.yaml"
    
    # --- Generation ---
    
    def generate_keys(self, force: bool = False) -> dict:
        """Generate all keys and save to disk."""
        if not force and self.client_secret_path.exists():
            raise FileExistsError(f"Keys already exist at {self.key_dir}. Use force=True to overwrite.")
        
        print(f"[HE] Generating CKKS keys (N={self.params.poly_modulus_degree})...")
        
        # Full context with secret key
        context = create_tenseal_context(self.params, generate_galois_keys=True, generate_relin_keys=True)
        
        # Save client secret (full context)
        secret_bytes = context.serialize(
            save_secret_key=True,
            save_public_key=True,
            save_galois_keys=True,
            save_relin_keys=True,
        )
        self.client_secret_path.write_bytes(secret_bytes)
        print(f"  Client secret: {self.client_secret_path} ({len(secret_bytes)/1024:.1f} KB)")
        
        # Save client public (no secret key)
        public_context = context.copy()
        public_context.make_context_public()
        public_bytes = public_context.serialize(
            save_secret_key=False,
            save_public_key=True,
            save_galois_keys=True,
            save_relin_keys=True,
        )
        self.client_public_path.write_bytes(public_bytes)
        print(f"  Client public: {self.client_public_path} ({len(public_bytes)/1024:.1f} KB)")
        
        # Save server public (same as client public for CKKS)
        self.server_public_path.write_bytes(public_bytes)
        print(f"  Server public: {self.server_public_path} ({len(public_bytes)/1024:.1f} KB)")
        
        # Save galois/relin keys separately (for server loading)
        galois_bytes = context.serialize(save_secret_key=False, save_public_key=False, save_galois_keys=True, save_relin_keys=False)
        self.galois_keys_path.write_bytes(galois_bytes)
        
        relin_bytes = context.serialize(save_secret_key=False, save_public_key=False, save_galois_keys=False, save_relin_keys=True)
        self.relin_keys_path.write_bytes(relin_bytes)
        
        # Save params
        import yaml
        params_dict = {
            "poly_modulus_degree": self.params.poly_modulus_degree,
            "coeff_mod_bit_sizes": self.params.coeff_mod_bit_sizes,
            "scale_bits": self.params.scale_bits,
            "security_level": self.params.security_level,
            "std_dev": self.params.std_dev,
        }
        self.params_path.write_text(yaml.dump(params_dict))
        
        return {
            "client_secret": str(self.client_secret_path),
            "client_public": str(self.client_public_path),
            "server_public": str(self.server_public_path),
            "galois_keys": str(self.galois_keys_path),
            "relin_keys": str(self.relin_keys_path),
        }
    
    # --- Loading ---
    
    def load_client_secret(self) -> ts.Context:
        """Load FULL context with secret key (CLIENT ONLY)."""
        if not self.client_secret_path.exists():
            raise FileNotFoundError(f"Client secret key not found: {self.client_secret_path}")
        
        return ts.context_from(self.client_secret_path.read_bytes())
    
    def load_client_public(self) -> ts.Context:
        """Load public context (client encrypt, no decrypt)."""
        if not self.client_public_path.exists():
            raise FileNotFoundError(f"Client public key not found: {self.client_public_path}")
        return ts.context_from(self.client_public_path.read_bytes())
    
    def load_server_public(self) -> ts.Context:
        """Load public context for server (compute only)."""
        if not self.server_public_path.exists():
            raise FileNotFoundError(f"Server public key not found: {self.server_public_path}")
        return ts.context_from(self.server_public_path.read_bytes())
    
    def load_galois_keys(self, context: ts.Context) -> None:
        """Load galois keys into existing context (for server)."""
        pass
    
    def load_relin_keys(self, context: ts.Context) -> None:
        """Load relinearization keys into existing context."""
        pass


def get_context_sizes(context: ts.Context) -> dict:
    """Report serialized sizes for capacity planning."""
    secret = context.serialize(save_secret_key=True, save_public_key=True, 
                                save_galois_keys=True, save_relin_keys=True)
    public = context.serialize(save_secret_key=False, save_public_key=True,
                                save_galois_keys=True, save_relin_keys=True)
    galois = context.serialize(save_secret_key=False, save_public_key=False,
                               save_galois_keys=True, save_relin_keys=False)
    relin = context.serialize(save_secret_key=False, save_public_key=False,
                              save_galois_keys=False, save_relin_keys=True)
    
    return {
        "secret_key_mb": len(secret) / 1024 / 1024,
        "public_key_mb": len(public) / 1024 / 1024,
        "galois_keys_mb": len(galois) / 1024 / 1024,
        "relin_keys_mb": len(relin) / 1024 / 1024,
        "ciphertext_size_estimate_kb": len(public) / 1024,
    }
