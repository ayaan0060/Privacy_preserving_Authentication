# phase5_backend/tests/test_database.py
import pytest
import uuid
import sys, os
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models import User, Enrollment, AuditLog, NonceStore, KeyStatus
from backend.database import db_manager
from backend.services.audit_service import AuditService

@pytest.fixture
async def db_session():
    await db_manager.initialize()
    await db_manager.create_tables()
    async with db_manager.session() as session:
        yield session
    await db_manager.close()

class TestDatabaseModels:
    @pytest.mark.asyncio
    async def test_user_creation(self, db_session: AsyncSession):
        user = User(user_id="test_user_db")
        db_session.add(user)
        await db_session.flush()
        
        assert user.id is not None
        assert user.user_id == "test_user_db"
        assert user.created_at is not None
        assert user.is_active is True
    
    @pytest.mark.asyncio
    async def test_enrollment_foreign_key(self, db_session: AsyncSession):
        user = User(user_id="fk_test")
        db_session.add(user)
        await db_session.flush()
        
        enrollment = Enrollment(
            user_id=user.id,
            key_version=1,
            key_status=KeyStatus.ACTIVE,
            encrypted_template=b"fake_ct",
            client_pk_he=b"fake_pk",
        )
        db_session.add(enrollment)
        await db_session.flush()
        
        assert enrollment.id is not None
        assert enrollment.user_id == user.id
    
    @pytest.mark.asyncio
    async def test_unique_user_key_version(self, db_session: AsyncSession):
        user = User(user_id="unique_test")
        db_session.add(user)
        await db_session.flush()
        
        e1 = Enrollment(user_id=user.id, key_version=1, key_status=KeyStatus.ACTIVE,
                        encrypted_template=b"ct1", client_pk_he=b"pk1")
        e2 = Enrollment(user_id=user.id, key_version=1, key_status=KeyStatus.ACTIVE,
                        encrypted_template=b"ct2", client_pk_he=b"pk2")
        db_session.add_all([e1, e2])
        
        with pytest.raises(Exception):
            await db_session.flush()
    
    @pytest.mark.asyncio
    async def test_audit_log_hash_chain(self, db_session: AsyncSession):
        user = User(user_id="audit_test")
        db_session.add(user)
        await db_session.flush()
        
        log1 = AuditLog(
            user_id=user.id,
            event_type="test_event",
            event_data='{"action": "first"}',
            prev_hash=None,
            this_hash=""
        )
        log1.this_hash = AuditLog.compute_hash(None, log1.event_type, log1.event_data, log1.timestamp.isoformat())
        db_session.add(log1)
        await db_session.flush()
        
        log2 = AuditLog(
            user_id=user.id,
            event_type="test_event",
            event_data='{"action": "second"}',
            prev_hash=log1.this_hash,
            this_hash=""
        )
        log2.this_hash = AuditLog.compute_hash(log1.this_hash, log2.event_type, log2.event_data, log2.timestamp.isoformat())
        db_session.add(log2)
        await db_session.flush()
        
        valid, errors = await AuditService(db_session).verify_chain("audit_test")
        assert valid is True
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_nonce_expiration(self, db_session: AsyncSession):
        user = User(user_id="nonce_test")
        db_session.add(user)
        await db_session.flush()
        
        expired_nonce = NonceStore(
            nonce="expired123",
            user_id=user.id,
            expires_at=datetime.now(timezone.utc),
        )
        db_session.add(expired_nonce)
        await db_session.flush()
        
        assert expired_nonce.expires_at <= datetime.now(timezone.utc)
