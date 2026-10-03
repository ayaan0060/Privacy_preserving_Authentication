# phase6_tee/tee/key_release.py
"""
Key Release Protocol Implementation.

This is the CRYPTOGRAPHIC PROTOCOL for releasing the session key.
It runs INSIDE the SecureContext (TEE or simulation).

Protocol:
1. Server sends Enc(score) + nonce to client
2. Client passes to SecureContext.verify_and_sign()
3. Inside SecureContext:
   a. Decrypt score using HE secret key
   b. Check score >= threshold
   c. Check nonce fresh (not replayed, not expired)
   c. Check key version active
   d. If all pass: sign(payload) with device key
4. Return VerificationResult{verified, signature, signed_payload}
5. Client sends VerificationResult to server
6. Server verifies signature, checks nonce, issues session token
"""
from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime, timezone

from .interface import VerificationResult, DeviceIdentity
from .simulation import verify_and_sign_core, create_signed_payload, verify_signature
from .device_keys import DeviceKeyManager


@dataclass
class KeyReleaseRequest:
    """Request from client to SecureContext."""
    encrypted_similarity: bytes
    he_secret_key: bytes
    nonce: bytes
    key_version: int
    threshold: float


@dataclass
class KeyReleaseResponse:
    """Response from SecureContext."""
    result: VerificationResult
    device_identity: DeviceIdentity


class KeyReleaseProtocol:
    """
    High-level key release protocol coordinator.
    Orchestrates: HE decryption → threshold check → device signing.
    """
    
    def __init__(self, secure_context):
        self.secure_context = secure_context
    
    async def execute_release(self, request: KeyReleaseRequest) -> KeyReleaseResponse:
        """Execute full key release flow."""
        result = await self.secure_context.verify_and_sign(
            encrypted_similarity=request.encrypted_similarity,
            he_secret_key=request.he_secret_key,
            nonce=request.nonce,
            key_version=request.key_version,
            threshold=request.threshold,
        )
        
        device_identity = self.secure_context.get_device_identity()
        
        return KeyReleaseResponse(
            result=result,
            device_identity=device_identity,
        )


def verify_key_release_response(
    response: KeyReleaseResponse,
    expected_nonce: bytes,
    expected_threshold: float,
    max_time_skew_seconds: int = 300,
) -> Tuple[bool, str]:
    """
    Server verifies the key release response.
    Returns (valid, reason).
    """
    result = response.result
    device_identity = response.device_identity

    if not verify_signature(device_identity.public_key, result.signed_payload, result.signature):
        return False, "Invalid device signature"

    try:
        payload_data = parse_signed_payload(result.signed_payload)
    except Exception as e:
        return False, f"Payload parsing failed: {e}"

    expected_nonce_norm = expected_nonce.ljust(32, b'\x00')[:32] if len(expected_nonce) != 32 else expected_nonce
    if payload_data['nonce'] != expected_nonce_norm:
        return False, "Nonce mismatch"

    timestamp = payload_data['timestamp']
    now = datetime.now(timezone.utc)
    age = (now - timestamp).total_seconds()
    if age > max_time_skew_seconds:
        return False, f"Timestamp too old: {age}s"

    if abs(payload_data['similarity_score'] - result.similarity_score) > 1e-6:
        return False, "Score mismatch in payload"

    if payload_data['key_version'] != result.key_version:
        return False, "Key version mismatch"

    if result.similarity_score < expected_threshold or not result.verified:
        return False, f"Similarity score {result.similarity_score:.4f} below threshold {expected_threshold:.4f}"

    return True, "Valid key release"


def parse_signed_payload(payload: bytes) -> dict:
    """Parse canonical payload format."""
    import struct
    offset = 0
    
    nonce = payload[offset:offset+32]
    offset += 32
    
    similarity_score = struct.unpack('>d', payload[offset:offset+8])[0]
    offset += 8
    
    key_version = struct.unpack('>I', payload[offset:offset+4])[0]
    offset += 4
    
    device_id_len = struct.unpack('>H', payload[offset:offset+2])[0]
    offset += 2
    
    device_id = payload[offset:offset+device_id_len].decode('utf-8')
    offset += device_id_len
    
    timestamp_bytes = payload[offset:-1]
    timestamp_str = timestamp_bytes.decode('utf-8')
    timestamp = datetime.fromisoformat(timestamp_str)
    
    verified = bool(payload[-1])
    
    return {
        'nonce': nonce,
        'similarity_score': similarity_score,
        'key_version': key_version,
        'device_id': device_id,
        'timestamp': timestamp,
        'verified': verified,
    }
