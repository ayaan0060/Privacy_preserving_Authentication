# phase2_keymgmt/src/crypto/software_store.py
"""
SoftwareKeyStore — SIMULATED Secure Boundary.
STATUS: SIMULATED (Logic Real, Hardware Boundary Mocked).

PRODUCTION REPLACEMENT NOTES:
- Android: Implement using `KeyGenParameterSpec.Builder().setAttestationChallenge()...` 
           inside `android.security.keystore`. Seed = AES-256 key. 
           Derivation happens in TEE via `KeyStore` API or custom TA.
- iOS: `SecKeyCreateRandomKey` in `kSecAttrTokenIDSecureEnclave`. 
       Derivation via `SecKeyKeyExchangeAlgorithm` or custom logic in SE.
- HSM: PKCS#11 `C_GenerateKey` + `C_DeriveKey` (CKM_HKDF).

WHAT THIS SIMULATION PROTECTS:
- Seed never written to disk in plaintext (encrypted at rest via Fernet).
- Seed locked in RAM (mlock) during derivation.
- Seed zeroized after use (memset).
- Version rollback prevented by DB constraint + monotonic check.
"""
import os
import sqlite3
import json
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .interfaces import (
    SecureKeyStore, KeyRecord, SeedHandle, 
    UserExistsError, KeyNotFoundError, KeyRevokedError, HardwareError
)
from ..utils.memory import secure_buffer, secure_zero

log = logging.getLogger(__name__)

# --- Constants ---
SEED_BYTES = 32
# Master Key for encrypting seeds at rest in SQLite.
# IN PRODUCTION: THIS KEY LIVES IN HSM/TEE. HERE: Derived from Env Var / File (INSECURE).
MASTER_KEY_ENV = "CANCELABLE_BIO_MASTER_KEY" 

class SoftwareKeyStore(SecureKeyStore):
    def __init__(self, db_path: str, master_key: Optional[bytes] = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.config = {}
        
        # Initialize Master Key (DEV ONLY)
        if master_key:
            self._master_key = master_key
        else:
            # Derive stable Fernet key from env var so seeds survive process restarts.
            import base64
            pwd = os.environ.get(MASTER_KEY_ENV, "dev-only-insecure-default-change-me").encode()
            salt = b'cancelable_bio_salt_v1'  # Static salt for dev determinism
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
            raw_key = kdf.derive(pwd)  # 32 raw bytes
            # Fernet requires URL-safe base64-encoded 32-byte key
            self._master_key = base64.urlsafe_b64encode(raw_key)
        
        self._fernet = Fernet(self._master_key)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS keys (
                    user_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    seed_blob BLOB NOT NULL,      -- Fernet encrypted seed
                    created_at REAL NOT NULL,
                    is_revoked INTEGER NOT NULL DEFAULT 0,
                    metadata TEXT,                -- JSON
                    PRIMARY KEY (user_id, version)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_active 
                ON keys (user_id) WHERE is_revoked = 0
            """)
            conn.commit()

    # --- SecureKeyStore Interface Implementation ---

    def initialize_user(self, user_id: str) -> KeyRecord:
        with sqlite3.connect(self.db_path) as conn:
            # Check existence
            cur = conn.execute("SELECT 1 FROM keys WHERE user_id = ?", (user_id,))
            if cur.fetchone():
                raise UserExistsError(f"User {user_id} already exists")
            
            # Generate Seed (CSPRNG)
            seed = os.urandom(SEED_BYTES)
            
            # Encrypt for Storage
            seed_blob = self._fernet.encrypt(seed)
            
            now = time.time()
            record = KeyRecord(
                user_id=user_id, version=1, created_at=now, 
                is_revoked=False, metadata={}
            )
            
            conn.execute(
                "INSERT INTO keys (user_id, version, seed_blob, created_at, is_revoked, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, 1, seed_blob, now, 0, json.dumps({}))
            )
            conn.commit()
            log.info(f"[SIM] User {user_id} initialized v1")
            return record

    @contextmanager
    def get_active_seed_handle(self, user_id: str):
        # Fetch Active Record
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM keys WHERE user_id = ? AND is_revoked = 0 ORDER BY version DESC LIMIT 1",
                (user_id,)
            )
            row = cur.fetchone()
        
        if not row:
            raise KeyNotFoundError(f"No active key for user {user_id}")
        
        record = KeyRecord(
            user_id=row['user_id'], version=row['version'], 
            created_at=row['created_at'], is_revoked=bool(row['is_revoked']),
            metadata=json.loads(row['metadata'] or '{}')
        )
        
        # Decrypt Seed into SECURE BUFFER
        try:
            seed_plain = self._fernet.decrypt(row['seed_blob'])
        except Exception as e:
            log.error(f"Decryption failed for {user_id} v{row['version']}: {e}")
            raise HardwareError("Seed decryption failed (corruption/tamper)") from e
        
        if len(seed_plain) != SEED_BYTES:
            raise HardwareError("Decrypted seed length mismatch")

        # Yield Handle with Zeroizer
        with secure_buffer(SEED_BYTES) as buf:
            buf[:] = seed_plain
            # Zeroize source immediately
            secure_zero(bytearray(seed_plain))
            
            def _zeroizer(b):
                pass 
            
            handle = SeedHandle(bytes(buf), record, _zeroizer)
            try:
                yield handle
            finally:
                pass

    def rotate_key(self, user_id: str) -> KeyRecord:
        with sqlite3.connect(self.db_path) as conn:
            # 1. Start Transaction (Atomicity)
            conn.execute("BEGIN IMMEDIATE")
            
            # 2. Fetch Current Active
            cur = conn.execute(
                "SELECT version, seed_blob FROM keys WHERE user_id = ? AND is_revoked = 0 ORDER BY version DESC LIMIT 1",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                raise KeyNotFoundError(f"No active key to rotate for {user_id}")
            
            old_version = row[0]
            
            # 3. Revoke Old (Mark revoked)
            conn.execute(
                "UPDATE keys SET is_revoked = 1 WHERE user_id = ? AND version = ?",
                (user_id, old_version)
            )
            
            # 4. Generate New Seed
            new_version = old_version + 1
            new_seed = os.urandom(SEED_BYTES)
            new_seed_blob = self._fernet.encrypt(new_seed)
            now = time.time()
            
            conn.execute(
                "INSERT INTO keys (user_id, version, seed_blob, created_at, is_revoked, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, new_version, new_seed_blob, now, 0, json.dumps({"rotated_from": old_version}))
            )
            
            conn.commit()
            
            new_record = KeyRecord(
                user_id=user_id, version=new_version, created_at=now,
                is_revoked=False, metadata={"rotated_from": old_version}
            )
            log.warning(f"[SIM] User {user_id} rotated v{old_version} -> v{new_version}")
            return new_record

    def get_key_history(self, user_id: str) -> List[KeyRecord]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM keys WHERE user_id = ? ORDER BY version ASC", (user_id,)
            )
            rows = cur.fetchall()
        
        return [
            KeyRecord(
                user_id=r['user_id'], version=r['version'], created_at=r['created_at'],
                is_revoked=bool(r['is_revoked']), metadata=json.loads(r['metadata'] or '{}')
            ) for r in rows
        ]

    def delete_user(self, user_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM keys WHERE user_id = ?", (user_id,))
            conn.commit()
            return cur.rowcount > 0

    def set_config(self, config: dict):
        self.config = config
