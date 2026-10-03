# phase5_backend/backend/models.py
"""
SQLAlchemy ORM Models.

Security properties:
- NO plaintext biometric data stored
- Encrypted templates stored as BYTEA / BLOB
- Key versioning for revocation
- Audit trail with hash chaining
"""
import enum
from datetime import datetime, timezone
from typing import Optional
import hashlib
import json

from sqlalchemy import (
    String, LargeBinary, DateTime, Integer, ForeignKey, 
    Index, UniqueConstraint, Text, Boolean, Enum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase
import uuid


class Base(DeclarativeBase):
    pass


class KeyStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Enrollment(Base):
    __tablename__ = "enrollments"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    key_status: Mapped[KeyStatus] = mapped_column(Enum(KeyStatus), default=KeyStatus.ACTIVE, nullable=False)
    
    # HE Encrypted template (CKKS ciphertext)
    encrypted_template: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    # Client HE public key (for verification)
    client_pk_he: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Device attestation fields
    device_public_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attestation_cert_chain: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attestation_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="enrollments")
    
    __table_args__ = (
        UniqueConstraint("user_id", "key_version", name="uq_user_key_version"),
        Index("ix_enrollments_user_version", "user_id", "key_version"),
        Index("ix_enrollments_status", "key_status"),
    )


class AuditLog(Base):
    """
    Tamper-evident audit log.
    Each entry includes hash of previous entry (hash chain).
    """
    __tablename__ = "audit_logs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON serialized string
    
    # Hash chain for tamper evidence
    prev_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    this_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")
    
    def __init__(self, **kwargs):
        if "timestamp" not in kwargs or kwargs["timestamp"] is None:
            kwargs["timestamp"] = datetime.now(timezone.utc)
        super().__init__(**kwargs)

    @classmethod
    def compute_hash(cls, prev_hash: Optional[str], event_type: str, event_data: str, timestamp: str) -> str:
        """Compute SHA256 hash for audit entry."""
        content = f"{prev_hash or ''}|{event_type}|{event_data}|{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()


class NonceStore(Base):
    """Server-side nonce storage for challenge-response."""
    __tablename__ = "nonces"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nonce: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        Index("ix_nonces_expires", "expires_at"),
    )
