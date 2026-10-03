# phase4_he/tests/test_benchmarks.py
import pytest
import tempfile
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from he.benchmarks import HEBenchmarker
from he.params import DEFAULT_PARAMS
from he.crypto import generate_he_keys

@pytest.fixture
def benchmarker():
    with tempfile.TemporaryDirectory() as tmpdir:
        generate_he_keys(tmpdir, DEFAULT_PARAMS)
        yield HEBenchmarker(tmpdir, num_runs=10, warmup=2)

def test_benchmark_runs(benchmarker):
    results = benchmarker.run_all()
    
    assert "key_sizes_kb" in results
    assert "encryption_ms" in results
    assert "decryption_ms" in results
    assert "homomorphic_dot_ms" in results
    assert "full_roundtrip_ms" in results
    assert "accuracy" in results
    assert "memory_mb" in results
    assert "parameters" in results
    
    assert results["encryption_ms"]["mean_ms"] > 0
    assert results["homomorphic_dot_ms"]["mean_ms"] > 0
    assert results["accuracy"]["mean_rel_error"] < 1e-2
