# phase4_he/he/benchmarks.py
"""
Comprehensive CKKS Benchmarks.

Measures (REAL, not estimated):
- Key generation time
- Ciphertext size (bytes)
- Encryption latency
- Decryption latency
- Homomorphic dot product latency
- Memory usage
- Numerical accuracy vs plaintext
"""
import time
import statistics
import numpy as np
try:
    import psutil
except ImportError:
    psutil = None
import json
from pathlib import Path
from typing import Dict, List, Union
from tqdm import tqdm

from .params import DEFAULT_PARAMS
from .context import HEContextManager, get_context_sizes
from .crypto import HEClient
from .compute import HESimilarityServer, plaintext_dot_product
from .client import BiometricHEClient
from .server import BiometricHEServer


class HEBenchmarker:
    def __init__(self, key_dir: Union[str, Path], params = DEFAULT_PARAMS, 
                 num_runs: int = 100, warmup: int = 10):
        self.key_dir = Path(key_dir)
        self.params = params
        self.num_runs = num_runs
        self.warmup = warmup
        
        # Ensure keys exist
        mgr = HEContextManager(key_dir, params)
        if not mgr.client_secret_path.exists():
            mgr.generate_keys()
        
        self.client = BiometricHEClient(key_dir, params)
        self.server = BiometricHEServer(key_dir, params)
        self.he_client = HEClient(key_dir, params)
        self.he_server = HESimilarityServer(key_dir, params)
    
    def _time_it(self, func, *args, **kwargs) -> List[float]:
        """Run function multiple times, return list of latencies (ms)."""
        latencies = []
        
        for _ in range(self.warmup):
            func(*args, **kwargs)
        
        for _ in range(self.num_runs):
            start = time.perf_counter()
            func(*args, **kwargs)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)
        
        return latencies
    
    def _stats(self, latencies: List[float]) -> Dict[str, float]:
        return {
            "mean_ms": statistics.mean(latencies),
            "median_ms": statistics.median(latencies),
            "stdev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "p95_ms": float(np.percentile(latencies, 95)),
            "p99_ms": float(np.percentile(latencies, 99)),
        }
    
    def benchmark_keygen(self) -> Dict:
        """Key generation latency (one-time)."""
        mgr = HEContextManager(self.key_dir, self.params)
        latencies = self._time_it(mgr.generate_keys, force=True)
        return {"keygen": self._stats(latencies)}
    
    def benchmark_key_sizes(self) -> Dict:
        """Serialized key sizes."""
        return {"key_sizes_kb": get_context_sizes(self.he_client.context)}
    
    def benchmark_encryption(self) -> Dict:
        """Template encryption latency."""
        template = np.random.randn(256).astype(np.float32)
        template = template / np.linalg.norm(template)
        
        latencies = self._time_it(self.he_client.encrypt_template, template)
        return {"encryption_ms": self._stats(latencies)}
    
    def benchmark_decryption(self) -> Dict:
        """Score decryption latency."""
        template = np.random.randn(256).astype(np.float32)
        template = template / np.linalg.norm(template)
        ct = self.he_client.encrypt_template(template)
        
        latencies = self._time_it(self.he_client.decrypt_score, ct)
        return {"decryption_ms": self._stats(latencies)}
    
    def benchmark_homomorphic_dot(self) -> Dict:
        """Server-side homomorphic dot product latency."""
        t1 = np.random.randn(256).astype(np.float32)
        t2 = np.random.randn(256).astype(np.float32)
        t1 = t1 / np.linalg.norm(t1)
        t2 = t2 / np.linalg.norm(t2)
        
        ct1 = self.he_client.encrypt_template(t1)
        ct2 = self.he_client.encrypt_template(t2)
        
        latencies = self._time_it(self.he_server.compute_similarity, ct1, ct2)
        return {"homomorphic_dot_ms": self._stats(latencies)}
    
    def benchmark_full_roundtrip(self) -> Dict:
        """Full client-server-client roundtrip latency."""
        t_enroll = np.random.randn(256).astype(np.float32)
        t_probe = np.random.randn(256).astype(np.float32)
        t_enroll = t_enroll / np.linalg.norm(t_enroll)
        t_probe = t_probe / np.linalg.norm(t_probe)
        
        def roundtrip():
            probe_ct = self.he_client.encrypt_template(t_probe)
            enrolled_ct = self.he_client.encrypt_template(t_enroll)
            result_ct = self.he_server.compute_similarity(enrolled_ct, probe_ct)
            return self.he_client.decrypt_score(result_ct)
        
        latencies = self._time_it(roundtrip)
        return {"full_roundtrip_ms": self._stats(latencies)}
    
    def benchmark_accuracy(self, num_samples: int = 1000) -> Dict:
        """Numerical accuracy: HE result vs plaintext."""
        errors = []
        max_error = 0.0
        
        for _ in range(num_samples):
            t1 = np.random.randn(256).astype(np.float32)
            t2 = np.random.randn(256).astype(np.float32)
            t1 = t1 / np.linalg.norm(t1)
            t2 = t2 / np.linalg.norm(t2)
            
            pt_score = plaintext_dot_product(t1, t2)
            
            ct1 = self.he_client.encrypt_template(t1)
            ct2 = self.he_client.encrypt_template(t2)
            ct_result = self.he_server.compute_similarity(ct1, ct2)
            he_score = self.he_client.decrypt_score(ct_result)
            
            error = abs(he_score - pt_score)
            rel_error = error / (abs(pt_score) + 1e-10)
            errors.append(rel_error)
            max_error = max(max_error, rel_error)
        
        return {
            "accuracy": {
                "mean_rel_error": float(np.mean(errors)),
                "median_rel_error": float(np.median(errors)),
                "max_rel_error": float(max_error),
                "p95_rel_error": float(np.percentile(errors, 95)),
                "samples": num_samples,
            }
        }
    
    def benchmark_memory(self) -> Dict:
        """Memory usage during operations."""
        if psutil is None:
            return {"baseline_mb": 0.0, "peak_mb": 0.0, "delta_mb": 0.0}
        process = psutil.Process()
        baseline_mem = process.memory_info().rss / 1024 / 1024
        
        templates = [np.random.randn(256).astype(np.float32) for _ in range(100)]
        templates = [t / np.linalg.norm(t) for t in templates]
        
        cts = []
        for t in templates:
            cts.append(self.he_client.encrypt_template(t))
        
        after_encrypt_mem = process.memory_info().rss / 1024 / 1024
        
        for ct in cts:
            self.he_server.compute_similarity(cts[0], ct)
        
        after_compute_mem = process.memory_info().rss / 1024 / 1024
        
        return {
            "memory_mb": {
                "baseline": baseline_mem,
                "after_100_encrypt": after_encrypt_mem,
                "after_100_compute": after_compute_mem,
                "encrypt_overhead_mb": after_encrypt_mem - baseline_mem,
                "compute_overhead_mb": after_compute_mem - after_encrypt_mem,
            }
        }
    
    def run_all(self) -> Dict:
        """Run complete benchmark suite."""
        print(f"[BENCHMARK] Running {self.num_runs} iterations (warmup={self.warmup})...")
        
        results = {}
        results.update(self.benchmark_key_sizes())
        print("  Key sizes done")
        
        results.update(self.benchmark_encryption())
        print("  Encryption done")
        
        results.update(self.benchmark_decryption())
        print("  Decryption done")
        
        results.update(self.benchmark_homomorphic_dot())
        print("  Homomorphic dot done")
        
        results.update(self.benchmark_full_roundtrip())
        print("  Full roundtrip done")
        
        results.update(self.benchmark_accuracy(500))
        print("  Accuracy done")
        
        results["memory_mb"] = self.benchmark_memory()
        print("  Memory done")
        
        results["parameters"] = {
            "poly_modulus_degree": self.params.poly_modulus_degree,
            "coeff_mod_bit_sizes": self.params.coeff_mod_bit_sizes,
            "scale_bits": self.params.scale_bits,
            "security_level": self.params.security_level,
            "embedding_dim": 256,
        }
        
        return results


def run_benchmarks(key_dir: str = "./exports/he_keys", 
                   output: str = "./exports/benchmark_report.json",
                   num_runs: int = 100):
    """Main benchmark entry point."""
    benchmarker = HEBenchmarker(key_dir, num_runs=num_runs)
    results = benchmarker.run_all()
    
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n=== BENCHMARK SUMMARY ===")
    print(f"Key sizes: {results['key_sizes_kb']}")
    print(f"Encryption: {results['encryption_ms']['mean_ms']:.1f} ms (median)")
    print(f"Decryption: {results['decryption_ms']['mean_ms']:.1f} ms (median)")
    print(f"Homomorphic dot: {results['homomorphic_dot_ms']['mean_ms']:.1f} ms (median)")
    print(f"Full roundtrip: {results['full_roundtrip_ms']['mean_ms']:.1f} ms (median)")
    print(f"Max relative error: {results['accuracy']['max_rel_error']:.2e}")
    print(f"Report saved to: {output}")
    
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-dir", default="./exports/he_keys")
    parser.add_argument("--output", default="./exports/benchmark_report.json")
    parser.add_argument("--runs", type=int, default=100)
    args = parser.parse_args()
    
    run_benchmarks(args.key_dir, args.output, args.runs)
