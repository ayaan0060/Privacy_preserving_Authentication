# phase5_backend/backend/main.py
"""
FastAPI Application Factory.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import structlog
import logging

from .config import get_settings
from .database import db_manager, get_db
from .security.tls import create_ssl_context
from .security.pii_filter import setup_pii_logging, PIIRedactionMiddleware
from .security.rate_limit import rate_limiter
from .api import enrollment, verification, health, admin
from .services.audit_service import AuditService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    
    setup_pii_logging()
    logger = structlog.get_logger()
    
    logger.info("Starting Cancelable Biometric Auth Backend")
    
    await db_manager.initialize()
    await db_manager.create_tables()
    logger.info("Database initialized and tables created")
    
    await rate_limiter.initialize()
    logger.info("Rate limiter initialized")
    
    try:
        from .services.he_service import he_service
        he_service._get_client()
        he_service._get_server()
        logger.info("HE keys loaded")
    except Exception as e:
        logger.error("HE keys not available", error=str(e))
    
    from .services.keystore_service import keystore_service
    if not keystore_service.health_check():
        logger.warning("Keystore health check failed")
    
    def on_key_rotated(user_id: str, old_version: int, new_version: int):
        logger.info(f"Key rotated for {user_id}: v{old_version} → v{new_version}")
    
    keystore_service.add_rotation_callback(on_key_rotated)
    
    yield
    
    logger.info("Shutting down")
    await rate_limiter.close()
    await db_manager.close()


def create_app() -> FastAPI:
    settings = get_settings()
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    app = FastAPI(
        title="Cancelable Biometric Authentication API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.tls.enabled else None,
        redoc_url=None,
    )
    
    app.add_middleware(PIIRedactionMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*", "http://10.0.2.2", "http://10.0.2.2:8000", "http://10.0.2.2:8001", "http://10.0.2.2:8443", "http://localhost", "http://127.0.0.1"],
        allow_origin_regex=r".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger = structlog.get_logger()
        logger.error("Unhandled exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "error_code": "INTERNAL_ERROR"},
        )

    @app.get("/")
    async def root_summary():
        return {
            "name": "Cancelable Biometric Authentication API Backend",
            "status": "online",
            "version": "1.0.0",
            "documentation": "/docs",
            "endpoints": {
                "health_check": "GET /health",
                "readiness_probe": "GET /ready",
                "biometric_enrollment": "POST /enroll",
                "biometric_verification": "POST /verify",
                "admin_key_rotation": "POST /admin/rotate_key",
                "android_he_microservice": "http://0.0.0.0:8001"
            }
        }
    
    app.include_router(health.router)
    app.include_router(enrollment.router)
    app.include_router(verification.router)
    app.include_router(admin.router)
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    
    ssl_context = None
    if settings.tls.enabled:
        ssl_context = create_ssl_context()
    
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        ssl=ssl_context,
        log_config=None,
    )
