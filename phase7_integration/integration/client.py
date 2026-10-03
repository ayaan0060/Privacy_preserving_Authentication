# phase7_integration/integration/client.py
"""
High-Level Client API for Applications.
"""
import asyncio
import base64
import numpy as np
from pathlib import Path
from typing import Optional
import cv2

from .pipeline import BiometricPipeline, PipelineConfig, EnrollmentResult, VerificationResult


class BiometricAuthClient:
    """
    Application-facing client for cancelable biometric authentication.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        import yaml
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
        
        self.pipeline_config = PipelineConfig(
            encoder_path=Path(cfg['encoder']['model_path']),
            film_path=Path(cfg['film']['model_path']),
            he_key_dir=Path(cfg['he']['key_dir']),
            keystore_dir=Path(cfg['keystore']['storage_dir']),
            device_key_dir=Path(cfg['tee']['device_keys_dir']),
            threshold=cfg['tee']['key_release']['similarity_threshold'],
        )
        self.pipeline: Optional[BiometricPipeline] = None
    
    async def initialize(self):
        """Initialize pipeline components."""
        self.pipeline = BiometricPipeline(self.pipeline_config)
    
    async def enroll(
        self, 
        user_id: str, 
        fingerprint_image: np.ndarray,
        key_version: Optional[int] = None,
    ) -> EnrollmentResult:
        """Enroll a new fingerprint."""
        if self.pipeline is None:
            await self.initialize()
        return await self.pipeline.enroll(user_id, fingerprint_image, key_version)
    
    async def verify(
        self,
        user_id: str,
        fingerprint_image: np.ndarray,
        key_version: Optional[int] = None,
    ) -> VerificationResult:
        """Verify a fingerprint."""
        if self.pipeline is None:
            await self.initialize()
        return await self.pipeline.verify(user_id, fingerprint_image, key_version)
    
    async def rotate_key(self, user_id: str, reason: str = "user_requested") -> int:
        """Rotate user's biometric key (cancelable biometric)."""
        if self.pipeline is None:
            await self.initialize()
        new_version = await self.pipeline.keystore.rotate_key(user_id, reason)
        self.pipeline.secure_context.revoke_key_version(new_version - 1)
        self.pipeline.secure_context.set_active_key_version(new_version)
        return new_version
    
    def close(self):
        if self.pipeline:
            self.pipeline.close()
    
    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()


def load_fingerprint_image(path: str) -> np.ndarray:
    """Load and preprocess fingerprint image from file."""
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not load image: {path}")
    return image
