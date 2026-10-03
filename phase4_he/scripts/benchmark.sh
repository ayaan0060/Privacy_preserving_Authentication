#!/usr/bin/env bash
# phase4_he/scripts/benchmark.sh
set -euo pipefail

KEY_DIR="${1:-./exports/he_keys}"
OUTPUT="${2:-./exports/benchmark_report.json}"
RUNS="${3:-100}"

echo "=== CKKS BENCHMARK ==="
echo "Key directory: $KEY_DIR"
echo "Output: $OUTPUT"
echo "Runs: $RUNS"

python -m he.benchmarks \
    --key-dir "$KEY_DIR" \
    --output "$OUTPUT" \
    --runs "$RUNS"
