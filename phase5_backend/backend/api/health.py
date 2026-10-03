# phase5_backend/backend/api/health.py
"""
Health & Readiness Endpoints.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..database import get_db, db_manager
from ..services.he_service import he_service
from ..services.keystore_service import keystore_service
from ..schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Liveness probe - service is running."""
    db_healthy = await db_manager.health_check()
    
    redis_healthy = True
    try:
        from ..security.rate_limit import rate_limiter
        if rate_limiter.redis_client:
            await rate_limiter.redis_client.ping()
    except Exception:
        redis_healthy = False
    
    he_loaded = True
    try:
        he_service._get_client()
        he_service._get_server()
    except Exception:
        he_loaded = False
    
    return HealthResponse(
        status="healthy" if all([db_healthy, redis_healthy, he_loaded]) else "degraded",
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
        database="connected" if db_healthy else "disconnected",
        redis="connected" if redis_healthy else "disconnected",
        he_keys_loaded=he_loaded,
    )


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness probe - service can handle requests."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return {"ready": False, "reason": "database unavailable"}
    
    if not keystore_service.health_check():
        return {"ready": False, "reason": "keystore unavailable"}
    
    return {"ready": True}
