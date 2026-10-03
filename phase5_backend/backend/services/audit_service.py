# phase5_backend/backend/services/audit_service.py
"""
Tamper-Evident Audit Logging.
Hash-chained audit log stored in database.
"""
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models import AuditLog, User
from ..database import get_db


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log_event(
        self,
        event_type: str,
        event_data: dict,
        user_id: Optional[str] = None,
    ) -> AuditLog:
        """Create tamper-evident audit entry."""
        prev_hash = await self._get_latest_hash(user_id)
        
        event_json = json.dumps(event_data, sort_keys=True, default=str)
        timestamp = datetime.now(timezone.utc).isoformat()
        
        this_hash = AuditLog.compute_hash(prev_hash, event_type, event_json, timestamp)
        
        entry = AuditLog(
            user_id=user_id,
            event_type=event_type,
            event_data=event_json,
            prev_hash=prev_hash,
            this_hash=this_hash,
        )
        
        self.db.add(entry)
        await self.db.flush()
        return entry
    
    async def _get_latest_hash(self, user_id: Optional[str]) -> Optional[str]:
        """Get hash of most recent audit entry for user (or global)."""
        query = select(AuditLog.this_hash).order_by(AuditLog.timestamp.desc()).limit(1)
        if user_id:
            user_query = select(User.id).where(User.user_id == user_id)
            user_result = await self.db.execute(user_query)
            user_uuid = user_result.scalar_one_or_none()
            if user_uuid:
                query = query.where(AuditLog.user_id == user_uuid)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def verify_chain(self, user_id: Optional[str] = None) -> Tuple[bool, List[str]]:
        """Verify hash chain integrity."""
        query = select(AuditLog).order_by(AuditLog.timestamp.asc())
        if user_id:
            user_query = select(User.id).where(User.user_id == user_id)
            user_result = await self.db.execute(user_query)
            user_uuid = user_result.scalar_one_or_none()
            if user_uuid:
                query = query.where(AuditLog.user_id == user_uuid)
        
        result = await self.db.execute(query)
        entries = result.scalars().all()
        
        errors = []
        prev_hash = None
        
        for entry in entries:
            event_json = entry.event_data
            timestamp = entry.timestamp.isoformat()
            expected_hash = AuditLog.compute_hash(
                prev_hash, entry.event_type, event_json, timestamp
            )
            
            if entry.prev_hash != prev_hash:
                errors.append(f"Entry {entry.id}: prev_hash mismatch")
            if entry.this_hash != expected_hash:
                errors.append(f"Entry {entry.id}: hash chain broken")
            
            prev_hash = entry.this_hash
        
        return len(errors) == 0, errors


from fastapi import Depends

def get_audit_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    """FastAPI dependency reusing endpoint DB session."""
    return AuditService(db)
