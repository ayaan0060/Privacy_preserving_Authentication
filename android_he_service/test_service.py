# android_he_service/test_service.py
import pytest
import numpy as np
import base64
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_encrypt_and_decrypt():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        dummy_template = np.random.randn(256).astype(np.float32)
        dummy_template = dummy_template / np.linalg.norm(dummy_template)
        
        enc_res = await ac.post("/he/encrypt", json={"template": dummy_template.tolist()})
        assert enc_res.status_code == 200
        ciphertext = enc_res.json()["ciphertext"]
        assert len(ciphertext) > 0

        dec_res = await ac.post("/he/decrypt", json={"ciphertext": ciphertext})
        assert dec_res.status_code == 200
        val = dec_res.json()["score"]
        # Decrypting an encrypted vector returns its first element
        assert abs(val - dummy_template[0]) < 1e-3
