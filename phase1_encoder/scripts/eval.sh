#!/usr/bin/env bash
# phase1_encoder/scripts/eval.sh
set -euo pipefail

CONFIG="${1:-config.yaml}"
CHECKPOINT="${2:-checkpoints/best.pt}"
OUTPUT_DIR="${3:-eval_results}"

echo "=== PHASE 1 EVALUATION ==="
echo "Config: $CONFIG"
echo "Checkpoint: $CHECKPOINT"
echo "Output: $OUTPUT_DIR"

python -m eval.evaluate \
    --config "$CONFIG" \
    --checkpoint "$CHECKPOINT" \
    --output-dir "$OUTPUT_DIR"
