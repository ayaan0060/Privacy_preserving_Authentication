#!/usr/bin/env bash
# phase5_backend/scripts/generate_certs.sh
set -euo pipefail

CERT_DIR="${1:-./certs}"
DAYS="${2:-365}"
CN="${3:-localhost}"

echo "=== Generating TLS Certificates ==="
echo "Directory: $CERT_DIR"
echo "Validity: $DAYS days"
echo "CN: $CN"

mkdir -p "$CERT_DIR"

python -c "
from backend.security.tls import generate_self_signed_cert
from pathlib import Path
generate_self_signed_cert(
    cert_path=Path('$CERT_DIR/server.crt'),
    key_path=Path('$CERT_DIR/server.key'),
    ca_path=Path('$CERT_DIR/ca.crt'),
    common_name='$CN',
    days=$DAYS,
)
print('Certificates generated successfully')
"
