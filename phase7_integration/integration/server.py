# phase7_integration/integration/server.py
"""
Production Server Integration.
Wires FastAPI backend with all pipeline components.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog
import sys, os

phase_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for p in ["phase1_encoder", "phase2_keymgmt", "phase3_fusion", "phase4_he", "phase5_backend", "phase6_tee"]:
    path = os.path.join(phase_root, p)
    if path not in sys.path:
        sys.path.insert(0, path)

from backend.main import create_app as create_backend_app
from backend.config import get_settings
from backend.database import db_manager
from integration.pipeline import BiometricPipeline, PipelineConfig


@asynccontextmanager
async def integrated_lifespan(app: FastAPI):
    """Extended lifespan with pipeline initialization."""
    settings = get_settings()
    logger = structlog.get_logger()
    
    await db_manager.initialize()
    logger.info("Database initialized")
    
    from backend.security.rate_limit import rate_limiter
    await rate_limiter.initialize()
    logger.info("Rate limiter initialized")
    
    pipeline_config = PipelineConfig(
        encoder_path=Path(settings.encoder.model_path) if hasattr(settings, 'encoder') else Path("./exports/encoder.onnx"),
        film_path=Path(settings.film.model_path) if hasattr(settings, 'film') else Path("./exports/film.onnx"),
        he_key_dir=Path(settings.he.key_dir),
        keystore_dir=Path(settings.keystore.storage_dir),
        device_key_dir=Path(settings.tee.device_keys_dir),
        threshold=settings.tee.key_release.similarity_threshold,
    )
    
    app.state.pipeline = BiometricPipeline(pipeline_config)
    logger.info("Biometric pipeline initialized")
    
    yield
    
    app.state.pipeline.close()
    await rate_limiter.close()
    await db_manager.close()
    logger.info("Shutdown complete")


def create_integrated_app() -> FastAPI:
    """Create FastAPI app with full pipeline integration."""
    app = create_backend_app()
    app.router.lifespan_context = integrated_lifespan
    
    from pydantic import BaseModel
    from typing import Optional
    
    class FingerprintImage(BaseModel):
        image_b64: str
    
    class EnrollRequest(BaseModel):
        user_id: str
        fingerprint: FingerprintImage
        key_version: Optional[int] = None
    
    class VerifyRequest(BaseModel):
        user_id: str
        fingerprint: FingerprintImage
        key_version: Optional[int] = None
    
    class RotateRequest(BaseModel):
        user_id: str
        reason: str = "user_requested"
    
    @app.post("/integrated/enroll")
    async def integrated_enroll(request: EnrollRequest):
        """Enroll via integrated pipeline."""
        import base64
        import numpy as np
        import cv2
        
        img_data = base64.b64decode(request.fingerprint.image_b64)
        nparr = np.frombuffer(img_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        pipeline: BiometricPipeline = app.state.pipeline
        result = await pipeline.enroll(request.user_id, image, request.key_version)
        
        return {
            "user_id": result.user_id,
            "key_version": result.key_version,
            "latency_ms": result.latency_ms,
        }
    
    @app.post("/integrated/verify")
    async def integrated_verify(request: VerifyRequest):
        """Verify via integrated pipeline."""
        import base64
        import numpy as np
        import cv2
        
        img_data = base64.b64decode(request.fingerprint.image_b64)
        nparr = np.frombuffer(img_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        pipeline: BiometricPipeline = app.state.pipeline
        result = await pipeline.verify(request.user_id, image, request.key_version)
        
        return {
            "verified": result.verified,
            "similarity_score": result.similarity_score,
            "key_version": result.key_version,
            "session_token": result.session_token,
            "latency_ms": result.latency_ms,
            "key_release_valid": result.key_release_valid,
        }
    
    @app.post("/integrated/rotate")
    async def integrated_rotate(request: RotateRequest):
        """Rotate key via integrated pipeline."""
        pipeline: BiometricPipeline = app.state.pipeline
        new_version = await pipeline.keystore.rotate_key(request.user_id, request.reason)
        pipeline.secure_context.revoke_key_version(new_version - 1)
        pipeline.secure_context.set_active_key_version(new_version)
        
        return {
            "user_id": request.user_id,
            "new_key_version": new_version,
            "reason": request.reason,
        }
    
    return app
