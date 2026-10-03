# phase5_backend/backend/security/tls.py
"""
TLS Configuration for Production.
Enforces TLS 1.3, secure ciphers, proper cert validation.
"""
import ssl
from pathlib import Path
from typing import Optional

from ..config import get_settings


def create_ssl_context() -> ssl.SSLContext:
    """
    Create hardened SSL context for uvicorn.
    Enforces TLS 1.3 only, secure ciphers.
    """
    settings = get_settings()
    tls_settings = settings.tls
    
    if not tls_settings.enabled:
        raise RuntimeError("TLS is required but disabled in config")
    
    cert_path = Path(tls_settings.cert_file)
    key_path = Path(tls_settings.key_file)
    
    if not cert_path.exists():
        raise FileNotFoundError(f"TLS certificate not found: {cert_path}")
    if not key_path.exists():
        raise FileNotFoundError(f"TLS private key not found: {key_path}")
    
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # Minimum TLS 1.3
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    
    # Secure ciphers only
    context.set_ciphers(tls_settings.ciphers)
    
    # Load cert and key
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    
    # Client verification (mTLS)
    if tls_settings.client_verify and tls_settings.ca_file:
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=tls_settings.ca_file)
    else:
        context.verify_mode = ssl.CERT_NONE
    
    # Security options
    context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2
    context.options |= ssl.OP_NO_COMPRESSION
    context.options |= ssl.OP_SINGLE_ECDH_USE
    context.options |= ssl.OP_SINGLE_DH_USE
    
    return context


def generate_self_signed_cert(
    cert_path: Path, 
    key_path: Path,
    ca_path: Optional[Path] = None,
    common_name: str = "localhost",
    days: int = 365,
) -> None:
    """Generate self-signed certificate for development."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import datetime
    
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc)
    ).not_valid_after(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(common_name)]),
        critical=False,
    ).add_extension(
        x509.BasicConstraints(ca=False, path_length=None), critical=True,
    ).add_extension(
        x509.KeyUsage(
            digital_signature=True,
            key_encipherment=True,
            content_commitment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=True,
    ).add_extension(
        x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
        critical=True,
    ).sign(private_key, hashes.SHA256())
    
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
