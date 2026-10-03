#!/usr/bin/env bash
# phase5_backend/scripts/run_server.sh
set -euo pipefail

CONFIG="${1:-./config.yaml}"
HOST="${2:-0.0.0.0}"
PORT="${3:-8443}"

export CONFIG_PATH="$CONFIG"

echo "=== Starting Backend Server ==="
echo "Config: $CONFIG"
echo "Host: $HOST:$PORT"

if [ ! -f "./certs/server.crt" ]; then
    ./scripts/generate_certs.sh
fi

python -m backend.main
