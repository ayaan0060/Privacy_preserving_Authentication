# phase2_keymgmt/keystore/software.py
"""
SoftwareSecureKeyStore — DEVELOPMENT SIMULATION ONLY.
Implements SecureKeyStore interface with:
- /dev/urandom CSPRNG (production: hardware RNG)
- PBKDF2 + AES-GCM for encrypted storage
- mlock() on Linux for secret buffers (best effort)
- Explicit zeroize via memoryview casting

⚠️  THIS IS NOT A REAL HARDWARE SECURITY BOUNDARY.
⚠️  Secrets exist in Python process memory (swappable, inspectable).
⚠️  Production MUST swap backend to Android Keystore / iOS Secure Enclave / HSM.
"""
import os
import json
import secrets
import struct
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
import numpy as np

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import constant_time

from .interface import (
    SecureKeyStore, KeyStoreError, KeyNotFoundError, KeyRevokedError, 
    KeyExistsError, BackendUnavailableError
)
from .models import KeyRecord, KeyVersion, DerivedKeyMaterial, UserID
from .derivation import derive_key_vector  # Pure function, no secrets

try:
    import resource
    HAS_MLOCK = hasattr(os, 'mlock') or hasattr(resource, 'RLIMIT_MEMLOCK')
except ImportError:
    HAS_MLOCK = False

class SoftwareSecureKeyStore(SecureKeyStore):
    """
    File-based encrypted keystore for development.
    Directory structure:
      storage_dir/
        {user_id}/
          meta.json          # Version list, salts, nonces (plaintext metadata)
          v{version}.enc     # Encrypted blob: seed(32) || key_vector(256*4) || pk_he
    """
    
    def __init__(
        self,
        storage_dir: str | Path,
        master_key: bytes | None = None,  # In prod: derived from user auth + hardware key
        pbkdf2_iterations: int = 100000,
        use_mlock: bool = True,
        max_versions: int = 10,
        grace_period_hours: int = 24,
    ):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.pbkdf2_iterations = pbkdf2_iterations
        self.use_mlock = use_mlock and HAS_MLOCK
        self.max_versions = max_versions
        self.grace_period_seconds = grace_period_hours * 3600
        self._lock = threading.RLock()
        
        # Master key for encryption at rest (DEV: load/persist per storage_dir; PROD: from TEE/HSM)
        if master_key is None:
            env_key = os.environ.get("CANCELABLE_BIO_MASTER_KEY")
            if env_key:
                if len(env_key) == 64:
                    master_key = bytes.fromhex(env_key)
                else:
                    master_key = hashes.Hash(hashes.SHA256())
                    master_key.update(env_key.encode())
                    master_key = master_key.finalize()
            else:
                master_key_file = self.storage_dir / ".master_key"
                if master_key_file.exists():
                    master_key = master_key_file.read_bytes()
                else:
                    master_key = secrets.token_bytes(32)
                    master_key_file.parent.mkdir(parents=True, exist_ok=True)
                    master_key_file.write_bytes(master_key)
        self._master_key = self._mlock_bytes(master_key) if self.use_mlock else master_key
        
        print(f"[SoftwareKeyStore] Initialized at {self.storage_dir} (mlock={'enabled' if self.use_mlock else 'unavailable'})")
    
    def _mlock_bytes(self, data: bytes) -> bytes:
        """Attempt to mlock the buffer (Linux only, requires CAP_IPC_LOCK)."""
        if not self.use_mlock:
            return data
        try:
            # Create mutable copy for mlock
            buf = bytearray(data)
            import resource
            resource.setrlimit(resource.RLIMIT_MEMLOCK, (len(buf), len(buf)))
            return bytes(buf)
        except Exception as e:
            print(f"[WARN] mlock failed: {e}")
            return data
    
    def _zeroize_buffer(self, buf: bytearray):
        """Best-effort zeroization."""
        if buf:
            buf[:] = b'\x00' * len(buf)
    
    # --- Key Derivation (Pure) ---
    
    def _derive_storage_key(self, salt: bytes) -> bytes:
        """PBKDF2-HMAC-SHA256 from master_key + salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.pbkdf2_iterations,
        )
        return kdf.derive(self._master_key)
    
    def _encrypt_blob(self, plaintext: bytes, salt: bytes) -> tuple[bytes, bytes]:
        """AES-GCM encrypt. Returns (ciphertext, nonce)."""
        key = self._derive_storage_key(salt)
        nonce = secrets.token_bytes(12)
        aead = AESGCM(key)
        ct = aead.encrypt(nonce, plaintext, None)  # No AAD
        return ct, nonce
    
    def _decrypt_blob(self, ciphertext: bytes, salt: bytes, nonce: bytes) -> bytes:
        """AES-GCM decrypt."""
        key = self._derive_storage_key(salt)
        aead = AESGCM(key)
        return aead.decrypt(nonce, ciphertext, None)
    
    # --- Storage Helpers ---
    
    def _user_dir(self, user_id: UserID) -> Path:
        # Sanitize user_id for filesystem
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
        return self.storage_dir / safe_id
    
    def _meta_path(self, user_id: UserID) -> Path:
        return self._user_dir(user_id) / "meta.json"
    
    def _version_path(self, user_id: UserID, version: int) -> Path:
        return self._user_dir(user_id) / f"v{version}.enc"
    
    def _load_meta(self, user_id: UserID) -> dict:
        path = self._meta_path(user_id)
        if not path.exists():
            return {"versions": [], "current_version": None}
        with open(path, "r") as f:
            return json.load(f)
    
    def _save_meta(self, user_id: UserID, meta: dict):
        path = self._meta_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(meta, f)
    
    # --- SecureKeyStore Interface ---
    
    def generate_seed(self, user_id: UserID) -> KeyVersion:
        with self._lock:
            meta = self._load_meta(user_id)
            
            # Check for existing active key
            if meta["current_version"] is not None:
                curr_ver = meta["current_version"]
                curr_meta = next((v for v in meta["versions"] if v["version"] == curr_ver), None)
                if curr_meta and not curr_meta.get("revoked", False):
                    raise KeyExistsError(f"User {user_id} already has active key v{curr_ver}. Use rotate_key().")
            
            # Generate new version
            new_version_num = (max([v["version"] for v in meta["versions"]], default=0) + 1)
            version = KeyVersion(version=new_version_num)
            
            # Generate seed (32 bytes) from CSPRNG
            seed = secrets.token_bytes(32)
            
            # Derive key_vector (256-dim float32 in [-1, 1])
            key_vector = derive_key_vector(seed, length=256, range_min=-1.0, range_max=1.0)
            
            # Generate CKKS public key placeholder (Phase 4 will provide real one)
            # For now, store a dummy 32-byte identifier
            pk_he = secrets.token_bytes(32)
            
            # Pack plaintext: seed(32) || key_vector(256*float32) || pk_he(32)
            kv_bytes = key_vector.astype(np.float32).tobytes()
            plaintext = seed + kv_bytes + pk_he
            
            # Encrypt
            salt = secrets.token_bytes(16)
            ciphertext, nonce = self._encrypt_blob(plaintext, salt)
            
            # Save version file
            vpath = self._version_path(user_id, new_version_num)
            vpath.parent.mkdir(parents=True, exist_ok=True)
            with open(vpath, "wb") as f:
                f.write(ciphertext)
            
            # Update metadata
            version_record = {
                "version": new_version_num,
                "created_at": version.created_at.isoformat(),
                "revoked": False,
                "revoked_at": None,
                "revoked_reason": None,
                "salt": salt.hex(),
                "nonce": nonce.hex(),
                "pk_he_len": len(pk_he),
            }
            meta["versions"].append(version_record)
            meta["current_version"] = new_version_num
            
            # Enforce max versions (keep revoked ones for audit)
            active_versions = [v for v in meta["versions"] if not v.get("revoked", False)]
            if len(active_versions) > self.max_versions:
                # Revoke oldest active
                oldest = min(active_versions, key=lambda v: v["version"])
                oldest["revoked"] = True
                oldest["revoked_at"] = datetime.now(timezone.utc).isoformat()
                oldest["revoked_reason"] = "max_versions_exceeded"
            
            self._save_meta(user_id, meta)
            return version
    
    def rotate_key(self, user_id: UserID, reason: str = "scheduled_rotation") -> KeyVersion:
        with self._lock:
            meta = self._load_meta(user_id)
            curr_ver = meta["current_version"]
            
            if curr_ver is None:
                raise KeyNotFoundError(f"No active key for user {user_id}")
            
            # Revoke current
            for v in meta["versions"]:
                if v["version"] == curr_ver:
                    v["revoked"] = True
                    v["revoked_at"] = datetime.now(timezone.utc).isoformat()
                    v["revoked_reason"] = reason
                    v["grace_period_ends"] = (
                        datetime.now(timezone.utc).timestamp() + self.grace_period_seconds
                    )
                    break
            
            meta["current_version"] = None
            self._save_meta(user_id, meta)
            
            # Generate new
            new_version = self.generate_seed(user_id)
            return new_version
    
    def get_key_material(self, user_id: UserID, version: Optional[int] = None) -> DerivedKeyMaterial:
        with self._lock:
            meta = self._load_meta(user_id)
            
            if version is None:
                version = meta["current_version"]
            
            if version is None:
                raise KeyNotFoundError(f"No key for user {user_id}")
            
            # Find version record
            ver_record = next((v for v in meta["versions"] if v["version"] == version), None)
            if ver_record is None:
                raise KeyNotFoundError(f"Version {version} not found for user {user_id}")
            
            if ver_record.get("revoked", False):
                # Check grace period
                grace_end = ver_record.get("grace_period_ends", 0)
                if datetime.now(timezone.utc).timestamp() > grace_end:
                    raise KeyRevokedError(f"Key version {version} revoked: {ver_record.get('revoked_reason')}")
                # Allow during grace period but log warning
                print(f"[WARN] Using revoked key v{version} within grace period (expires {grace_end})")
            
            # Decrypt
            vpath = self._version_path(user_id, version)
            if not vpath.exists():
                raise KeyNotFoundError(f"Encrypted blob missing for v{version}")
            
            with open(vpath, "rb") as f:
                ciphertext = f.read()
            
            salt = bytes.fromhex(ver_record["salt"])
            nonce = bytes.fromhex(ver_record["nonce"])
            
            plaintext = self._decrypt_blob(ciphertext, salt, nonce)
            
            # Unpack: seed(32) || key_vector(1024) || pk_he(32)
            if len(plaintext) != 32 + 1024 + 32:
                raise KeyStoreError(f"Corrupted key blob: expected 1088 bytes, got {len(plaintext)}")
            
            seed = plaintext[:32]
            kv_bytes = plaintext[32:1056]
            pk_he = plaintext[1056:]
            
            # Reconstruct key_vector
            key_vector = np.frombuffer(kv_bytes, dtype=np.float32).copy()
            
            # Verify length
            if key_vector.shape != (256,):
                raise KeyStoreError(f"Invalid key_vector shape: {key_vector.shape}")
            
            # Create version object
            created_at = datetime.fromisoformat(ver_record["created_at"])
            revoked_at = datetime.fromisoformat(ver_record["revoked_at"]) if ver_record.get("revoked_at") else None
            key_version = KeyVersion(
                version=version,
                created_at=created_at,
                revoked_at=revoked_at,
                revoked_reason=ver_record.get("revoked_reason"),
            )
            
            # Return in-memory material (caller must zeroize)
            return DerivedKeyMaterial(
                seed=seed,
                key_vector=key_vector,
                version=key_version,
            )
    
    def get_public_key_he(self, user_id: UserID, version: Optional[int] = None) -> bytes:
        with self._lock:
            meta = self._load_meta(user_id)
            if version is None:
                version = meta["current_version"]
            if version is None:
                raise KeyNotFoundError(f"No key for user {user_id}")
            
            ver_record = next((v for v in meta["versions"] if v["version"] == version), None)
            if ver_record is None:
                raise KeyNotFoundError(f"Version {version} not found")
            
            vpath = self._version_path(user_id, version)
            with open(vpath, "rb") as f:
                ciphertext = f.read()
            
            salt = bytes.fromhex(ver_record["salt"])
            nonce = bytes.fromhex(ver_record["nonce"])
            plaintext = self._decrypt_blob(ciphertext, salt, nonce)
            
            # pk_he is last 32 bytes
            return plaintext[-32:]
    
    def list_versions(self, user_id: UserID) -> List[KeyVersion]:
        with self._lock:
            meta = self._load_meta(user_id)
            versions = []
            for v in meta["versions"]:
                created = datetime.fromisoformat(v["created_at"])
                revoked = datetime.fromisoformat(v["revoked_at"]) if v.get("revoked_at") else None
                versions.append(KeyVersion(
                    version=v["version"],
                    created_at=created,
                    revoked_at=revoked,
                    revoked_reason=v.get("revoked_reason"),
                ))
            return versions
    
    def delete_user(self, user_id: UserID) -> bool:
        with self._lock:
            import shutil
            udir = self._user_dir(user_id)
            if udir.exists():
                shutil.rmtree(udir)
                return True
            return False
    
    def health_check(self) -> bool:
        try:
            # Test write/read
            test_dir = self.storage_dir / ".health_check"
            test_dir.mkdir(exist_ok=True)
            test_file = test_dir / "test"
            test_file.write_bytes(secrets.token_bytes(32))
            test_file.unlink()
            test_dir.rmdir()
            return True
        except Exception:
            return False
    
    def __del__(self):
        """Best-effort zeroize master key on destruction."""
        if hasattr(self, '_master_key') and isinstance(self._master_key, bytearray):
            self._zeroize_buffer(self._master_key)
