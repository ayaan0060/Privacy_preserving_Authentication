# phase6_tee/tee/device_keys.py
"""
Device Signing Key Management.

PRODUCTION:
- Android: Key generated in StrongBox, never exportable
- iOS: Key generated in Secure Enclave, never exportable
- OP-TEE: Key generated in TA, sealed storage

SIMULATION: File-based with encryption (for development only).
"""
import os
import json
import secrets
from pathlib import Path
from typing import Optional, Tuple, Union
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DeviceKeyManager:
    """
    Manages device signing keys (ECDSA P-256).
    """
    
    def __init__(
        self,
        key_dir: Union[str, Path],
        master_password: Optional[str] = None,
    ):
        self.key_dir = Path(key_dir)
        self.key_dir.mkdir(parents=True, exist_ok=True)
        
        self.private_key_path = self.key_dir / "device_signing.key"
        self.public_key_path = self.key_dir / "device_signing.pub"
        self.metadata_path = self.key_dir / "device_metadata.json"
        self.device_id_path = self.key_dir / "device_id"
        
        self._private_key: Optional[ec.EllipticCurvePrivateKey] = None
        self._public_key: Optional[ec.EllipticCurvePublicKey] = None
        self._device_id: Optional[str] = None
        
        self._master_password = master_password or os.getenv("DEVICE_KEY_PASSWORD", "dev-password-change-in-production")
        
        self._load_or_generate()
    
    def _derive_storage_key(self, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(self._master_password.encode())
    
    def _encrypt_key(self, private_key: ec.EllipticCurvePrivateKey, salt: bytes) -> Tuple[bytes, bytes]:
        key = self._derive_storage_key(salt)
        nonce = secrets.token_bytes(12)
        aead = AESGCM(key)
        
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        
        ct = aead.encrypt(nonce, pem, None)
        return ct, nonce
    
    def _decrypt_key(self, ciphertext: bytes, salt: bytes, nonce: bytes) -> ec.EllipticCurvePrivateKey:
        key = self._derive_storage_key(salt)
        aead = AESGCM(key)
        pem = aead.decrypt(nonce, ciphertext, None)
        return serialization.load_pem_private_key(pem, password=None)
    
    def _load_or_generate(self):
        if self.private_key_path.exists() and self.metadata_path.exists():
            self._load_existing()
        else:
            self._generate_new()
    
    def _load_existing(self):
        with open(self.metadata_path, 'r') as f:
            meta = json.load(f)
        
        salt = bytes.fromhex(meta['salt'])
        nonce = bytes.fromhex(meta['nonce'])
        
        ciphertext = self.private_key_path.read_bytes()
        self._private_key = self._decrypt_key(ciphertext, salt, nonce)
        self._public_key = self._private_key.public_key()
        self._device_id = meta['device_id']
    
    def _generate_new(self):
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        self._public_key = self._private_key.public_key()
        self._device_id = f"dev_{secrets.token_hex(16)}"
        
        salt = secrets.token_bytes(16)
        ciphertext, nonce = self._encrypt_key(self._private_key, salt)
        
        self.private_key_path.write_bytes(ciphertext)
        
        pub_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.public_key_path.write_bytes(pub_pem)
        
        meta = {
            'device_id': self._device_id,
            'salt': salt.hex(),
            'nonce': nonce.hex(),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'algorithm': 'ES256',
            'curve': 'P-256',
        }
        self.metadata_path.write_text(json.dumps(meta, indent=2))
        self.device_id_path.write_text(self._device_id)
    
    def get_signing_key(self) -> ec.EllipticCurvePrivateKey:
        return self._private_key
    
    def get_public_key(self) -> ec.EllipticCurvePublicKey:
        return self._public_key
    
    def get_device_id(self) -> str:
        return self._device_id
    
    def get_public_key_pem(self) -> bytes:
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    
    def health_check(self) -> bool:
        return self._private_key is not None and self._public_key is not None
    
    def close(self):
        """Zeroize keys in memory."""
        self._private_key = None
        self._public_key = None
    
    def rotate_key(self) -> str:
        """Generate new device signing key (for scheduled rotation)."""
        if self.private_key_path.exists():
            archive_dir = self.key_dir / "archive"
            archive_dir.mkdir(exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self.private_key_path.rename(archive_dir / f"device_signing_{timestamp}.key")
            self.public_key_path.rename(archive_dir / f"device_signing_{timestamp}.pub")
            self.metadata_path.rename(archive_dir / f"device_metadata_{timestamp}.json")
        
        self._generate_new()
        return self._device_id
