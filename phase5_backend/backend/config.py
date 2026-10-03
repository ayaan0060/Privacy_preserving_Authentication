# phase5_backend/backend/config.py
"""
Pydantic Settings Management.
All configuration via YAML + environment variables.
Environment variables take precedence (12-factor app).
"""
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union, Any
import yaml

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TLSSettings(BaseSettings):
    enabled: bool = True
    cert_file: str = "./certs/server.crt"
    key_file: str = "./certs/server.key"
    ca_file: Optional[str] = None
    client_verify: bool = False
    min_version: str = "TLSv1.3"
    ciphers: str = "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256"


class DatabaseSettings(BaseSettings):
    url: str = "sqlite+aiosqlite:///./storage/backend.sqlite"
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30
    echo: bool = False


class RedisSettings(BaseSettings):
    url: str = "redis://localhost:6379/0"
    max_connections: int = 50


class RateLimitSettings(BaseSettings):
    enroll_per_minute: int = 5
    verify_per_minute: int = 30
    challenge_per_minute: int = 60
    burst_multiplier: int = 2


class SessionSettings(BaseSettings):
    token_ttl_seconds: int = 3600
    refresh_ttl_seconds: int = 86400
    issuer: str = "cancelable-bio-auth"
    audience: str = "bioauth-client"


class HESettings(BaseSettings):
    key_dir: str = "./exports/he_keys"
    poly_modulus_degree: int = 8192
    security_level: int = 128


class KeystoreSettings(BaseSettings):
    storage_dir: str = "./keystore_data"
    master_key_env: str = "KEYSTORE_MASTER_KEY"


class AuditSettings(BaseSettings):
    enabled: bool = True
    log_file: str = "./logs/audit.log"
    max_size_mb: int = 100
    backup_count: int = 10
    hash_chain: bool = True


class PIISettings(BaseSettings):
    filter_logs: bool = True
    redact_fields: List[str] = [
        "template", "ciphertext", "key_vector", "seed", 
        "biometric", "fingerprint"
    ]
    redact_patterns: List[str] = [
        "BEGIN.*KEY",
    ]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8443
    workers: int = 4
    timeout: int = 30
    keepalive: int = 5
    
    # Nested settings
    tls: TLSSettings = Field(default_factory=TLSSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    he: HESettings = Field(default_factory=HESettings)
    keystore: KeystoreSettings = Field(default_factory=KeystoreSettings)
    audit: AuditSettings = Field(default_factory=AuditSettings)
    pii: PIISettings = Field(default_factory=PIISettings)
    
    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Settings":
        """Load from YAML file, then apply env overrides."""
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p, "r") as f:
            data = yaml.safe_load(f) or {}
        
        flat = {}
        for key, value in data.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    flat[f"{key}__{k}"] = v
            else:
                flat[key] = value
        
        return cls(**flat)


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    import os
    config_path = os.getenv("CONFIG_PATH", "./config.yaml")
    return Settings.from_yaml(config_path)
