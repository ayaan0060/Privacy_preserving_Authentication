# android_he_service/main.py
"""
Android HE Microservice (Runs as separate process on localhost:8001).
Provides HE encryption & decryption endpoints for Android app / TEE integration.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import base64
import tenseal as ts
import numpy as np
from pathlib import Path
import os
import sys

# Add Phase 4 to path if available
phase4_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase4_he"))
if phase4_path not in sys.path:
    sys.path.insert(0, phase4_path)

try:
    from he.crypto import generate_he_keys
    from he.params import DEFAULT_PARAMS
except ImportError:
    generate_he_keys = None

app = FastAPI(title="Android HE Service")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://10.0.2.2", "http://10.0.2.2:8000", "http://10.0.2.2:8001", "http://10.0.2.2:8443", "http://localhost", "http://127.0.0.1"],
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root_summary():
    return {
        "name": "Android HE Encryption Microservice",
        "status": "online",
        "endpoints": {
            "health": "GET /health",
            "encrypt": "POST /he/encrypt",
            "decrypt": "POST /he/decrypt"
        }
    }

KEY_DIR = Path("./he_keys")
KEY_DIR.mkdir(parents=True, exist_ok=True)

secret_key_file = KEY_DIR / "client_secret.key"
public_key_file = KEY_DIR / "client_public.key"

if not secret_key_file.exists() or not public_key_file.exists():
    if generate_he_keys is not None:
        generate_he_keys(KEY_DIR)
    else:
        # Fallback TenSEAL key creation if phase4 module not imported
        context_gen = ts.context(
            ts.SCHEME_TYPE.CKKS,
            poly_modulus_degree=8192,
            coeff_mod_bit_sizes=[60, 40, 40, 60]
        )
        context_gen.global_scale = 2**40
        context_gen.generate_galois_keys()
        context_gen.generate_relin_keys()
        
        secret_key_file.write_bytes(context_gen.serialize(save_secret_key=True))
        context_pub = context_gen.copy()
        context_pub.drop_secret_key()
        public_key_file.write_bytes(context_pub.serialize(save_secret_key=False))

context = ts.context_from(secret_key_file.read_bytes())
public_context = ts.context_from(public_key_file.read_bytes())


class EncryptRequest(BaseModel):
    template: List[float]


class EncryptResponse(BaseModel):
    ciphertext: str  # base64


class DecryptRequest(BaseModel):
    ciphertext: str


class DecryptResponse(BaseModel):
    score: float


@app.post("/he/encrypt", response_model=EncryptResponse)
async def encrypt(req: EncryptRequest):
    try:
        template = np.array(req.template, dtype=np.float32)
        if np.linalg.norm(template) > 0:
            template = template / np.linalg.norm(template)
        
        ct = ts.ckks_vector(context, template.tolist())
        ct_bytes = ct.serialize()
        
        return EncryptResponse(ciphertext=base64.b64encode(ct_bytes).decode())
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/he/decrypt", response_model=DecryptResponse)
async def decrypt(req: DecryptRequest):
    try:
        ct_bytes = base64.b64decode(req.ciphertext)
        ct = ts.ckks_vector_from(context, ct_bytes)
        decrypted = ct.decrypt()
        score = float(decrypted[0].real) if hasattr(decrypted[0], 'real') else float(decrypted[0])
        return DecryptResponse(score=score)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
