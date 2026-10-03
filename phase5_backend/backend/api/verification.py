# phase5_backend/backend/api/verification.py
"""
POST /verify/challenge - Get nonce for session
POST /verify - Verify encrypted probe against enrolled template
"""
import base64
import secrets
from typing import Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature

from ..database import get_db
from ..models import User, Enrollment, NonceStore, KeyStatus
from ..schemas import (
    ChallengeRequest, ChallengeResponse,
    VerifyRequest, VerifyResponse,
    ErrorResponse,
)
from ..services.he_service import he_service
from ..services.keystore_service import keystore_service
from ..services.audit_service import AuditService, get_audit_service
from ..security.rate_limit import rate_limit_dependency
from ..config import get_settings

router = APIRouter(prefix="/verify", tags=["verification"])


@router.post(
    "/challenge",
    response_model=ChallengeResponse,
    responses={404: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
@router.post(
    "/challenge/",
    response_model=ChallengeResponse,
    responses={404: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def verify_challenge(
    challenge_data: ChallengeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
):
    """
    Issue a cryptographic nonce for verification session.
    """
    await rate_limit_dependency(request, get_settings().rate_limit.challenge_per_minute)
    
    user_query = select(User).where(User.user_id == challenge_data.user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    
    if not user:
        user = User(user_id=challenge_data.user_id)
        db.add(user)
        await db.flush()
    
    nonce_bytes = secrets.token_bytes(32)
    nonce_b64 = base64.b64encode(nonce_bytes).decode()
    
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=300)
    nonce_store = NonceStore(
        nonce=nonce_b64,
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(nonce_store)
    
    await audit.log_event(
        event_type="challenge_issued",
        event_data={"user_id": challenge_data.user_id, "nonce": nonce_b64[:16] + "..."},
        user_id=challenge_data.user_id,
    )
    
    return ChallengeResponse(
        nonce=nonce_b64,
        expires_in_seconds=300,
    )


@router.post(
    "",
    response_model=VerifyResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
@router.post(
    "/",
    response_model=VerifyResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def verify(
    verify_data: VerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
):
    """
    Verify encrypted probe template against enrolled template.
    """
    await rate_limit_dependency(request, get_settings().rate_limit.verify_per_minute)
    settings = get_settings()
    
    nonce_query = select(NonceStore).where(
        NonceStore.nonce == verify_data.nonce,
        NonceStore.used == False,
        NonceStore.expires_at > datetime.now(timezone.utc),
    )
    nonce_result = await db.execute(nonce_query)
    nonce_store = nonce_result.scalar_one_or_none()
    
    if not nonce_store:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired nonce",
        )
    
    user_query = select(User).where(User.user_id == verify_data.user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    enroll_query = select(Enrollment).where(
        Enrollment.user_id == user.id,
        Enrollment.key_status == KeyStatus.ACTIVE,
    )
    if verify_data.key_version:
        enroll_query = enroll_query.where(Enrollment.key_version == verify_data.key_version)
    
    enroll_result = await db.execute(enroll_query.order_by(Enrollment.key_version.desc()))
    enrollment = enroll_result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active enrollment for specified key version",
        )
    
    nonce_store.used = True
    nonce_store.used_at = datetime.now(timezone.utc)
    
    try:
        enrolled_ct = enrollment.encrypted_template
        similarity = he_service.verify_similarity(
            base64.b64encode(enrolled_ct).decode(),
            verify_data.encrypted_probe,
        )
    except Exception as e:
        await audit.log_event(
            event_type="verification_he_error",
            event_data={"user_id": verify_data.user_id, "error": str(e)},
            user_id=verify_data.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"HE computation failed: {str(e)}",
        )
    
    threshold = 0.3
    verified = similarity >= threshold
    
    session_token = None
    expires_at = None
    if verified:
        from jose import jwt
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=settings.session.token_ttl_seconds)
        session_token = jwt.encode(
            {
                "sub": verify_data.user_id,
                "key_version": enrollment.key_version,
                "iat": now,
                "exp": expires_at,
                "iss": settings.session.issuer,
                "aud": settings.session.audience,
            },
            "session-secret-change-in-production",
            algorithm="HS256",
        )
    
    await audit.log_event(
        event_type="verification_attempt",
        event_data={
            "user_id": verify_data.user_id,
            "key_version": enrollment.key_version,
            "verified": verified,
            "similarity": round(similarity, 4),
            "threshold": threshold,
        },
        user_id=verify_data.user_id,
    )
    
    return VerifyResponse(
        verified=verified,
        similarity_score=round(similarity, 4),
        threshold=threshold,
        key_version=enrollment.key_version,
        session_token=session_token,
        expires_at=expires_at,
    )


# --- Compute & Finalize Endpoints for Android StrongBox / TEE Integration ---

from pydantic import BaseModel
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature


class ComputeRequest(BaseModel):
    user_id: str
    encrypted_probe: str  # base64 CKKS ciphertext
    nonce: str            # base64 nonce
    key_version: int


class ComputeResponse(BaseModel):
    success: bool
    encrypted_score: Optional[str] = None  # base64 CKKS ciphertext
    error: Optional[str] = None


class FinalRequest(BaseModel):
    user_id: str
    nonce: str
    signature: str          # base64 ECDSA signature
    signed_payload: str     # base64 signed payload
    key_version: int


class FinalResponse(BaseModel):
    success: bool
    verified: bool
    similarity_score: Optional[float] = None
    session_token: Optional[str] = None
    error: Optional[str] = None


@router.post("/compute", response_model=ComputeResponse)
async def compute_similarity(
    request: Request,
    compute_data: ComputeRequest,
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
):
    """
    Server-side HE computation: Enc(enrolled) · Enc(probe) → Enc(score)
    
    Client sends: encrypted_probe + nonce
    Server returns: Enc(score) for client TEE to decrypt
    """
    await rate_limit_dependency(request, get_settings().rate_limit.verify_per_minute)
    
    # 1. Validate nonce (must match challenge)
    nonce_query = select(NonceStore).where(
        NonceStore.nonce == compute_data.nonce,
        NonceStore.used == False,
        NonceStore.expires_at > datetime.now(timezone.utc),
    )
    nonce_result = await db.execute(nonce_query)
    nonce_store = nonce_result.scalar_one_or_none()
    
    if not nonce_store:
        raise HTTPException(401, "Invalid or expired nonce")
    
    # 2. Get enrollment
    user_query = select(User).where(User.user_id == compute_data.user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(404, "User not found")
    
    enroll_query = select(Enrollment).where(
        Enrollment.user_id == user.id,
        Enrollment.key_version == compute_data.key_version,
        Enrollment.key_status == KeyStatus.ACTIVE,
    )
    enroll_result = await db.execute(enroll_query)
    enrollment = enroll_result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(404, "No active enrollment for key version")
    
    # 3. Compute HE similarity
    try:
        enrolled_ct = enrollment.encrypted_template
        enc_score = he_service.compute_encrypted_similarity(
            base64.b64encode(enrolled_ct).decode(),
            compute_data.encrypted_probe
        )
        
        return ComputeResponse(
            success=True,
            encrypted_score=base64.b64encode(enc_score).decode() if isinstance(enc_score, bytes) else str(enc_score)
        )
    except Exception as e:
        await audit.log_event(
            event_type="he_compute_failed",
            event_data={"user_id": compute_data.user_id, "error": str(e)},
            user_id=compute_data.user_id,
        )
        raise HTTPException(400, f"HE computation failed: {e}")


@router.post("/finalize", response_model=FinalResponse)
async def finalize_verification(
    request: Request,
    final_data: FinalRequest,
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
):
    """
    Final verification: Client submits TEE signature.
    Server verifies signature, checks payload, issues session token.
    """
    await rate_limit_dependency(request, get_settings().rate_limit.verify_per_minute)
    
    # 1. Validate nonce (must be same, unused)
    nonce_query = select(NonceStore).where(
        NonceStore.nonce == final_data.nonce,
        NonceStore.used == False,
        NonceStore.expires_at > datetime.now(timezone.utc),
    )
    nonce_result = await db.execute(nonce_query)
    nonce_store = nonce_result.scalar_one_or_none()
    
    if not nonce_store:
        raise HTTPException(401, "Invalid or expired nonce")
    
    # 2. Get enrollment for device public key
    user_query = select(User).where(User.user_id == final_data.user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(404, "User not found")
    
    enroll_query = select(Enrollment).where(
        Enrollment.user_id == user.id,
        Enrollment.key_version == final_data.key_version,
        Enrollment.key_status == KeyStatus.ACTIVE,
    )
    enroll_result = await db.execute(enroll_query)
    enrollment = enroll_result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(404, "No active enrollment")
    
    # 3. Verify TEE signature
    try:
        device_pub_pem = enrollment.device_public_key
        if not device_pub_pem:
            raise HTTPException(400, "Device public key not found for enrollment")
            
        device_public_key = serialization.load_pem_public_key(device_pub_pem.encode())
        
        signature = base64.b64decode(final_data.signature)
        signed_payload = base64.b64decode(final_data.signed_payload)
        
        device_public_key.verify(
            signature,
            signed_payload,
            ec.ECDSA(hashes.SHA256())
        )
    except InvalidSignature:
        await audit.log_event(
            event_type="verification_signature_invalid",
            event_data={"user_id": final_data.user_id},
            user_id=final_data.user_id,
        )
        raise HTTPException(401, "Invalid TEE signature")
    except Exception as e:
        raise HTTPException(400, f"Signature verification failed: {e}")
    
    # 4. Parse and validate signed payload
    try:
        payload_data = parse_signed_payload(base64.b64decode(final_data.signed_payload))
        
        if payload_data['nonce'] != base64.b64decode(final_data.nonce):
            raise HTTPException(401, "Nonce mismatch in payload")
        
        if payload_data['key_version'] != final_data.key_version:
            raise HTTPException(401, "Key version mismatch in payload")
        
        if not payload_data['verified']:
            raise HTTPException(401, "TEE verified flag false")
        
        similarity_score = payload_data['similarity_score']
        threshold = 0.3
        
        if similarity_score < threshold:
            raise HTTPException(401, f"Similarity {similarity_score} below threshold")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Payload validation failed: {e}")
    
    # 5. Mark nonce as used
    nonce_store.used = True
    nonce_store.used_at = datetime.now(timezone.utc)
    
    # 6. Issue session token
    from jose import jwt
    now = datetime.now(timezone.utc)
    settings = get_settings()
    expires_at = now + timedelta(seconds=settings.session.token_ttl_seconds)
    session_token = jwt.encode(
        {
            "sub": final_data.user_id,
            "key_version": final_data.key_version,
            "similarity": similarity_score,
            "iat": now,
            "exp": expires_at,
            "iss": settings.session.issuer,
            "aud": settings.session.audience,
        },
        "session-secret-change-in-production",
        algorithm="HS256",
    )
    
    # 7. Audit log
    await audit.log_event(
        event_type="verification_success",
        event_data={
            "user_id": final_data.user_id,
            "key_version": final_data.key_version,
            "similarity": similarity_score,
            "threshold": threshold,
        },
        user_id=final_data.user_id,
    )
    
    return FinalResponse(
        success=True,
        verified=True,
        similarity_score=similarity_score,
        session_token=session_token,
        error=None,
    )


def parse_signed_payload(payload: bytes) -> dict:
    """Parse the canonical signed payload format."""
    import struct
    offset = 0
    
    nonce = payload[offset:offset+32]
    offset += 32
    
    similarity_score = struct.unpack('>d', payload[offset:offset+8])[0]
    offset += 8
    
    key_version = struct.unpack('>I', payload[offset:offset+4])[0]
    offset += 4
    
    device_id_len = struct.unpack('>H', payload[offset:offset+2])[0]
    offset += 2
    
    device_id = payload[offset:offset+device_id_len].decode('utf-8')
    offset += device_id_len
    
    timestamp_str = payload[offset:-1].decode('utf-8')
    timestamp = datetime.fromisoformat(timestamp_str)
    
    verified = bool(payload[-1])
    
    return {
        'nonce': nonce,
        'similarity_score': similarity_score,
        'key_version': key_version,
        'device_id': device_id,
        'timestamp': timestamp,
        'verified': verified,
    }
