#!/usr/bin/env bash
# phase7_integration/scripts/run_benchmarks.sh
set -euo pipefail

echo "=========================================="
echo "FULL BENCHMARK SUITE"
echo "=========================================="

echo "[1/3] Latency breakdown..."
python -m benchmarks.latency --runs 100

echo "[2/3] Throughput sweep..."
python -m benchmarks.throughput

echo "[3/3] Generating consolidated report..."
python -m benchmarks.report

echo
echo "=========================================="
echo "BENCHMARKS COMPLETE"
echo "=========================================="
echo "Reports:"
echo "  ./exports/benchmark_report.json"
echo "  ./exports/adversarial_report.json"
