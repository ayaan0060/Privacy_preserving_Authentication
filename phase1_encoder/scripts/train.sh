#!/usr/bin/env bash
# phase1_encoder/scripts/train.sh
set -euo pipefail

CONFIG="${1:-config.yaml}"
CHECKPOINT="${2:-}"  # Optional resume

echo "=== PHASE 1 TRAINING ==="
echo "Config: $CONFIG"
[ -n "$CHECKPOINT" ] && echo "Resuming from: $CHECKPOINT"

python -m train.trainer \
    --config "$CONFIG" \
    ${CHECKPOINT:+--resume "$CHECKPOINT"}
