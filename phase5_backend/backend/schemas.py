# phase5_backend/backend/schemas.py
"""
Pydantic Request/Response Models.
Compatible with both snake_case and camelCase (for Android/Retrofit/Gson).
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from pydantic.alias_generators import to_camel
import base64


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


# --- Enrollment ---

class EnrollRequest(BaseSchema):
    user_id: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9._-]+$")
    encrypted_template: str = Field(..., description="Base64 encoded CKKS ciphertext")
    client_pk_he: str = Field(..., description="Base64 encoded client HE public key")
    key_version: int = Field(..., ge=1)
    
    # Attestation fields
    attestation_cert_chain: List[str] = Field(default_factory=list, description="PEM certificate chain (leaf first)")
    attestation_challenge: Optional[str] = Field(None, description="Base64 challenge sent during enrollment prep")
    
    @field_validator("encrypted_template", "client_pk_he", mode="before")
    @classmethod
    def validate_base64(cls, v: str) -> str:
        try:
            base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError("Invalid base64 encoding")
        return v


class EnrollResponse(BaseSchema):
    user_id: str
    key_version: int
    enrolled_at: datetime
    message: str = "Enrollment successful"
    userId: Optional[str] = None
    keyVersion: Optional[int] = None
    enrolledAt: Optional[str] = None

    @model_validator(mode="after")
    def populate_dual_casing(self):
        if not self.userId:
            self.userId = self.user_id
        if self.keyVersion is None:
            self.keyVersion = self.key_version
        if self.enrolledAt is None and self.enrolled_at:
            self.enrolledAt = self.enrolled_at.isoformat()
        return self


# --- Verification ---

class ChallengeRequest(BaseSchema):
    user_id: str = Field(..., min_length=1, max_length=255)


class ChallengeResponse(BaseSchema):
    success: bool = True
    nonce: str = Field(..., description="Base64 encoded random nonce")
    expires_in_seconds: int = 300
    expiresInSeconds: Optional[int] = None

    @model_validator(mode="after")
    def populate_dual_casing(self):
        if self.expiresInSeconds is None:
            self.expiresInSeconds = self.expires_in_seconds
        return self


class VerifyRequest(BaseSchema):
    user_id: str = Field(..., min_length=1, max_length=255)
    nonce: str = Field(..., description="Base64 encoded nonce from challenge")
    encrypted_probe: str = Field(..., description="Base64 encoded CKKS ciphertext of probe template")
    key_version: Optional[int] = Field(None, description="Specific key version to verify against")


class VerifyResponse(BaseSchema):
    verified: bool
    similarity_score: float = Field(..., ge=-1.0, le=1.0)
    threshold: float
    key_version: int
    session_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    similarityScore: Optional[float] = None
    keyVersion: Optional[int] = None
    sessionToken: Optional[str] = None
    expiresAt: Optional[str] = None

    @model_validator(mode="after")
    def populate_dual_casing(self):
        if self.similarityScore is None:
            self.similarityScore = self.similarity_score
        if self.keyVersion is None:
            self.keyVersion = self.key_version
        if self.sessionToken is None:
            self.sessionToken = self.session_token
        if self.expiresAt is None and self.expires_at:
            self.expiresAt = self.expires_at.isoformat()
        return self


# --- Health ---

class HealthResponse(BaseSchema):
    status: str = "healthy"
    timestamp: datetime
    version: str
    database: str
    redis: str
    he_keys_loaded: bool


# --- Admin ---

class KeyRotateRequest(BaseSchema):
    user_id: str
    reason: str = Field(default="user_requested", min_length=1, max_length=255)
    attestation_cert_chain: List[str] = Field(default_factory=list, description="PEM certificate chain for new key")
    attestation_challenge: Optional[str] = Field(None, description="Base64 attestation challenge")


class KeyRotateResponse(BaseSchema):
    success: bool = True
    user_id: Optional[str] = None
    old_version: int
    new_version: int
    rotated_at: datetime
    error: Optional[str] = None
    userId: Optional[str] = None
    oldVersion: Optional[int] = None
    newVersion: Optional[int] = None
    rotatedAt: Optional[str] = None

    @model_validator(mode="after")
    def populate_dual_casing(self):
        if not self.userId and self.user_id:
            self.userId = self.user_id
        if self.oldVersion is None:
            self.oldVersion = self.old_version
        if self.newVersion is None:
            self.newVersion = self.new_version
        if self.rotatedAt is None and self.rotated_at:
            self.rotatedAt = self.rotated_at.isoformat()
        return self


class AuditLogEntry(BaseSchema):
    id: str
    user_id: Optional[str]
    event_type: str
    event_data: Dict[str, Any]
    prev_hash: Optional[str]
    this_hash: str
    timestamp: datetime


# --- Error ---

class ErrorResponse(BaseSchema):
    error: str
    error_code: str
    details: Optional[Dict[str, Any]] = None
