# phase7_integration/tests/test_key_rotation_e2e.py
"""
End-to-end key rotation test.
Tests: Enroll v1 → Verify v1 → Rotate → Verify v1 fails → Enroll v2 → Verify v2 succeeds
"""
import pytest
import asyncio
import base64
import numpy as np
from httpx import AsyncClient, ASGITransport
import sys, os

phase_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for p in ["phase1_encoder", "phase2_keymgmt", "phase3_fusion", "phase4_he", "phase5_backend", "phase6_tee", "phase7_integration"]:
    path = os.path.join(phase_root, p)
    if path not in sys.path:
        sys.path.insert(0, path)

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


import uuid


class TestKeyRotationE2E:
    
    @pytest.mark.asyncio
    async def test_full_rotation_flow(self, client):
        user_id = f"rotation_e2e_user_{uuid.uuid4().hex[:8]}"
        
        # ===== PHASE 1: Enroll v1 =====
        template_v1 = np.random.randn(256).astype(np.float32)
        template_v1 = template_v1 / np.linalg.norm(template_v1)
        
        ct_v1 = he_service._get_client().encrypt_template(template_v1)
        ct_b64 = base64.b64encode(ct_v1).decode()
        pk_b64 = base64.b64encode(
            he_service._get_client().context.serialize(save_secret_key=False)
        ).decode()
        
        enroll_resp = await client.post("/enroll", json={
            "user_id": user_id,
            "encrypted_template": ct_b64,
            "client_pk_he": pk_b64,
            "key_version": 1,
            "attestation_cert_chain": [],
        })
        assert enroll_resp.status_code == 201
        
        # ===== PHASE 2: Verify v1 (should succeed) =====
        challenge_resp = await client.post("/verify/challenge", json={"user_id": user_id})
        assert challenge_resp.status_code == 200
        nonce = challenge_resp.json()["nonce"]
        
        probe_v1 = template_v1 * 0.95 + np.random.randn(256).astype(np.float32) * 0.05
        probe_v1 = probe_v1 / np.linalg.norm(probe_v1)
        probe_ct = he_service._get_client().encrypt_template(probe_v1)
        probe_b64 = base64.b64encode(probe_ct).decode()
        
        verify_resp = await client.post("/verify", json={
            "user_id": user_id,
            "nonce": nonce,
            "encrypted_probe": probe_b64,
            "key_version": 1
        })
        assert verify_resp.status_code == 200
        assert verify_resp.json()["verified"] is True
        
        # ===== PHASE 3: Rotate Key =====
        rotate_resp = await client.post("/admin/keys/rotate", json={
            "user_id": user_id,
            "reason": "user_requested",
            "attestation_cert_chain": [],
        }, headers={"X-Admin-Key": "change-me-in-production"})
        
        assert rotate_resp.status_code == 200
        rotate_data = rotate_resp.json()
        assert rotate_data["old_version"] == 1
        assert rotate_data["new_version"] == 2
        
        # ===== PHASE 4: Verify v1 FAILS (no active enrollment before v2) =====
        verify_v1_no_active = await client.post("/verify/challenge", json={"user_id": user_id})
        assert verify_v1_no_active.status_code == 404
        
        # ===== PHASE 5: Re-enroll with v2 =====
        template_v2 = np.random.randn(256).astype(np.float32)
        template_v2 = template_v2 / np.linalg.norm(template_v2)
        
        ct_v2 = he_service._get_client().encrypt_template(template_v2)
        ct_v2_b64 = base64.b64encode(ct_v2).decode()
        
        enroll_v2_resp = await client.post("/enroll", json={
            "user_id": user_id,
            "encrypted_template": ct_v2_b64,
            "client_pk_he": pk_b64,
            "key_version": 2,
            "attestation_cert_chain": [],
        })
        assert enroll_v2_resp.status_code == 201
        assert enroll_v2_resp.json()["key_version"] == 2
        
        # ===== PHASE 6: Verify v2 SUCCEEDS & v1 FAILS =====
        challenge_resp2 = await client.post("/verify/challenge", json={"user_id": user_id})
        assert challenge_resp2.status_code == 200
        nonce2 = challenge_resp2.json()["nonce"]

        # Verify old v1 fails even after v2 is enrolled
        verify_v1_fail = await client.post("/verify", json={
            "user_id": user_id,
            "nonce": nonce2,
            "encrypted_probe": probe_b64,
            "key_version": 1  # Old version
        })
        assert verify_v1_fail.status_code == 404  # No active v1 enrollment
        
        # Verify v2 succeeds
        probe_v2 = template_v2 * 0.95 + np.random.randn(256).astype(np.float32) * 0.05
        probe_v2 = probe_v2 / np.linalg.norm(probe_v2)
        probe_v2_ct = he_service._get_client().encrypt_template(probe_v2)
        probe_v2_b64 = base64.b64encode(probe_v2_ct).decode()
        
        verify_v2_resp = await client.post("/verify", json={
            "user_id": user_id,
            "nonce": nonce2,
            "encrypted_probe": probe_v2_b64,
            "key_version": 2
        })
        assert verify_v2_resp.status_code == 200
        assert verify_v2_resp.json()["verified"] is True
        assert verify_v2_resp.json()["key_version"] == 2
        
        print("✅ FULL ROTATION FLOW PASSED")
