# phase5_backend/tests/test_api_enrollment.py
import pytest
import base64
import numpy as np
import sys, os
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import create_app
from backend.database import db_manager
from backend.services.he_service import he_service

@pytest.fixture
async def app():
    app = create_app()
    await db_manager.initialize()
    await db_manager.create_tables()
    yield app

@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def test_user():
    return "testuser_enroll"

class TestEnrollment:
    @pytest.mark.asyncio
    async def test_enroll_success(self, client, test_user):
        template = np.random.randn(256).astype(np.float32)
        template = template / np.linalg.norm(template)
        ct_bytes = he_service._get_client().encrypt_template(template)
        ct_b64 = base64.b64encode(ct_bytes).decode()
        pk_b64 = base64.b64encode(he_service._get_client().context.serialize(save_secret_key=False)).decode()
        
        response = await client.post("/enroll", json={
            "user_id": test_user,
            "encrypted_template": ct_b64,
            "client_pk_he": pk_b64,
            "key_version": 1,
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == test_user
        assert data["key_version"] == 1

    @pytest.mark.asyncio
    async def test_enroll_duplicate_version_fails(self, client, test_user):
        template = np.random.randn(256).astype(np.float32)
        template = template / np.linalg.norm(template)
        ct_bytes = he_service._get_client().encrypt_template(template)
        ct_b64 = base64.b64encode(ct_bytes).decode()
        pk_b64 = base64.b64encode(he_service._get_client().context.serialize(save_secret_key=False)).decode()
        
        await client.post("/enroll", json={
            "user_id": test_user,
            "encrypted_template": ct_b64,
            "client_pk_he": pk_b64,
            "key_version": 1,
        })
        
        response = await client.post("/enroll", json={
            "user_id": test_user,
            "encrypted_template": ct_b64,
            "client_pk_he": pk_b64,
            "key_version": 1,
        })
        
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_enroll_invalid_ciphertext(self, client, test_user):
        response = await client.post("/enroll", json={
            "user_id": test_user,
            "encrypted_template": base64.b64encode(b"invalid").decode(),
            "client_pk_he": base64.b64encode(b"invalid").decode(),
            "key_version": 1,
        })
        
        assert response.status_code == 400
