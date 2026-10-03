#!/usr/bin/env bash
# phase7_integration/scripts/run_full_demo.sh
set -euo pipefail

echo "=========================================="
echo "CANCELABLE BIOMETRIC AUTH - FULL DEMO"
echo "=========================================="
echo

# 1. Start infrastructure
echo "[1/6] Starting PostgreSQL + Redis..."
docker-compose -f docker/docker-compose.yml up -d postgres redis || true
sleep 5

# 2. Generate TLS certs
echo "[2/6] Generating TLS certificates..."
./scripts/generate_certs.sh || true

# 3. Generate HE keys
echo "[3/6] Generating CKKS keys..."
python -c "
from he.crypto import generate_he_keys
from he.params import DEFAULT_PARAMS
from pathlib import Path
generate_he_keys(Path('./exports/he_keys'), DEFAULT_PARAMS)
"

# 4. Generate device keys
echo "[4/6] Generating device keys..."
python phase6_tee/scripts/generate_device_keys.py --key-dir ./exports/device_keys

# 5. Run database migrations
echo "[5/6] Running database migrations..."
alembic -c alembic.ini upgrade head || true

# 6. Start backend server
echo "[6/6] Starting backend server..."
export CONFIG_PATH=./config.yaml
python -m backend.main &
SERVER_PID=$!

sleep 3

echo
echo "=========================================="
echo "RUNNING CLIENT DEMO"
echo "=========================================="
python -c "
import asyncio
import numpy as np
from integration.client import BiometricAuthClient

async def demo():
    async with BiometricAuthClient() as client:
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        print('Enrolling user alice...')
        enroll = await client.enroll('alice', fingerprint)
        print(f'  Enrolled: key_version={enroll.key_version}')
        
        print('Verifying...')
        verify = await client.verify('alice', fingerprint)
        print(f'  Verified: {verify.verified}')
        print(f'  Score: {verify.similarity_score:.4f}')
        print(f'  Latency: {verify.latency_ms}')
        
        print('Rotating key...')
        new_ver = await client.rotate_key('alice', 'demo_rotation')
        print(f'  New version: {new_ver}')
        
        print('Verifying with new key...')
        verify2 = await client.verify('alice', fingerprint)
        print(f'  Verified: {verify2.verified}')
        print(f'  Key version: {verify2.key_version}')

asyncio.run(demo())
"

kill $SERVER_PID || true
docker-compose -f docker/docker-compose.yml down || true

echo
echo "=========================================="
echo "DEMO COMPLETE"
echo "=========================================="
