#!/usr/bin/env python3
"""
scripts/run_latency_benchmark.py

Directly re-measures per-component and end-to-end latencies over 1,000 fresh trials.
Covers all 8 pipeline processing stages plus directly measured end-to-end wall-clock latency:
  1. Client: CLAHE Preprocessing
  2. Client: ResNet-18 Encoder Inference
  3. Client: Keystore Retrieval
  4. Client: FiLM Modulation + ROP
  5. Client: CKKS Vector Encryption
  6. Server: Homomorphic Dot Product
  7. Client: Scalar Decryption & 1-Bit Attestation
  8. Client: Decision + Signing
Also computes exact ciphertext sizes and 4G physical transmission delays in the same run.
Saves raw samples to results/raw/latency_trials_1000.npz and results/raw/latency_summary.json.
"""

import sys
import time
import json
from pathlib import Path
import numpy as np
import tenseal as ts
import cv2
import torch
import torchvision.models as models
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
RAW_DIR = ROOT_DIR / 'results' / 'raw'
RAW_DIR.mkdir(parents=True, exist_ok=True)

DIM = 256
N_TRIALS = 1000


def main():
    print("=" * 70)
    print("RUNNING FRESH 1,000-TRIAL PER-COMPONENT & E2E LATENCY BENCHMARK")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("=" * 70)

    # 1. Initialize TenSEAL context
    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=8192,
        coeff_mod_bit_sizes=[60, 40, 40, 60]
    )
    context.generate_galois_keys()
    context.global_scale = 2**40

    # 2. Initialize Encoder & Crypto Primitives
    torch.set_num_threads(1)
    encoder = models.resnet18(num_classes=DIM)
    encoder.eval()

    signing_key = ed25519.Ed25519PrivateKey.generate()
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    from core.keys import derive_haar_matrix
    Q = derive_haar_matrix(b"latency_benchmark_seed", "user_latency", 1, DIM)

    rng = np.random.RandomState(42)

    # Pre-generate synthetic fingerprint images and enrolled vector
    raw_images = [rng.randint(0, 256, (96, 96), dtype=np.uint8) for _ in range(N_TRIALS)]
    v_enrolled = rng.randn(DIM).astype(np.float64)
    v_enrolled /= np.linalg.norm(v_enrolled)
    ct_enrolled = ts.ckks_vector(context, v_enrolled)

    # Measure exact ciphertext serializations
    dummy = ts.ckks_vector(context, [0.0] * DIM)
    probe_bytes = len(dummy.serialize())
    probe_kb = round(probe_bytes / 1024.0, 2)

    dummy_res = dummy.dot(dummy)
    res_bytes = len(dummy_res.serialize())
    res_kb = round(res_bytes / 1024.0, 2)

    print(f"Ciphertext serialization: Probe = {probe_kb} KiB, Result = {res_kb} KiB")

    # Warm-up (50 trials)
    print("Warming up JIT, caches, and memory allocations...")
    for i in range(50):
        img = clahe.apply(raw_images[i % 10])
        norm_img = img.astype(np.float32) / 255.0
        with torch.no_grad():
            x = torch.from_numpy(norm_img).unsqueeze(0).unsqueeze(0).repeat(1, 3, 1, 1)
            emb = encoder(x).squeeze(0).numpy()
        fused = Q @ emb
        fused /= np.linalg.norm(fused)
        ct_p = ts.ckks_vector(context, fused)
        ct_r = ct_enrolled.dot(ct_p)
        _ = ct_r.decrypt()
        _ = signing_key.sign(b"token:warmup")

    # Arrays for 8 stages + e2e
    times_stage1_pre = []
    times_stage2_enc = []
    times_stage3_key = []
    times_stage4_film = []
    times_stage5_he_enc = []
    times_stage6_he_dot = []
    times_stage7_he_dec = []
    times_stage8_sign = []
    times_e2e = []
    ckks_errors = []

    print(f"Executing {N_TRIALS} measured trials across all 8 pipeline stages...")
    for i in range(N_TRIALS):
        raw_img = raw_images[i]

        t_start = time.perf_counter_ns()

        # 1. CLAHE Preprocessing
        t0 = time.perf_counter_ns()
        proc_img = clahe.apply(raw_img)
        norm_img = proc_img.astype(np.float32) / 255.0
        t1 = time.perf_counter_ns()

        # 2. ResNet-18 Encoder Inference
        t2 = time.perf_counter_ns()
        with torch.no_grad():
            inp = torch.from_numpy(norm_img).unsqueeze(0).unsqueeze(0).repeat(1, 3, 1, 1)
            emb = encoder(inp).squeeze(0).numpy()
        t3 = time.perf_counter_ns()

        # 3. Keystore Retrieval (HKDF)
        t4 = time.perf_counter_ns()
        hkdf = HKDF(algorithm=hashes.SHA256(), length=64, salt=b"salt", info=f"user_{i}".encode())
        key_bytes = hkdf.derive(b"master_seed")
        seed_val = int.from_bytes(key_bytes[:4], "big")
        rng_user = np.random.RandomState(seed_val)
        key_vec = rng_user.randn(2 * DIM).astype(np.float32)
        t5 = time.perf_counter_ns()

        # 4. FiLM Modulation + ROP
        t6 = time.perf_counter_ns()
        gamma = 1.0 + 0.1 * key_vec[:DIM]
        beta = 0.1 * key_vec[DIM:2*DIM]
        fused = gamma * emb + beta
        fused /= (np.linalg.norm(fused) + 1e-12)
        proj = Q @ fused
        t7 = time.perf_counter_ns()

        # 5. CKKS Vector Encryption
        t8 = time.perf_counter_ns()
        ct_probe = ts.ckks_vector(context, proj)
        t9 = time.perf_counter_ns()

        # 6. Server Homomorphic Dot Product
        t10 = time.perf_counter_ns()
        ct_res = ct_enrolled.dot(ct_probe)
        t11 = time.perf_counter_ns()

        # 7. Client Scalar Decryption & 1-Bit Attestation
        t12 = time.perf_counter_ns()
        res_dec = ct_res.decrypt()
        decision = bool(res_dec[0] >= 0.8910)
        t13 = time.perf_counter_ns()

        # 8. Decision + Signing
        t14 = time.perf_counter_ns()
        sig = signing_key.sign(b"token:" + str(decision).encode())
        t15 = time.perf_counter_ns()

        t_end = time.perf_counter_ns()

        # Record times in ms
        s1 = (t1 - t0) / 1e6
        s2 = (t3 - t2) / 1e6
        s3 = (t5 - t4) / 1e6
        s4 = (t7 - t6) / 1e6
        s5 = (t9 - t8) / 1e6
        s6 = (t11 - t10) / 1e6
        s7 = (t13 - t12) / 1e6
        s8 = (t15 - t14) / 1e6
        tot = (t_end - t_start) / 1e6

        times_stage1_pre.append(s1)
        times_stage2_enc.append(s2)
        times_stage3_key.append(s3)
        times_stage4_film.append(s4)
        times_stage5_he_enc.append(s5)
        times_stage6_he_dot.append(s6)
        times_stage7_he_dec.append(s7)
        times_stage8_sign.append(s8)
        times_e2e.append(tot)

        # Accuracy
        plain_dot = float(np.dot(v_enrolled, proj))
        ckks_dot = float(res_dec[0])
        ckks_errors.append(abs(ckks_dot - plain_dot))

    # Convert to numpy arrays
    arr_s1 = np.array(times_stage1_pre)
    arr_s2 = np.array(times_stage2_enc)
    arr_s3 = np.array(times_stage3_key)
    arr_s4 = np.array(times_stage4_film)
    arr_s5 = np.array(times_stage5_he_enc)
    arr_s6 = np.array(times_stage6_he_dot)
    arr_s7 = np.array(times_stage7_he_dec)
    arr_s8 = np.array(times_stage8_sign)
    arr_e2e = np.array(times_e2e)
    err_arr = np.array(ckks_errors)

    # Save raw trial arrays
    npz_path = RAW_DIR / "latency_trials_1000.npz"
    np.savez_compressed(
        npz_path,
        preprocessing=arr_s1,
        encoder_inference=arr_s2,
        keystore_retrieval=arr_s3,
        film_modulation=arr_s4,
        ckks_encryption_client=arr_s5,
        ckks_dot_server=arr_s6,
        ckks_decryption_client=arr_s7,
        decision_and_signing=arr_s8,
        directly_measured_end_to_end=arr_e2e,
        errors=err_arr
    )
    print(f"[✓] Saved raw trials to {npz_path.name}")

    def stat_dict(arr):
        return {
            "median": round(float(np.median(arr)), 2),
            "p95": round(float(np.percentile(arr, 95)), 2),
            "p99": round(float(np.percentile(arr, 99)), 2),
            "mean": round(float(np.mean(arr)), 2),
            "std": round(float(np.std(arr)), 2)
        }

    components = {
        "preprocessing": stat_dict(arr_s1),
        "encoder_inference": stat_dict(arr_s2),
        "keystore_retrieval": stat_dict(arr_s3),
        "film_modulation": stat_dict(arr_s4),
        "ckks_encryption_client": stat_dict(arr_s5),
        "ckks_dot_server": stat_dict(arr_s6),
        "ckks_decryption_client": stat_dict(arr_s7),
        "decision_and_signing": stat_dict(arr_s8),
    }
    e2e_stats = stat_dict(arr_e2e)

    # 4G LTE physical delay
    uplink_delay = (probe_kb * 1024 * 8) / (15 * 10**6) * 1000.0   # 15 Mbps
    downlink_delay = (res_kb * 1024 * 8) / (30 * 10**6) * 1000.0  # 30 Mbps
    cellular_delay = round(uplink_delay + downlink_delay + 45.0, 2)
    total_mobile_e2e = round(cellular_delay + e2e_stats["median"], 2)

    summary = {
        "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "n_trials": N_TRIALS,
        "components": components,
        "directly_measured_end_to_end": e2e_stats,
        "pre_ms": components["preprocessing"],
        "enc_ms": components["ckks_encryption_client"],
        "server_dot_product_ms": components["ckks_dot_server"],
        "dec_ms": components["ckks_decryption_client"],
        "e2e_ms": e2e_stats,
        "probe_ciphertext_kb": probe_kb,
        "result_ciphertext_kb": res_kb,
        "uplink_transmission_ms": round(uplink_delay, 2),
        "downlink_transmission_ms": round(downlink_delay, 2),
        "cellular_4g_delay_ms": cellular_delay,
        "total_mobile_latency_ms": total_mobile_e2e,
        "max_abs_error": f"{float(err_arr.max()):.2e}",
        "mean_abs_error": f"{float(err_arr.mean()):.2e}"
    }

    sum_path = RAW_DIR / "latency_summary.json"
    with open(sum_path, "w") as f:
        json.dump(summary, f, indent=2)

    from scripts.provenance import record_manifest_entry
    record_manifest_entry(npz_path, Path(__file__), protocol="N/A", metadata={"desc": "1000 latency trials (8 stages + e2e)"})
    record_manifest_entry(sum_path, Path(__file__), protocol="N/A", metadata={"desc": "Latency summary metrics (8 stages + e2e)"})

    print(f"Directly Measured End-to-End: Median = {e2e_stats['median']} ms (p95 = {e2e_stats['p95']} ms, p99 = {e2e_stats['p99']} ms)")
    print(f"Server Homomorphic Dot Product: Median = {components['ckks_dot_server']['median']} ms (p95 = {components['ckks_dot_server']['p95']} ms, p99 = {components['ckks_dot_server']['p99']} ms)")
    print(f"Encoder Inference: Median = {components['encoder_inference']['median']} ms (p95 = {components['encoder_inference']['p95']} ms)")
    print(f"Total Mobile 4G Delay: {cellular_delay} ms | Total Mobile E2E: {total_mobile_e2e} ms")
    print(f"Max CKKS Error: {summary['max_abs_error']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
