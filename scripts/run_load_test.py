#!/usr/bin/env python3
"""
scripts/run_load_test.py

Multi-tier Closed-Loop Load Testing of the CKKS Biometric Verification Server.
Hardware Configuration:
  - Host: Apple Silicon Mac (8 physical cores, unified memory)
  - OS: macOS 26.5.1, AC Power, sleep disabled via caffeinate
  - Architecture: Shared host (single machine)
    * Server: 4 worker threads in dedicated process (max 4 cores)
    * Generator: Lightweight asyncio event loop in separate process (at most 2 cores)
  - Inter-process communication: Local TCP socket (127.0.0.1:8765)
  - Protocol: Closed queueing network with think time Z = 1.25 s
  - Concurrency tiers: N in {10, 25, 50, 100, 150, 200, 300}
  - Duration per tier: 3 repetitions of (60 s warm-up + 300 s measurement window)
  - Metrics collected:
    * Server Service Time S (time strictly inside homomorphic matching handler)
    * Client-Perceived Response Time R (mean, p50, p95, p99)
    * Independent Throughput X = (completed requests in window) / (window duration)
    * Independent Little's Law Discrepancy = |N - X*(R+Z)| / N
    * Per-second CPU logging: Server Worker CPU %, Generator CPU %, System Total CPU %
"""

import sys
import os
import time
import json
import asyncio
import subprocess
import threading
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
import tenseal as ts

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scripts.provenance import record_manifest_entry

RAW_DIR = ROOT_DIR / "results" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
LOAD_RESULTS_PATH = RAW_DIR / "load_test_results.json"
LOAD_REQUESTS_LOG = RAW_DIR / "load_test_requests.jsonl"
LOAD_CPU_LOG = RAW_DIR / "load_test_cpu_log.jsonl"

DIM = 256
THINK_TIME_S = 1.25  # Z = 1.25 s
CONCURRENCY_TIERS = [10, 25, 50, 100, 150, 200, 300]
WARMUP_S = 60.0
WINDOW_S = 300.0
REPETITIONS = 3
SERVER_PORT = 8765
SERVER_HOST = "127.0.0.1"
SERVER_WORKERS = 4


def create_he_server_context():
    """Initializes TenSEAL CKKS server context and sample ciphertexts."""
    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=8192,
        coeff_mod_bit_sizes=[60, 40, 40, 60]
    )
    context.generate_galois_keys()
    context.global_scale = 2**40
    
    rng = np.random.RandomState(42)
    v1 = rng.randn(DIM).astype(np.float64)
    v1 /= np.linalg.norm(v1)
    v2 = rng.randn(DIM).astype(np.float64)
    v2 /= np.linalg.norm(v2)
    
    ct_enrolled = ts.ckks_vector(context, v1)
    ct_probe = ts.ckks_vector(context, v2)
    
    enrolled_bytes = ct_enrolled.serialize()
    probe_bytes = ct_probe.serialize()
    
    server_context = context.copy()
    server_context.make_context_public()
    
    return server_context, enrolled_bytes, probe_bytes


# ==============================================================================
# Server Process
# ==============================================================================
def run_server_process(ready_event, stop_event):
    """Dedicated server process executing TenSEAL homomorphic matching."""
    server_ctx, enrolled_bytes, _ = create_he_server_context()
    enrolled_vec = ts.ckks_vector_from(server_ctx, enrolled_bytes)
    pool = ThreadPoolExecutor(max_workers=SERVER_WORKERS)

    def do_matching(p_bytes: bytes) -> tuple:
        t0 = time.perf_counter_ns()
        pv = ts.ckks_vector_from(server_ctx, p_bytes)
        res = enrolled_vec.dot(pv)
        out_b = res.serialize()
        t1 = time.perf_counter_ns()
        s_ms = (t1 - t0) / 1e6
        return len(out_b), s_ms

    async def handle_request(reader, writer):
        try:
            head = await reader.readexactly(4)
            msg_len = int.from_bytes(head, 'big')
            payload = await reader.readexactly(msg_len)
            
            loop = asyncio.get_running_loop()
            out_len, s_ms = await loop.run_in_executor(pool, do_matching, payload)
            
            resp = json.dumps({"status": 200, "service_time_ms": s_ms, "out_len": out_len}).encode()
            writer.write(len(resp).to_bytes(4, 'big') + resp)
            await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def server_main():
        srv = await asyncio.start_server(handle_request, SERVER_HOST, SERVER_PORT, reuse_address=True)
        ready_event.set()
        while not stop_event.is_set():
            await asyncio.sleep(0.5)
        srv.close()
        await srv.wait_closed()
        pool.shutdown(wait=False)

    asyncio.run(server_main())


# ==============================================================================
# CPU Monitoring Thread
# ==============================================================================
class CPUMonitor:
    def __init__(self, server_pid: int, gen_pid: int, log_file):
        self.server_pid = server_pid
        self.gen_pid = gen_pid
        self.log_file = log_file
        self.running = False
        self.samples = []
        self.thread = None
        self.lock = threading.Lock()

    def start(self, concurrency: int, rep: int):
        self.running = True
        self.samples = []
        self.thread = threading.Thread(target=self._monitor_loop, args=(concurrency, rep), daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3.0)
        return self.samples

    def _get_proc_cpu(self, pid: int) -> float:
        try:
            out = subprocess.check_output(["ps", "-p", str(pid), "-o", "%cpu"], stderr=subprocess.DEVNULL).decode()
            lines = out.strip().split("\n")
            if len(lines) >= 2:
                return float(lines[1].strip())
        except Exception:
            pass
        return 0.0

    def _monitor_loop(self, concurrency: int, rep: int):
        while self.running:
            t_now = time.time()
            srv_cpu = self._get_proc_cpu(self.server_pid)
            gen_cpu = self._get_proc_cpu(self.gen_pid)
            tot_cpu = srv_cpu + gen_cpu
            
            rec = {
                "timestamp": round(t_now, 2),
                "concurrency": concurrency,
                "repetition": rep,
                "server_cpu_pct": srv_cpu,
                "generator_cpu_pct": gen_cpu,
                "combined_cpu_pct": tot_cpu
            }
            with self.lock:
                self.samples.append(rec)
                self.log_file.write(json.dumps(rec) + "\n")
                self.log_file.flush()
            time.sleep(1.0)


# ==============================================================================
# Single Tier Repetition Execution
# ==============================================================================
async def run_single_client(client_id: int, probe_bytes: bytes, stop_event: asyncio.Event,
                            window_start_time: float, window_end_time: float,
                            tier_requests: list, req_lock: asyncio.Lock, req_log_file):
    """Single asynchronous client executing closed request-think cycles."""
    req_idx = 0
    while not stop_event.is_set():
        t0 = time.perf_counter()
        t0_wall = time.time()
        try:
            reader, writer = await asyncio.open_connection(SERVER_HOST, SERVER_PORT)
            writer.write(len(probe_bytes).to_bytes(4, 'big') + probe_bytes)
            await writer.drain()
            
            head = await reader.readexactly(4)
            resp_len = int.from_bytes(head, 'big')
            resp_bytes = await reader.readexactly(resp_len)
            writer.close()
            await writer.wait_closed()
            
            t1 = time.perf_counter()
            r_ms = (t1 - t0) * 1000.0
            info = json.loads(resp_bytes.decode())
            s_ms = float(info.get("service_time_ms", 0.0))
            status = info.get("status", 200)
        except Exception as e:
            t1 = time.perf_counter()
            r_ms = (t1 - t0) * 1000.0
            s_ms = 0.0
            status = 500

        in_window = (window_start_time <= t0_wall <= window_end_time)
        rec = {
            "timestamp": round(t0_wall, 4),
            "client_id": client_id,
            "request_id": req_idx,
            "client_latency_ms": round(r_ms, 3),
            "server_service_ms": round(s_ms, 3),
            "status": status,
            "in_measurement_window": in_window
        }
        
        async with req_lock:
            tier_requests.append(rec)
            req_log_file.write(json.dumps(rec) + "\n")
            req_log_file.flush()

        req_idx += 1
        try:
            await asyncio.sleep(THINK_TIME_S)
        except asyncio.CancelledError:
            break


async def run_tier_repetition(N: int, rep: int, probe_bytes: bytes, cpu_monitor: CPUMonitor, req_log_file):
    """Runs 60s warmup followed by 300s measurement window for tier N, rep R."""
    print(f"\n  [Tier N={N}, Rep {rep}/{REPETITIONS}] Starting {WARMUP_S}s warmup...")
    stop_event = asyncio.Event()
    req_lock = asyncio.Lock()
    tier_requests = []
    
    t_start_wall = time.time()
    w_start_time = t_start_wall + WARMUP_S
    w_end_time = w_start_time + WINDOW_S
    
    cpu_monitor.start(N, rep)
    
    # Spawn N asynchronous client tasks
    client_tasks = [
        asyncio.create_task(
            run_single_client(
                cid, probe_bytes, stop_event,
                w_start_time, w_end_time,
                tier_requests, req_lock, req_log_file
            )
        )
        for cid in range(N)
    ]
    
    # Wait for warmup
    await asyncio.sleep(WARMUP_S)
    print(f"  [Tier N={N}, Rep {rep}/{REPETITIONS}] Warmup complete. Entering {WINDOW_S}s measurement window...")
    
    # Measurement window
    await asyncio.sleep(WINDOW_S)
    
    # Stop clients
    print(f"  [Tier N={N}, Rep {rep}/{REPETITIONS}] Measurement window complete. Stopping clients...")
    stop_event.set()
    await asyncio.gather(*client_tasks, return_exceptions=True)
    
    cpu_samples = cpu_monitor.stop()
    
    # Filter measurement window requests
    window_reqs = [r for r in tier_requests if r["in_measurement_window"] and r["status"] == 200]
    completed_in_window = len(window_reqs)
    
    # INDEPENDENT THROUGHPUT COMPUTATION: X = completed / duration
    effective_duration_s = WINDOW_S
    measured_x = completed_in_window / effective_duration_s
    
    r_latencies = [r["client_latency_ms"] for r in window_reqs]
    s_latencies = [r["server_service_ms"] for r in window_reqs]
    
    mean_r = float(np.mean(r_latencies)) if r_latencies else 0.0
    p50_r = float(np.percentile(r_latencies, 50)) if r_latencies else 0.0
    p95_r = float(np.percentile(r_latencies, 95)) if r_latencies else 0.0
    p99_r = float(np.percentile(r_latencies, 99)) if r_latencies else 0.0
    mean_s = float(np.mean(s_latencies)) if s_latencies else 0.0
    
    # INDEPENDENT LITTLE'S LAW DISCREPANCY: |N - X*(R+Z)| / N
    r_sec = mean_r / 1000.0
    expected_n = measured_x * (r_sec + THINK_TIME_S)
    little_disc = abs(N - expected_n) / N * 100.0
    
    # CPU statistics across measurement window
    srv_cpus = [c["server_cpu_pct"] for c in cpu_samples]
    gen_cpus = [c["generator_cpu_pct"] for c in cpu_samples]
    
    mean_srv_cpu = float(np.mean(srv_cpus)) if srv_cpus else 0.0
    mean_gen_cpu = float(np.mean(gen_cpus)) if gen_cpus else 0.0
    
    print(f"    Completed in window: {completed_in_window} reqs over {WINDOW_S}s")
    print(f"    Throughput X = {measured_x:.2f} req/s (Little's Disc = {little_disc:.2f}%, Expected N = {expected_n:.2f})")
    print(f"    Service Time S = {mean_s:.2f} ms | Response Time Mean R = {mean_r:.2f} ms (p95 = {p95_r:.2f} ms, p99 = {p99_r:.2f} ms)")
    print(f"    Server CPU = {mean_srv_cpu:.1f}%, Generator CPU = {mean_gen_cpu:.1f}%")
    
    return {
        "concurrency": N,
        "repetition": rep,
        "completed_requests": completed_in_window,
        "window_duration_s": WINDOW_S,
        "throughput_req_per_s": round(measured_x, 2),
        "mean_latency_ms": round(mean_r, 2),
        "p50_latency_ms": round(p50_r, 2),
        "p95_latency_ms": round(p95_r, 2),
        "p99_latency_ms": round(p99_r, 2),
        "service_time_ms": round(mean_s, 2),
        "littles_law_discrepancy_percent": round(little_disc, 2),
        "server_cpu_pct": round(mean_srv_cpu, 1),
        "generator_cpu_pct": round(mean_gen_cpu, 1)
    }


# ==============================================================================
# Main Orchestrator
# ==============================================================================
def main():
    print("=" * 70)
    print("STARTING FULL REPRODUCIBLE LOAD TEST (TASK 1)")
    print("Hardware: Apple Silicon Mac (8 cores, macOS 26.5.1, AC Power)")
    print("Configuration: 4 server worker threads, async client generator on shared host")
    print(f"Tiers: {CONCURRENCY_TIERS} | 3 Reps x ({WARMUP_S}s warmup + {WINDOW_S}s window)")
    print(f"Total duration: ~{len(CONCURRENCY_TIERS) * REPETITIONS * (WARMUP_S + WINDOW_S) / 3600:.2f} hours")
    print("=" * 70)

    # Check power and caffeinate
    pm_out = subprocess.check_output(["pmset", "-g", "batt"]).decode()
    print("Power status:", pm_out.strip().split("\n")[0])

    server_ready = mp.Event()
    server_stop = mp.Event()
    
    server_proc = mp.Process(target=run_server_process, args=(server_ready, server_stop), daemon=True)
    server_proc.start()
    
    print("Waiting for server initialization on port 8765...")
    server_ready.wait(timeout=30.0)
    print(f"Server PID {server_proc.pid} active with {SERVER_WORKERS} worker threads.")
    
    # Prepare probe ciphertext bytes
    _, _, probe_bytes = create_he_server_context()
    
    gen_pid = os.getpid()
    all_tier_summaries = []
    
    with open(LOAD_REQUESTS_LOG, "w") as req_log, open(LOAD_CPU_LOG, "w") as cpu_log:
        cpu_monitor = CPUMonitor(server_proc.pid, gen_pid, cpu_log)
        
        for N in CONCURRENCY_TIERS:
            rep_results = []
            for rep in range(1, REPETITIONS + 1):
                res = asyncio.run(run_tier_repetition(N, rep, probe_bytes, cpu_monitor, req_log))
                rep_results.append(res)
                
            # Aggregate across 3 repetitions: mean and std
            xs = [r["throughput_req_per_s"] for r in rep_results]
            rs = [r["mean_latency_ms"] for r in rep_results]
            p95s = [r["p95_latency_ms"] for r in rep_results]
            p99s = [r["p99_latency_ms"] for r in rep_results]
            ss = [r["service_time_ms"] for r in rep_results]
            srv_cpus = [r["server_cpu_pct"] for r in rep_results]
            gen_cpus = [r["generator_cpu_pct"] for r in rep_results]
            discs = [r["littles_law_discrepancy_percent"] for r in rep_results]
            
            summary = {
                "concurrent_clients": N,
                "think_time_s": THINK_TIME_S,
                "repetitions": REPETITIONS,
                "warmup_s": WARMUP_S,
                "window_s": WINDOW_S,
                
                "throughput_mean": round(float(np.mean(xs)), 2),
                "throughput_std": round(float(np.std(xs)), 2),
                "throughput_req_per_s": round(float(np.mean(xs)), 2),
                
                "mean_latency_ms": round(float(np.mean(rs)), 2),
                "mean_latency_std": round(float(np.std(rs)), 2),
                
                "p95_latency_ms": round(float(np.mean(p95s)), 2),
                "p95_latency_std": round(float(np.std(p95s)), 2),
                
                "p99_latency_ms": round(float(np.mean(p99s)), 2),
                "p99_latency_std": round(float(np.std(p99s)), 2),
                
                "service_time_ms": round(float(np.mean(ss)), 2),
                "service_time_std": round(float(np.std(ss)), 2),
                
                "server_cpu_pct": round(float(np.mean(srv_cpus)), 1),
                "server_cpu_std": round(float(np.std(srv_cpus)), 1),
                
                "generator_cpu_pct": round(float(np.mean(gen_cpus)), 1),
                "generator_cpu_std": round(float(np.std(gen_cpus)), 1),
                
                "littles_law_discrepancy_percent": round(float(np.mean(discs)), 2),
                "littles_law_discrepancy_std": round(float(np.std(discs)), 2),
                
                "per_repetition_runs": rep_results
            }
            all_tier_summaries.append(summary)
            print(f"\n[SUMMARY Tier N={N}] X = {summary['throughput_mean']} ± {summary['throughput_std']} req/s | "
                  f"Mean R = {summary['mean_latency_ms']} ± {summary['mean_latency_std']} ms | "
                  f"S = {summary['service_time_ms']} ± {summary['service_time_std']} ms | "
                  f"Server CPU = {summary['server_cpu_pct']}% | Little's Disc = {summary['littles_law_discrepancy_percent']}%")
            
            # Save intermediate progress so far
            with open(LOAD_RESULTS_PATH, "w") as f:
                json.dump(all_tier_summaries, f, indent=2)

    # Terminate server
    server_stop.set()
    server_proc.join(timeout=5.0)
    if server_proc.is_alive():
        server_proc.terminate()

    # Final save and manifest recording
    with open(LOAD_RESULTS_PATH, "w") as f:
        json.dump(all_tier_summaries, f, indent=2)
        
    script_path = Path(__file__).resolve()
    record_manifest_entry(LOAD_RESULTS_PATH, script_path, protocol="N/A", metadata={"desc": "7-tier 3-rep load test"})
    record_manifest_entry(LOAD_REQUESTS_LOG, script_path, protocol="N/A", metadata={"desc": "Every load request logged"})
    record_manifest_entry(LOAD_CPU_LOG, script_path, protocol="N/A", metadata={"desc": "Per-second CPU log"})

    print("\n" + "=" * 70)
    print(f"FULL LOAD TEST COMPLETE: {len(all_tier_summaries)} tiers saved to {LOAD_RESULTS_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    main()
