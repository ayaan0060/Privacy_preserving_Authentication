# phase5_backend/tests/test_api_verification.py
import pytest
import base64
import numpy as np
import sys, os
from httpx import AsyncClient, ASGITransport

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
async def enrolled_user(client):
    user_id = "verify_test_user"
    template = np.random.randn(256).astype(np.float32)
    template = template / np.linalg.norm(template)
    ct_bytes = he_service._get_client().encrypt_template(template)
    ct_b64 = base64.b64encode(ct_bytes).decode()
    pk_b64 = base64.b64encode(he_service._get_client().context.serialize(save_secret_key=False)).decode()
    
    await client.post("/enroll", json={
        "user_id": user_id,
        "encrypted_template": ct_b64,
        "client_pk_he": pk_b64,
        "key_version": 1,
    })
    
    return user_id, template

class TestVerification:
    @pytest.mark.asyncio
    async def test_challenge_issued(self, client, enrolled_user):
        user_id, _ = enrolled_user
        response = await client.post("/verify/challenge", json={"user_id": user_id})
        
        assert response.status_code == 200
        data = response.json()
        assert "nonce" in data
        assert data["expires_in_seconds"] == 300

    @pytest.mark.asyncio
    async def test_verify_success(self, client, enrolled_user):
        user_id, template = enrolled_user
        
        challenge = await client.post("/verify/challenge", json={"user_id": user_id})
        nonce = challenge.json()["nonce"]
        
        probe_ct = he_service._get_client().encrypt_template(template)
        probe_b64 = base64.b64encode(probe_ct).decode()
        
        response = await client.post("/verify", json={
            "user_id": user_id,
            "nonce": nonce,
            "encrypted_probe": probe_b64,
            "key_version": 1,
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert data["similarity_score"] > 0.99
        assert data["session_token"] is not None

    @pytest.mark.asyncio
    async def test_verify_fail_different_finger(self, client, enrolled_user):
        user_id, _ = enrolled_user
        
        challenge = await client.post("/verify/challenge", json={"user_id": user_id})
        nonce = challenge.json()["nonce"]
        
        different_template = np.random.randn(256).astype(np.float32)
        different_template = different_template / np.linalg.norm(different_template)
        probe_ct = he_service._get_client().encrypt_template(different_template)
        probe_b64 = base64.b64encode(probe_ct).decode()
        
        response = await client.post("/verify", json={
            "user_id": user_id,
            "nonce": nonce,
            "encrypted_probe": probe_b64,
            "key_version": 1,
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is False
        assert data["session_token"] is None

    @pytest.mark.asyncio
    async def test_verify_replay_attack_fails(self, client, enrolled_user):
        user_id, template = enrolled_user
        
        challenge = await client.post("/verify/challenge", json={"user_id": user_id})
        nonce = challenge.json()["nonce"]
        
        probe_ct = he_service._get_client().encrypt_template(template)
        probe_b64 = base64.b64encode(probe_ct).decode()
        
        await client.post("/verify", json={
            "user_id": user_id,
            "nonce": nonce,
            "encrypted_probe": probe_b64,
            "key_version": 1,
        })
        
        response = await client.post("/verify", json={
            "user_id": user_id,
            "nonce": nonce,
            "encrypted_probe": probe_b64,
            "key_version": 1,
        })
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_compute_success(self, client, enrolled_user):
        user_id, template = enrolled_user
        
        challenge = await client.post("/verify/challenge", json={"user_id": user_id})
        nonce = challenge.json()["nonce"]
        
        probe_ct = he_service._get_client().encrypt_template(template)
        probe_b64 = base64.b64encode(probe_ct).decode()
        
        response = await client.post("/verify/compute", json={
            "user_id": user_id,
            "encrypted_probe": probe_b64,
            "nonce": nonce,
            "key_version": 1,
        })
        
        if response.status_code != 200:
            print("ERROR RESPONSE:", response.json())
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["encrypted_score"] is not None
