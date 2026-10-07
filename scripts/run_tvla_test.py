#!/usr/bin/env python3
"""
scripts/run_tvla_test.py

Executes a real 10,000-trial Test Vector Leakage Assessment (TVLA) under fresh encryptions:
- 5,000 fixed-input trials (Group A)
- 5,000 random-input trials (Group B)

Evaluates:
(a) Server-side CKKS homomorphic dot product (TenSEAL / Microsoft SEAL)
(b) Client-side CKKS vector encryption

Computes Welch's t-test, Mann-Whitney U, Kolmogorov-Smirnov, F-test of variances,
and latency percentiles (99th, 99.9th).
Outputs results to results/raw/tvla_10k_results.json.
"""

import sys
import time
import json
from pathlib import Path
import numpy as np
from scipy import stats
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import tenseal as ts
from scripts.provenance import record_manifest_entry

RAW_DIR = ROOT_DIR / "results" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

MASTER_SEED = 42
DIM = 256
TRIALS_PER_GROUP = 5000
TOTAL_TRIALS = TRIALS_PER_GROUP * 2

def create_ckks_context():
    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=8192,
        coeff_mod_bit_sizes=[60, 40, 40, 60]
    )
    context.generate_galois_keys()
    context.global_scale = 2**40
    return context

def run_tvla():
    print(f"=== Starting 10,000-Trial Fresh-Encryption TVLA Experiment ===")
    print(f"Configuration: {TRIALS_PER_GROUP} fixed vs {TRIALS_PER_GROUP} random trials")
    print(f"Dimension: {DIM}, Poly modulus degree: 8192")

    context = create_ckks_context()
    rng = np.random.RandomState(MASTER_SEED)

    # 1. Fixed vector: normalized all-ones
    v_fixed = np.ones(DIM, dtype=np.float64) / np.sqrt(DIM)
    # Reference vector for server dot
    v_ref = np.ones(DIM, dtype=np.float64) / np.sqrt(DIM)

    # Prepare random vectors
    print("Generating random test vectors...")
    random_vectors = []
    for _ in range(TRIALS_PER_GROUP):
        vr = rng.randn(DIM).astype(np.float64)
        vr /= np.linalg.norm(vr)
        random_vectors.append(vr)

    # Pre-encrypt ciphertexts for server dot product to measure purely the homomorphic dot
    print("Pre-encrypting ciphertexts for server dot product TVLA...")
    c_ref = ts.ckks_vector(context, v_ref)
    
    # Generate fresh encryptions for fixed and random groups
    # Group A: fresh encryptions of fixed vector
    # Group B: fresh encryptions of random vectors
    fixed_ciphertexts = [ts.ckks_vector(context, v_fixed) for _ in range(TRIALS_PER_GROUP)]
    random_ciphertexts = [ts.ckks_vector(context, random_vectors[i]) for i in range(TRIALS_PER_GROUP)]

    # Interleave trials randomly to prevent temporal drift bias
    # label 0 = fixed (Group A), 1 = random (Group B)
    labels = np.array([0] * TRIALS_PER_GROUP + [1] * TRIALS_PER_GROUP)
    perm = rng.permutation(TOTAL_TRIALS)
    labels_interleaved = labels[perm]

    # Map indices
    fixed_idx = 0
    rand_idx = 0

    print("\n--- (a) Measuring Server CKKS Dot Product Latency (10,000 trials) ---")
    dot_fixed_times_ms = []
    dot_random_times_ms = []

    # Warmup
    for _ in range(50):
        _ = c_ref.dot(fixed_ciphertexts[0])

    t_start = time.perf_counter()
    for trial_i, label in enumerate(labels_interleaved):
        if label == 0:
            c_target = fixed_ciphertexts[fixed_idx]
            fixed_idx += 1
            t0 = time.perf_counter_ns()
            _ = c_ref.dot(c_target)
            t1 = time.perf_counter_ns()
            dot_fixed_times_ms.append((t1 - t0) / 1e6)
        else:
            c_target = random_ciphertexts[rand_idx]
            rand_idx += 1
            t0 = time.perf_counter_ns()
            _ = c_ref.dot(c_target)
            t1 = time.perf_counter_ns()
            dot_random_times_ms.append((t1 - t0) / 1e6)

        if (trial_i + 1) % 2000 == 0:
            print(f"  Server dot completed {trial_i + 1}/{TOTAL_TRIALS} trials ({time.perf_counter() - t_start:.1f} s)...")

    dot_fixed = np.array(dot_fixed_times_ms)
    dot_random = np.array(dot_random_times_ms)

    print("\n--- (b) Measuring Client CKKS Encryption Latency (10,000 trials) ---")
    enc_fixed_times_ms = []
    enc_random_times_ms = []

    # Warmup
    for _ in range(50):
        _ = ts.ckks_vector(context, v_fixed)

    t_start = time.perf_counter()
    rand_idx = 0
    for trial_i, label in enumerate(labels_interleaved):
        if label == 0:
            t0 = time.perf_counter_ns()
            _ = ts.ckks_vector(context, v_fixed)
            t1 = time.perf_counter_ns()
            enc_fixed_times_ms.append((t1 - t0) / 1e6)
        else:
            vr = random_vectors[rand_idx]
            rand_idx += 1
            t0 = time.perf_counter_ns()
            _ = ts.ckks_vector(context, vr)
            t1 = time.perf_counter_ns()
            enc_random_times_ms.append((t1 - t0) / 1e6)

        if (trial_i + 1) % 2000 == 0:
            print(f"  Client enc completed {trial_i + 1}/{TOTAL_TRIALS} trials ({time.perf_counter() - t_start:.1f} s)...")

    enc_fixed = np.array(enc_fixed_times_ms)
    enc_random = np.array(enc_random_times_ms)

    def analyze_group(fixed, random, name):
        n_a, n_b = len(fixed), len(random)
        mean_a, mean_b = float(np.mean(fixed)), float(np.mean(random))
        std_a, std_b = float(np.std(fixed, ddof=1)), float(np.std(random, ddof=1))
        var_a, var_b = float(np.var(fixed, ddof=1)), float(np.var(random, ddof=1))

        # Welch's t-test
        t_stat, p_welch = stats.ttest_ind(fixed, random, equal_var=False)

        # Mann-Whitney U test
        u_stat, p_mw = stats.mannwhitneyu(fixed, random, alternative='two-sided')

        # Kolmogorov-Smirnov 2-sample test
        ks_stat, p_ks = stats.ks_2samp(fixed, random)

        # F-test for equality of variances
        f_stat = var_a / var_b if var_b > 0 else 1.0
        # Two-tailed F-test p-value
        p_f = 2.0 * min(stats.f.cdf(f_stat, n_a - 1, n_b - 1), 1.0 - stats.f.cdf(f_stat, n_a - 1, n_b - 1))

        # Percentiles
        p99_a, p99_b = float(np.percentile(fixed, 99)), float(np.percentile(random, 99))
        p999_a, p999_b = float(np.percentile(fixed, 99.9)), float(np.percentile(random, 99.9))

        res = {
            "name": name,
            "trials_per_group": TRIALS_PER_GROUP,
            "total_trials": TOTAL_TRIALS,
            "group_fixed_mean_ms": round(mean_a, 4),
            "group_fixed_std_ms": round(std_a, 4),
            "group_fixed_var_ms2": round(var_a, 4),
            "group_random_mean_ms": round(mean_b, 4),
            "group_random_std_ms": round(std_b, 4),
            "group_random_var_ms2": round(var_b, 4),
            "mean_diff_ms": round(mean_a - mean_b, 4),
            "welch_t_stat": round(float(t_stat), 4),
            "welch_p_value": round(float(p_welch), 4),
            "mann_whitney_u": float(u_stat),
            "mann_whitney_p_value": round(float(p_mw), 4),
            "ks_statistic": round(float(ks_stat), 4),
            "ks_p_value": round(float(p_ks), 4),
            "f_variance_ratio": round(float(f_stat), 4),
            "f_test_p_value": round(float(p_f), 4),
            "group_fixed_p99_ms": round(p99_a, 4),
            "group_random_p99_ms": round(p99_b, 4),
            "group_fixed_p999_ms": round(p999_a, 4),
            "group_random_p999_ms": round(p999_b, 4),
            "tvla_threshold_pass": bool(abs(t_stat) < 4.5)
        }
        return res

    server_stats = analyze_group(dot_fixed, dot_random, "TenSEAL CKKS Server Dot Product")
    client_stats = analyze_group(enc_fixed, enc_random, "TenSEAL CKKS Client Encryption")

    out_data = {
        "metadata": {
            "master_seed": MASTER_SEED,
            "trials_per_group": TRIALS_PER_GROUP,
            "total_trials": TOTAL_TRIALS,
            "poly_modulus_degree": 8192,
            "coeff_mod_bit_sizes": [60, 40, 40, 60],
            "scale_bits": 40,
            "vector_dimension": DIM
        },
        "server_dot_product": server_stats,
        "client_encryption": client_stats
    }

    out_file = RAW_DIR / "tvla_10k_results.json"
    with open(out_file, "w") as f:
        json.dump(out_data, f, indent=2)

    trials_npz = RAW_DIR / "tvla_10k_trials.npz"
    np.savez_compressed(
        trials_npz,
        dot_fixed=dot_fixed,
        dot_random=dot_random,
        enc_fixed=enc_fixed,
        enc_random=enc_random,
        labels=labels_interleaved
    )

    record_manifest_entry(out_file, Path(__file__), protocol="N/A", seed=MASTER_SEED)
    record_manifest_entry(trials_npz, Path(__file__), protocol="N/A", seed=MASTER_SEED)

    print(f"\nSaved 10,000-trial TVLA results to {out_file} and {trials_npz}")
    print("\n--- Summary ---")
    print(f"Server Dot:  t = {server_stats['welch_t_stat']:.2f}, p = {server_stats['welch_p_value']:.4f}, Mean Diff = {server_stats['mean_diff_ms']:.4f} ms, Fixed Var = {server_stats['group_fixed_var_ms2']:.4f}, Random Var = {server_stats['group_random_var_ms2']:.4f}, F = {server_stats['f_variance_ratio']:.4f}")
    print(f"Client Enc:  t = {client_stats['welch_t_stat']:.2f}, p = {client_stats['welch_p_value']:.4f}, Mean Diff = {client_stats['mean_diff_ms']:.4f} ms, Fixed Var = {client_stats['group_fixed_var_ms2']:.4f}, Random Var = {client_stats['group_random_var_ms2']:.4f}, F = {client_stats['f_variance_ratio']:.4f}")

if __name__ == "__main__":
    run_tvla()
