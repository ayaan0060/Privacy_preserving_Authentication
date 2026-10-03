# phase7_integration/benchmarks/throughput.py
"""
Throughput Benchmark: Concurrent Verification Capacity.

Measures maximum verifications per second under load.
"""
import asyncio
import time
import statistics
import numpy as np
from dataclasses import dataclass
from typing import List
from pathlib import Path
import tempfile
import sys, os

phase_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for p in ["phase1_encoder", "phase2_keymgmt", "phase3_fusion", "phase4_he", "phase5_backend", "phase6_tee", "phase7_integration"]:
    path = os.path.join(phase_root, p)
    if path not in sys.path:
        sys.path.insert(0, path)

from integration.pipeline import BiometricPipeline, PipelineConfig
from he.crypto import HEClient, generate_he_keys
from he.compute import HESimilarityServer
from he.params import DEFAULT_PARAMS
from film.model import FiLMFusion
import torch
import onnx


@dataclass
class ThroughputResult:
    concurrent_users: int
    total_requests: int
    duration_sec: float
    requests_per_sec: float
    mean_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate: float


class ThroughputBenchmark:
    def __init__(self):
        self.pipeline: BiometricPipeline | None = None
    
    async def setup(self):
        self._device_dir = tempfile.TemporaryDirectory()
        self._he_dir = tempfile.TemporaryDirectory()
        self._keystore_dir = tempfile.TemporaryDirectory()
        self._film_dir = tempfile.TemporaryDirectory()
        
        device_dir = self._device_dir.name
        he_dir = self._he_dir.name
        keystore_dir = self._keystore_dir.name
        film_dir = self._film_dir.name
        
        generate_he_keys(Path(he_dir), DEFAULT_PARAMS)
        
        film_model = FiLMFusion(embedding_dim=256)
        film_model.eval()
        dummy_x = torch.randn(1, 256)
        dummy_k = torch.randn(1, 256)
        try:
            torch.onnx.export(film_model, (dummy_x, dummy_k), Path(film_dir) / "film.onnx", opset_version=17, dynamo=False)
        except TypeError:
            torch.onnx.export(film_model, (dummy_x, dummy_k), Path(film_dir) / "film.onnx", opset_version=17)
        
        class MockEncoderSession:
            def run(self, _, inputs):
                x = inputs[list(inputs.keys())[0]]
                batch = x.shape[0]
                emb = np.random.randn(batch, 256).astype(np.float32)
                emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
                return [emb]
        
        config = PipelineConfig(
            encoder_path=Path(film_dir) / "dummy.onnx",
            film_path=Path(film_dir) / "film.onnx",
            he_key_dir=Path(he_dir),
            keystore_dir=Path(keystore_dir),
            device_key_dir=Path(device_dir),
        )
        
        self.pipeline = BiometricPipeline(config)
        self.pipeline.encoder_session = MockEncoderSession()
        self.pipeline.encoder_input_name = "input"
        self.pipeline.encoder_output_name = "output"
        
        for i in range(100):
            await self.pipeline.enroll(f"user_{i}", np.random.rand(200, 200).astype(np.uint8) * 255)

    
    async def run_load_test(
        self, 
        concurrent_users: int, 
        requests_per_user: int = 10,
    ) -> ThroughputResult:
        """Run concurrent load test."""
        if not self.pipeline:
            await self.setup()
        
        async def single_verify(user_id: str):
            fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
            start = time.perf_counter()
            try:
                result = await self.pipeline.verify(user_id, fingerprint)
                latency = (time.perf_counter() - start) * 1000
                return (True, latency)
            except Exception:
                latency = (time.perf_counter() - start) * 1000
                return (False, latency)
        
        tasks = []
        for i in range(concurrent_users):
            user_id = f"user_{i % 100}"
            for _ in range(requests_per_user):
                tasks.append(single_verify(user_id))
        
        total_requests = len(tasks)
        start_time = time.perf_counter()
        
        results = await asyncio.gather(*tasks)
        
        duration = time.perf_counter() - start_time
        
        successes = [r for r in results if r[0]]
        latencies = [r[1] for r in results if r[0]]
        
        return ThroughputResult(
            concurrent_users=concurrent_users,
            total_requests=total_requests,
            duration_sec=duration,
            requests_per_sec=total_requests / duration if duration > 0 else 0,
            mean_latency_ms=statistics.mean(latencies) if latencies else 0,
            p95_latency_ms=float(np.percentile(latencies, 95)) if latencies else 0,
            p99_latency_ms=float(np.percentile(latencies, 99)) if latencies else 0,
            error_rate=1 - len(successes) / total_requests if total_requests > 0 else 0,
        )
    
    async def run_sweep(self, user_counts: List[int] = None) -> List[ThroughputResult]:
        """Run throughput sweep across concurrency levels."""
        if user_counts is None:
            user_counts = [1, 5, 10, 25, 50, 100]
        
        results = []
        for users in user_counts:
            print(f"Testing {users} concurrent users...")
            result = await self.run_load_test(users, requests_per_user=10)
            results.append(result)
            print(f"  {result.requests_per_sec:.1f} req/s, "
                  f"p95={result.p95_latency_ms:.1f}ms, "
                  f"errors={result.error_rate:.2%}")
        
        return results


async def run_throughput_benchmark():
    """Main entry point."""
    bench = ThroughputBenchmark()
    results = await bench.run_sweep()
    
    print("\n" + "=" * 90)
    print("THROUGHPUT BENCHMARK RESULTS")
    print("=" * 90)
    print(f"{'Users':>6} | {'Req/s':>8} | {'Mean(ms)':>8} | {'P95(ms)':>8} | {'P99(ms)':>8} | {'Errors':>6}")
    print("-" * 90)
    for r in results:
        print(f"{r.concurrent_users:>6} | {r.requests_per_sec:>8.1f} | "
              f"{r.mean_latency_ms:>8.1f} | {r.p95_latency_ms:>8.1f} | "
              f"{r.p99_latency_ms:>8.1f} | {r.error_rate:>6.2%}")
    print("=" * 90)
    
    return results


if __name__ == "__main__":
    asyncio.run(run_throughput_benchmark())
