#!/usr/bin/env bash
# phase5_backend/scripts/load_test.sh
set -euo pipefail

HOST="${1:-https://localhost:8443}"
USERS="${2:-100}"
SPAWN_RATE="${3:-10}"
RUN_TIME="${4:-60s}"

echo "=== Load Test ==="
echo "Target: $HOST"
echo "Users: $USERS"
echo "Spawn rate: $SPAWN_RATE/s"
echo "Duration: $RUN_TIME"

locust -f locustfile.py --host="$HOST" -u "$USERS" -r "$SPAWN_RATE" -t "$RUN_TIME" --headless
