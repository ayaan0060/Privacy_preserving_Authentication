# phase5_backend/tests/test_integration_p4.py
"""
Integration: Phase 4 HE + Phase 5 Backend.
Full enrollment → verification flow with real HE.
"""
import pytest
import base64
import numpy as np
import sys, os
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import create_app
from backend.services.he_service import he_service
from backend.services.keystore_service import keystore_service
from backend.database import db_manager

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

class TestHEIntegration:
    @pytest.mark.asyncio
    async def test_full_enroll_verify_flow(self, client):
        """Complete flow: enroll → challenge → verify with real HE."""
        user_id = "integration_user"
        
        template = np.random.randn(256).astype(np.float32)
        template = template / np.linalg.norm(template)
        
        ct_bytes = he_service._get_client().encrypt_template(template)
        ct_b64 = base64.b64encode(ct_bytes).decode()
        pk_b64 = base64.b64encode(
            he_service._get_client().context.serialize(save_secret_key=False)
        ).decode()
        
        enroll_resp = await client.post("/enroll", json={
            "user_id": user_id,
            "encrypted_template": ct_b64,
            "client_pk_he": pk_b64,
            "key_version": 1,
        })
        assert enroll_resp.status_code == 201
        
        challenge_resp = await client.post("/verify/challenge", json={"user_id": user_id})
        assert challenge_resp.status_code == 200
        nonce = challenge_resp.json()["nonce"]
        
        probe_ct = he_service._get_client().encrypt_template(template)
        probe_b64 = base64.b64encode(probe_ct).decode()
        
        verify_resp = await client.post("/verify", json={
            "user_id": user_id,
            "nonce": nonce,
            "encrypted_probe": probe_b64,
            "key_version": 1,
        })
        
        assert verify_resp.status_code == 200
        data = verify_resp.json()
        assert data["verified"] is True
        assert data["similarity_score"] > 0.99
        assert data["session_token"] is not None
    
    @pytest.mark.asyncio
    async def test_key_rotation_invalidates_old_template(self, client):
        """After key rotation, old template cannot verify with new key."""
        user_id = "rotation_user"
        
        template = np.random.randn(256).astype(np.float32)
        template = template / np.linalg.norm(template)
        ct_bytes = he_service._get_client().encrypt_template(template)
        ct_b64 = base64.b64encode(ct_bytes).decode()
        pk_b64 = base64.b64encode(
            he_service._get_client().context.serialize(save_secret_key=False)
        ).decode()
        
        await client.post("/enroll", json={
            "user_id": user_id,
            "encrypted_template": ct_b64,
            "client_pk_he": pk_b64,
            "key_version": 1,
        })
        
        keystore_service.rotate_key(user_id, "test_rotation")
        
        template_v2 = np.random.randn(256).astype(np.float32)
        template_v2 = template_v2 / np.linalg.norm(template_v2)
        ct_bytes_v2 = he_service._get_client().encrypt_template(template_v2)
        ct_b64_v2 = base64.b64encode(ct_bytes_v2).decode()
        
        await client.post("/enroll", json={
            "user_id": user_id,
            "encrypted_template": ct_b64_v2,
            "client_pk_he": pk_b64,
            "key_version": 2,
        })
        
        challenge_resp = await client.post("/verify/challenge", json={"user_id": user_id})
        nonce = challenge_resp.json()["nonce"]
        
        probe_ct = he_service._get_client().encrypt_template(template)
        probe_b64 = base64.b64encode(probe_ct).decode()
        
        verify_resp = await client.post("/verify", json={
            "user_id": user_id,
            "nonce": nonce,
            "encrypted_probe": probe_b64,
            "key_version": 1,
        })
        
        assert verify_resp.status_code == 404
        
        probe_ct_v2 = he_service._get_client().encrypt_template(template_v2)
        probe_b64_v2 = base64.b64encode(probe_ct_v2).decode()
        
        verify_resp2 = await client.post("/verify", json={
            "user_id": user_id,
            "nonce": nonce,
            "encrypted_probe": probe_b64_v2,
            "key_version": 2,
        })
        
        assert verify_resp2.status_code == 200
        data = verify_resp2.json()
        assert data["verified"] is True
        assert data["key_version"] == 2
