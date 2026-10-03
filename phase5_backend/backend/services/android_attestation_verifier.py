"""
Server-side Android Key Attestation Verification.
Verifies Google attestation certificates from StrongBox.
"""
import base64
import cbor2
import hashlib
from typing import List, Optional
from dataclasses import dataclass
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding
from cryptography.x509.oid import ExtensionOID
from cryptography.exceptions import InvalidSignature

@dataclass
class AttestationResult:
    valid: bool
    security_level: Optional[str]
    verified_boot_state: Optional[str]
    device_locked: Optional[bool]
    key_algorithm: Optional[str]
    key_size: Optional[int]
    attestation_challenge: Optional[bytes]
    error: Optional[str]
    public_key_pem: Optional[str]  # Extracted for storage

class AndroidAttestationVerifier:
    """Verify Android Key Attestation certificates from StrongBox."""
    
    # OIDs
    ATTESTATION_OID = "1.3.6.1.4.1.11129.2.1.17"  # Google attestation extension
    ATTESTATION_APP_ID_OID = "1.3.6.1.4.1.11129.2.1.18"  # App ID extension
    
    # Google Attestation Root CAs (Base64 DER) - UPDATE PERIODICALLY
    # Source: https://developers.google.com/android/attestation
    GOOGLE_ROOT_CAS = [
        # Google Hardware Attestation Root CA (as of 2024)
        "MIIFZjCCA06gAwIBAgIQQq1Y9/...",  # Truncated - GET REAL CERTS BELOW
        # Add all current Google attestation roots
    ]
    
    def __init__(self, expected_package_name: str = "com.cancelablebio.auth"):
        self.expected_package_name = expected_package_name
        self._root_certs = self._load_root_certs()
    
    def _load_root_certs(self) -> List[x509.Certificate]:
        """Load Google root CAs. In production, fetch from Google's published list."""
        certs = []
        for pem in self.GOOGLE_ROOT_CAS:
            try:
                der = base64.b64decode(pem)
                cert = x509.load_der_x509_certificate(der)
                certs.append(cert)
            except Exception:
                pass
        return certs
    
    def verify(
        self, 
        cert_chain_pem: List[str], 
        expected_challenge: bytes
    ) -> AttestationResult:
        """
        Verify attestation certificate chain.
        
        Args:
            cert_chain_pem: List of PEM certificates from device (leaf first)
            expected_challenge: Challenge bytes sent during enrollment
            
        Returns:
            AttestationResult with verification status and extracted public key
        """
        try:
            # 1. Parse certificate chain
            certs = [x509.load_pem_x509_certificate(pem.encode()) for pem in cert_chain_pem]
            if not certs:
                return AttestationResult(False, None, None, None, None, None, None, "Empty cert chain", None)
            
            leaf_cert = certs[0]
            
            # 2. Verify chain to Google root (simplified - use proper PKIX in prod)
            if not self._verify_chain_trust(certs):
                return AttestationResult(False, None, None, None, None, None, None, "Chain trust failed", None)
            
            # 3. Extract attestation extension
            attestation_data = self._extract_attestation_extension(leaf_cert)
            if not attestation_data:
                return AttestationResult(False, None, None, None, None, None, None, "No attestation extension", None)
            
            # 3. Verify security level
            sec_level = attestation_data.get("securityLevel")
            if sec_level != "StrongBox":
                return AttestationResult(False, sec_level, None, None, None, None, None, 
                    f"Not StrongBox: {sec_level}", None)
            
            # 4. Verify boot state
            boot_state = attestation_data.get("verifiedBootState")
            if boot_state != "Verified":
                return AttestationResult(False, sec_level, boot_state, None, None, None, None,
                    f"Boot not verified: {boot_state}", None)
            
            # 5. Verify device locked
            if not attestation_data.get("deviceLocked", False):
                return AttestationResult(False, sec_level, boot_state, False, None, None, None,
                    "Device not locked", None)
            
            # 6. Verify key algorithm/size
            key_algo = attestation_data.get("keyAlgorithm")
            key_size = attestation_data.get("keySize")
            if key_algo != "EC" or key_size != 256:
                return AttestationResult(False, sec_level, boot_state, True, key_algo, key_size, None,
                    f"Unexpected key: {key_algo}-{key_size}", None)
            
            # 7. Verify challenge
            challenge_b64 = attestation_data.get("challenge")
            if not challenge_b64:
                return AttestationResult(False, sec_level, boot_state, True, key_algo, key_size, None,
                    "No challenge in attestation", None)
            
            challenge = base64.b64decode(challenge_b64)
            if challenge != expected_challenge:
                return AttestationResult(False, sec_level, boot_state, True, key_algo, key_size, None,
                    "Challenge mismatch", None)
            
            # 8. Verify app package name (anti-replay to other apps)
            app_id = attestation_data.get("appPackageName")
            if app_id != self.expected_package_name:
                return AttestationResult(False, sec_level, boot_state, True, key_algo, key_size, None,
                    f"Package mismatch: {app_id}", None)
            
            # 9. Extract public key for storage
            public_key = leaf_cert.public_key()
            pub_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode()
            
            return AttestationResult(
                valid=True,
                security_level=sec_level,
                verified_boot_state=boot_state,
                device_locked=True,
                key_algorithm=key_algo,
                key_size=key_size,
                attestation_challenge=challenge,
                error=None,
                public_key_pem=pub_pem
            )
            
        except Exception as e:
            return AttestationResult(False, None, None, None, None, None, None, str(e), None)
    
    def _verify_chain_trust(self, certs: List[x509.Certificate]) -> bool:
        """
        Verify certificate chain signatures.
        In production: use proper PKIX validation with Google roots.
        """
        try:
            # Basic chain verification: each cert signed by next
            for i in range(len(certs) - 1):
                issuer = certs[i + 1]
                subject = certs[i]
                issuer_pub = issuer.public_key()
                
                # Verify signature
                if isinstance(issuer_pub, rsa.RSAPublicKey):
                    issuer_pub.verify(
                        subject.signature,
                        subject.tbs_certificate_bytes,
                        padding.PKCS1v15(),
                        subject.signature_hash_algorithm
                    )
                elif isinstance(issuer_pub, ec.EllipticCurvePublicKey):
                    issuer_pub.verify(
                        subject.signature,
                        subject.tbs_certificate_bytes,
                        ec.ECDSA(subject.signature_hash_algorithm)
                    )
            
            # TODO: Verify root against Google roots
            # For now: accept if chain verifies internally
            return True
        except Exception:
            return False
    
    def _extract_attestation_extension(self, cert: x509.Certificate) -> Optional[dict]:
        """Extract and parse CBOR attestation extension."""
        try:
            ext = cert.extensions.get_extension_for_oid(
                x509.ObjectIdentifier(self.ATTESTATION_OID)
            )
            # Value is ASN.1 OCTET STRING containing CBOR
            cbor_bytes = ext.value.value
            return cbor2.loads(cbor_bytes)
        except x509.ExtensionNotFound:
            return None
        except Exception:
            return None
