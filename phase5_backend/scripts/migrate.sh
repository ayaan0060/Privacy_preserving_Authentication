#!/usr/bin/env bash
# phase5_backend/scripts/migrate.sh
set -euo pipefail

CONFIG="${1:-./config.yaml}"
COMMAND="${2:-upgrade head}"

export CONFIG_PATH="$CONFIG"

echo "=== Running Database Migration ==="
echo "Command: alembic $COMMAND"

alembic -c alembic.ini $COMMAND
