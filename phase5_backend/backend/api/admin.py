# phase5_backend/backend/api/admin.py
"""
Admin Endpoints: Key rotation, audit, stats.
Protected by admin API key.
"""
from datetime import datetime, timezone
import json
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from ..database import get_db
from ..models import User, Enrollment, AuditLog, KeyStatus
from ..schemas import KeyRotateRequest, KeyRotateResponse, AuditLogEntry
from ..services.keystore_service import keystore_service
from ..services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_API_KEY = "change-me-in-production"


async def verify_admin_key(x_admin_key: str = Header(...)):
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


import base64
from ..schemas import KeyRotateRequest, KeyRotateResponse, AuditLogEntry, EnrollRequest, EnrollResponse
from ..services.android_attestation_verifier import AndroidAttestationVerifier


@router.post("/keys/rotate", response_model=KeyRotateResponse, dependencies=[Depends(verify_admin_key)])
async def rotate_key(
    request: KeyRotateRequest,
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
):
    """
    Key rotation with optional attestation verification for new key.
    """
    attest_pub_key = None
    if request.attestation_cert_chain and request.attestation_challenge:
        attestation_verifier = AndroidAttestationVerifier(expected_package_name="com.cancelablebio.auth")
        expected_challenge = base64.b64decode(request.attestation_challenge)
        attest_result = attestation_verifier.verify(
            request.attestation_cert_chain,
            expected_challenge
        )
        if not attest_result.valid:
            raise HTTPException(status_code=400, detail=f"New key attestation failed: {attest_result.error}")
        attest_pub_key = attest_result.public_key_pem

    user_query = select(User).where(User.user_id == request.user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    enroll_query = select(Enrollment).where(
        Enrollment.user_id == user.id,
        Enrollment.key_status == KeyStatus.ACTIVE,
    ).order_by(Enrollment.key_version.desc())
    enroll_result = await db.execute(enroll_query)
    current_enrollment = enroll_result.scalar_one_or_none()
    
    old_version = current_enrollment.key_version if current_enrollment else 0
    
    new_version_obj = keystore_service.rotate_key(request.user_id, request.reason)
    new_version = new_version_obj.version
    
    if current_enrollment:
        current_enrollment.key_status = KeyStatus.REVOKED
        current_enrollment.revoked_at = datetime.now(timezone.utc)
        current_enrollment.revoked_reason = request.reason
    
    await audit.log_event(
        event_type="key_rotated",
        event_data={
            "user_id": request.user_id,
            "old_version": old_version,
            "new_version": new_version,
            "reason": request.reason,
            "new_device_public_key": (attest_pub_key[:50] + "...") if attest_pub_key else None,
        },
        user_id=request.user_id,
    )
    
    return KeyRotateResponse(
        success=True,
        user_id=request.user_id,
        old_version=old_version,
        new_version=new_version,
        rotated_at=datetime.now(timezone.utc),
        error=None,
    )


@router.post("/keys/rotate/complete", response_model=EnrollResponse, dependencies=[Depends(verify_admin_key)])
async def complete_rotation_enrollment(
    enrollment_data: EnrollRequest,
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
):
    """
    Complete rotation by enrolling with new key version.
    """
    if enrollment_data.key_version <= 1:
        raise HTTPException(status_code=400, detail="Use regular /enroll for initial enrollment")
    
    active_version = keystore_service.get_active_version(enrollment_data.user_id)
    if active_version != enrollment_data.key_version:
        raise HTTPException(status_code=400, detail=f"Key version {enrollment_data.key_version} not active in keystore")
    
    user_query = select(User).where(User.user_id == enrollment_data.user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    from .enrollment import enroll
    from fastapi import Request
    # We can delegate to enroll logic or create the enrollment directly
    enrollment = Enrollment(
        user_id=user.id,
        key_version=enrollment_data.key_version,
        key_status=KeyStatus.ACTIVE,
        encrypted_template=base64.b64decode(enrollment_data.encrypted_template),
        client_pk_he=base64.b64decode(enrollment_data.client_pk_he),
    )
    db.add(enrollment)
    await db.flush()
    
    await audit.log_event(
        event_type="rotation_enrollment_completed",
        event_data={
            "user_id": enrollment_data.user_id,
            "key_version": enrollment_data.key_version,
        },
        user_id=enrollment_data.user_id,
    )
    
    return EnrollResponse(
        user_id=enrollment_data.user_id,
        key_version=enrollment_data.key_version,
        enrolled_at=enrollment.created_at,
    )


@router.get("/audit", response_model=list[AuditLogEntry], dependencies=[Depends(verify_admin_key)])
async def get_audit_logs(
    user_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve audit logs with optional filters."""
    query = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
    
    if user_id:
        user_query = select(User.id).where(User.user_id == user_id)
        user_result = await db.execute(user_query)
        user_uuid = user_result.scalar_one_or_none()
        if user_uuid:
            query = query.where(AuditLog.user_id == user_uuid)
    
    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        AuditLogEntry(
            id=str(log.id),
            user_id=user_id,
            event_type=log.event_type,
            event_data=json.loads(log.event_data) if isinstance(log.event_data, str) else log.event_data,
            prev_hash=log.prev_hash,
            this_hash=log.this_hash,
            timestamp=log.timestamp,
        )
        for log in logs
    ]


@router.get("/stats", dependencies=[Depends(verify_admin_key)])
async def get_stats(db: AsyncSession = Depends(get_db)):
    """System statistics."""
    users_count = await db.scalar(select(func.count(User.id)))
    enrollments_count = await db.scalar(select(func.count(Enrollment.id)))
    active_enrollments = await db.scalar(
        select(func.count(Enrollment.id)).where(Enrollment.key_status == KeyStatus.ACTIVE)
    )
    revoked_enrollments = await db.scalar(
        select(func.count(Enrollment.id)).where(Enrollment.key_status == KeyStatus.REVOKED)
    )
    audit_count = await db.scalar(select(func.count(AuditLog.id)))
    
    return {
        "users": users_count,
        "total_enrollments": enrollments_count,
        "active_enrollments": active_enrollments,
        "revoked_enrollments": revoked_enrollments,
        "audit_entries": audit_count,
    }
