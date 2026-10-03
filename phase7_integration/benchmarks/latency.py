# phase7_integration/benchmarks/latency.py
"""
Full Pipeline Latency Breakdown.

Measures end-to-end latency for each phase:
1. Preprocessing
2. Encoder Inference
3. Keystore Key Retrieval
4. FiLM Fusion
5. HE Encryption (client)
6. HE Homomorphic Compute (server)
7. HE Decryption (client)
8. TEE Key Release
9. Network Overhead (simulated)
"""
import asyncio
import time
import statistics
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict
from pathlib import Path
import tempfile
import sys, os

phase_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for p in ["phase1_encoder", "phase2_keymgmt", "phase3_fusion", "phase4_he", "phase5_backend", "phase6_tee", "phase7_integration"]:
    path = os.path.join(phase_root, p)
    if path not in sys.path:
        sys.path.insert(0, path)

from integration.pipeline import BiometricPipeline, PipelineConfig, film_fuse
from he.crypto import HEClient, generate_he_keys
from he.compute import HESimilarityServer
from he.params import DEFAULT_PARAMS
from film.model import FiLMFusion
from tee.simulation import SoftwareSecureContext
import torch
import onnx


@dataclass
class LatencyResult:
    phase: str
    mean_ms: float
    median_ms: float
    stdev_ms: float
    min_ms: float
    max_ms: float
    p95_ms: float
    p99_ms: float
    samples: int


@dataclass
class FullLatencyReport:
    results: List[LatencyResult]
    total_mean_ms: float
    bottleneck: str


class LatencyBenchmark:
    def __init__(self, num_runs: int = 100, warmup: int = 10):
        self.num_runs = num_runs
        self.warmup = warmup
        self.pipeline: BiometricPipeline | None = None
    
    async def setup(self):
        """Initialize pipeline with temporary directories."""
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
        
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        await self.pipeline.enroll("bench_user", fingerprint)

    
    async def _time_async(self, func, *args, **kwargs) -> List[float]:
        """Time an async function multiple times."""
        times = []
        
        for _ in range(self.warmup):
            await func(*args, **kwargs)
        
        for _ in range(self.num_runs):
            start = time.perf_counter()
            await func(*args, **kwargs)
            times.append((time.perf_counter() - start) * 1000)
        
        return times

    
    def _time_sync(self, func, *args, **kwargs) -> List[float]:
        """Time a sync function multiple times."""
        times = []
        
        for _ in range(self.warmup):
            func(*args, **kwargs)
        
        for _ in range(self.num_runs):
            start = time.perf_counter()
            func(*args, **kwargs)
            times.append((time.perf_counter() - start) * 1000)
        
        return times
    
    def _stats(self, times: List[float], phase: str) -> LatencyResult:
        return LatencyResult(
            phase=phase,
            mean_ms=statistics.mean(times),
            median_ms=statistics.median(times),
            stdev_ms=statistics.stdev(times) if len(times) > 1 else 0,
            min_ms=min(times),
            max_ms=max(times),
            p95_ms=float(np.percentile(times, 95)),
            p99_ms=float(np.percentile(times, 99)),
            samples=len(times),
        )
    
    async def run_all(self) -> FullLatencyReport:
        """Run complete latency benchmark."""
        if not self.pipeline:
            await self.setup()
        
        p = self.pipeline
        fingerprint = np.random.rand(200, 200).astype(np.uint8) * 255
        
        results = []
        
        times = self._time_sync(p._preprocess_fingerprint, fingerprint)
        results.append(self._stats(times, "Preprocessing"))
        
        processed = p._preprocess_fingerprint(fingerprint)
        times = self._time_sync(
            p.encoder_session.run,
            [p.encoder_output_name],
            {p.encoder_input_name: processed.astype(np.float32)}
        )
        results.append(self._stats(times, "Encoder Inference"))
        
        times = self._time_sync(p.keystore.get_key_material, "bench_user")
        results.append(self._stats(times, "Keystore Key Retrieval"))
        
        embedding = p.encoder_session.run(
            [p.encoder_output_name],
            {p.encoder_input_name: processed.astype(np.float32)}
        )[0][0]
        key_material = p.keystore.get_key_material("bench_user")
        times = self._time_sync(
            film_fuse, p.film_session, embedding, key_material.key_vector
        )
        results.append(self._stats(times, "FiLM Fusion"))
        
        fused = film_fuse(p.film_session, embedding, key_material.key_vector)
        times = self._time_sync(p.he_client.encrypt_template, fused)
        results.append(self._stats(times, "HE Encryption (Client)"))
        
        enrolled_result = await p._get_enrollment("bench_user", 1)
        probe_ct = p.he_client.encrypt_template(fused)
        times = self._time_sync(
            p.he_server.compute_similarity,
            enrolled_result.enrolled_template_ct, probe_ct
        )
        results.append(self._stats(times, "HE Compute (Server)"))
        
        enc_score = p.he_server.compute_similarity(
            enrolled_result.enrolled_template_ct, probe_ct
        )
        times = self._time_sync(p.he_client.decrypt_score, enc_score)
        results.append(self._stats(times, "HE Decryption (Client)"))
        
        he_secret = p.config.he_key_dir.joinpath("client_secret.key").read_bytes()
        async def tee_call():
            return await p.secure_context.verify_and_sign(
                encrypted_similarity=enc_score,
                he_secret_key=he_secret,
                nonce=os.urandom(32),
                key_version=1,
                threshold=0.0,
            )


        
        times = await self._time_async(tee_call)
        results.append(self._stats(times, "TEE Key Release"))
        
        import uuid
        async def full_enroll():
            uid = f"bench_user_{uuid.uuid4().hex[:8]}"
            return await p.enroll(uid, fingerprint)
        
        times = await self._time_async(full_enroll)

        results.append(self._stats(times, "Full Enrollment"))
        
        async def full_verify():
            return await p.verify("bench_user", fingerprint)
        
        times = await self._time_async(full_verify)

        results.append(self._stats(times, "Full Verification"))
        
        total_mean = sum(r.mean_ms for r in results if "Full" not in r.phase)
        bottleneck = max(results, key=lambda r: r.mean_ms).phase
        
        return FullLatencyReport(
            results=results,
            total_mean_ms=total_mean,
            bottleneck=bottleneck,
        )


def print_latency_report(report: FullLatencyReport):
    """Pretty print latency report."""
    print("\n" + "=" * 80)
    print("LATENCY BREAKDOWN REPORT")
    print("=" * 80)
    print(f"{'Phase':<35} {'Mean':>8} {'Median':>8} {'Stdev':>8} {'P95':>8} {'P99':>8}")
    print("-" * 80)
    
    for r in report.results:
        print(f"{r.phase:<35} {r.mean_ms:>8.1f} {r.median_ms:>8.1f} "
              f"{r.stdev_ms:>8.1f} {r.p95_ms:>8.1f} {r.p99_ms:>8.1f}")
    
    print("-" * 80)
    print(f"{'TOTAL (excl. full)':<35} {report.total_mean_ms:>8.1f} ms")
    print(f"{'BOTTLENECK':<35} {report.bottleneck}")
    print("=" * 80)


async def run_latency_benchmark(num_runs: int = 100) -> FullLatencyReport:
    """Main entry point."""
    bench = LatencyBenchmark(num_runs=num_runs)
    report = await bench.run_all()
    print_latency_report(report)
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=100)
    args, _ = parser.parse_known_args()
    asyncio.run(run_latency_benchmark(args.runs))

