# phase5_backend/backend/dependencies.py
"""
Common FastAPI Dependencies.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .services.audit_service import AuditService, get_audit_service
from .services.he_service import he_service, HEService
from .services.keystore_service import keystore_service, KeystoreService

async def get_he_service() -> HEService:
    return he_service

async def get_keystore_service() -> KeystoreService:
    return keystore_service
