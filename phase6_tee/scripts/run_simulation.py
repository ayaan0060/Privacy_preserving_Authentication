#!/usr/bin/env python3
# phase6_tee/scripts/run_simulation.py
"""
Demo: Full key release simulation.
"""
import asyncio
import base64
import numpy as np
from pathlib import Path
import tempfile
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
phase4_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "phase4_he"))
if phase4_path not in sys.path:
    sys.path.insert(0, phase4_path)

from tee.simulation import SoftwareSecureContext
from tee.key_release import KeyReleaseProtocol, KeyReleaseRequest, verify_key_release_response
from tee.device_keys import DeviceKeyManager
from he.crypto import HEClient, generate_he_keys
from he.compute import HESimilarityServer
from he.params import DEFAULT_PARAMS


async def main():
    print("=" * 70)
    print("KEY RELEASE SIMULATION DEMO")
    print("=" * 70)
    print()
    print("⚠️  THIS IS A SOFTWARE SIMULATION - NOT A REAL TEE")
    print("⚠️  DO NOT USE FOR PRODUCTION BIOMETRIC DATA")
    print()
    
    with tempfile.TemporaryDirectory() as device_dir, \
         tempfile.TemporaryDirectory() as he_dir:
        
        print("[1/5] Generating HE keys...")
        generate_he_keys(Path(he_dir), DEFAULT_PARAMS)
        
        print("[2/5] Initializing secure context...")
        ctx = SoftwareSecureContext(
            device_key_dir=Path(device_dir),
            he_key_dir=Path(he_dir),
            use_mlock=False,
            zeroize_on_release=True,
        )
        
        protocol = KeyReleaseProtocol(ctx)
        
        client = HEClient(Path(he_dir), DEFAULT_PARAMS)
        server = HESimilarityServer(Path(he_dir), DEFAULT_PARAMS)
        
        print("[3/5] Simulating enrollment...")
        template = np.random.randn(256).astype(np.float32)
        template = template / np.linalg.norm(template)
        enrolled_ct = client.encrypt_template(template)
        
        print("    Enrolled template encrypted and stored on server")
        
        print("[4/5] Running verification...")
        
        nonce = b"demo_nonce_32_bytes_for_testing!!"
        print(f"    Server nonce: {nonce.hex()[:16]}...")
        
        probe_template = template * 0.95 + np.random.randn(256).astype(np.float32) * 0.05
        probe_template = probe_template / np.linalg.norm(probe_template)
        probe_ct = client.encrypt_template(probe_template)
        
        enc_score = server.compute_similarity(enrolled_ct, probe_ct)
        print("    Server computed Enc(score) homomorphically")
        
        print("[5/5] Secure context verifying...")
        he_secret = Path(he_dir).joinpath("client_secret.key").read_bytes()
        
        request = KeyReleaseRequest(
            encrypted_similarity=enc_score,
            he_secret_key=he_secret,
            nonce=nonce,
            key_version=1,
            threshold=0.3,
        )
        
        response = await protocol.execute_release(request)
        
        print()
        print("=" * 70)
        print("RESULTS")
        print("=" * 70)
        print(f"Verified: {response.result.verified}")
        print(f"Similarity Score: {response.result.similarity_score:.4f}")
        print(f"Key Version: {response.result.key_version}")
        print(f"Timestamp: {response.result.timestamp.isoformat()}")
        print(f"Device ID: {response.device_identity.device_id}")
        print(f"TEE Type: {response.device_identity.tee_type}")
        print(f"Signature: {response.result.signature.hex()[:32]}... ({len(response.result.signature)} bytes)")
        
        print()
        print("Server verifying key release response...")
        valid, reason = verify_key_release_response(
            response=response,
            expected_nonce=nonce,
            expected_threshold=0.3,
        )
        print(f"Valid: {valid}")
        print(f"Reason: {reason}")
        
        if valid:
            print()
            print("✅ KEY RELEASE SUCCESSFUL")
            print("   Server would now issue session token")
        else:
            print()
            print("❌ KEY RELEASE FAILED")
        
        ctx.close()
    
    print()
    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
