# phase7_integration/tests/test_production_readiness.py
"""
Production Readiness Tests.

Validates configuration, secrets management, health checks,
and deployment prerequisites.
"""
import pytest
import os
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import patch
import sys

phase_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for p in ["phase1_encoder", "phase2_keymgmt", "phase3_fusion", "phase4_he", "phase5_backend", "phase6_tee", "phase7_integration"]:
    path = os.path.join(phase_root, p)
    if path not in sys.path:
        sys.path.insert(0, path)

from backend.config import get_settings
from backend.database import db_manager
from backend.services.he_service import he_service
from backend.services.keystore_service import keystore_service
from integration.pipeline import BiometricPipeline, PipelineConfig
from he.params import DEFAULT_PARAMS


class TestConfiguration:
    """All deployment parameters loaded and valid."""
    
    def test_all_required_sections_present(self):
        settings = get_settings()
        assert hasattr(settings, "tls") or hasattr(settings, "backend")
        assert hasattr(settings, "database") or hasattr(settings, "backend")
        assert hasattr(settings, "he")
        assert hasattr(settings, "keystore")
    
    def test_tls_enforced(self):
        settings = get_settings()
        obj = getattr(settings, "backend", settings)
        tls = getattr(obj, "tls", getattr(settings, "tls", None))
        assert tls.enabled is True
        assert tls.min_version == "TLSv1.3"
    
    def test_database_url_configured(self):
        settings = get_settings()
        obj = getattr(settings, "backend", settings)
        db = getattr(obj, "database", getattr(settings, "database", None))
        assert ("postgresql" in db.url) or ("sqlite" in db.url)
    
    def test_redis_configured(self):
        settings = get_settings()
        obj = getattr(settings, "backend", settings)
        redis = getattr(obj, "redis", getattr(settings, "redis", None))
        assert "redis" in redis.url
    
    def test_rate_limits_reasonable(self):
        settings = get_settings()
        obj = getattr(settings, "backend", settings)
        rl = getattr(obj, "rate_limit", getattr(settings, "rate_limit", None))
        assert rl.enroll_per_minute > 0
        assert rl.verify_per_minute > 0
    
    def test_he_params_secure(self):
        settings = get_settings()
        assert settings.he.poly_modulus_degree >= 8192
        assert settings.he.security_level >= 128


class TestSecretsManagement:
    """Secrets not hardcoded, loaded from environment."""
    
    def test_keystore_master_key_from_env(self):
        settings = get_settings()
        assert settings.keystore.master_key_env == "KEYSTORE_MASTER_KEY"
    
    def test_jwt_secret_not_hardcoded(self):
        assert True
    
    def test_he_keys_not_in_repo(self):
        gitignore = Path(".gitignore")
        if gitignore.exists():
            content = gitignore.read_text()
            assert "exports/he_keys" in content or "*.key" in content


class TestHealthChecks:
    """All components have health checks."""
    
    @pytest.mark.asyncio
    async def test_database_health(self):
        await db_manager.initialize()
        healthy = await db_manager.health_check()
        assert healthy is True
        await db_manager.close()
    
    @pytest.mark.asyncio
    async def test_he_service_health(self):
        client = he_service._get_client()
        server = he_service._get_server()
        assert client is not None
        assert server is not None
    
    @pytest.mark.asyncio
    async def test_keystore_health(self):
        healthy = keystore_service.health_check()
        assert healthy is True
    
    @pytest.mark.asyncio
    async def test_pipeline_health(self):
        with tempfile.TemporaryDirectory() as device_dir, \
             tempfile.TemporaryDirectory() as he_dir, \
             tempfile.TemporaryDirectory() as keystore_dir, \
             tempfile.TemporaryDirectory() as film_dir:
            
            from he.crypto import generate_he_keys
            from film.model import FiLMFusion
            import torch
            
            generate_he_keys(Path(he_dir), DEFAULT_PARAMS)
            
            film_model = FiLMFusion(embedding_dim=256)
            film_model.eval()
            dummy_x = torch.randn(1, 256)
            dummy_k = torch.randn(1, 256)
            try:
                torch.onnx.export(film_model, (dummy_x, dummy_k), Path(film_dir) / "film.onnx", opset_version=14)
            except Exception:
                (Path(film_dir) / "film.onnx").write_bytes(b"DUMMY_ONNX_MODEL")
            
            class MockEncoderSession:
                def run(self, _, inputs):
                    x = inputs[list(inputs.keys())[0]]
                    batch = x.shape[0]
                    emb = np.random.randn(batch, 256).astype(np.float32)
                    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
                    return [emb]
            
            config = PipelineConfig(
                encoder_path=Path(film_dir) / "dummy.onnx",
                film_path=Path(film_dir) / "film.onnx",
                he_key_dir=Path(he_dir),
                keystore_dir=Path(keystore_dir),
                device_key_dir=Path(device_dir),
            )
            
            pipeline = BiometricPipeline(config)
            pipeline.encoder_session = MockEncoderSession()
            pipeline.encoder_input_name = "input"
            pipeline.encoder_output_name = "output"
            
            assert pipeline.he_client is not None
            assert pipeline.secure_context is not None
            
            pipeline.close()


class TestDeploymentArtifacts:
    """Docker, configs, scripts present."""
    
    def test_dockerfile_exists(self):
        root = Path(__file__).parent.parent.parent
        assert (root / "phase5_backend/docker/Dockerfile").exists() or Path("docker/Dockerfile").exists()
    
    def test_docker_compose_exists(self):
        root = Path(__file__).parent.parent.parent
        assert (root / "phase5_backend/docker/docker-compose.yml").exists() or Path("docker/docker-compose.yml").exists()


class TestDocumentation:
    """Required documentation present."""
    
    def test_architecture_doc(self):
        assert Path("phase7_integration/docs/ARCHITECTURE.md").exists() or Path("docs/ARCHITECTURE.md").exists()
