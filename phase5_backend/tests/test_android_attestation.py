"""
Unit tests for AndroidAttestationVerifier service in phase5_backend.
"""
import base64
import pytest
from backend.services.android_attestation_verifier import AndroidAttestationVerifier, AttestationResult

def test_empty_cert_chain():
    verifier = AndroidAttestationVerifier(expected_package_name="com.cancelablebio.auth")
    result = verifier.verify([], b"challenge_123")
    assert result.valid is False
    assert result.error == "Empty cert chain"

def test_invalid_pem_cert_chain():
    verifier = AndroidAttestationVerifier()
    result = verifier.verify(["INVALID_PEM_DATA"], b"challenge_123")
    assert result.valid is False
    assert "ValueError" in str(result.error) or "Could not deserialize" in str(result.error) or "Unable to load" in str(result.error)
