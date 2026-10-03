# Phase 4 — Homomorphic Encryption Layer (CKKS)

## Overview
Phase 4 implements privacy-preserving biometric verification using the CKKS Homomorphic Encryption scheme via TenSEAL:
- **Poly Modulus Degree**: $N = 8192$ (4096 complex slots, 256 active real slots).
- **Coefficient Modulus**: $[60, 40, 40, 60]$ (200 bits total $\rightarrow$ $\approx 128$-bit security level).
- **Global Scale**: $2^{40}$.
- **Homomorphic Computation**: Dot product / cosine similarity computed directly on ciphertexts without decrypting.

## Project Structure
```
phase4_he/
├── config.yaml
├── requirements.txt
├── README.md
├── he/
│   ├── __init__.py
│   ├── params.py               # Parameter justification & validation
│   ├── context.py              # Key management & serialization
│   ├── crypto.py               # Encrypt / Decrypt primitives
│   ├── compute.py              # Server-side homomorphic dot product
│   ├── client.py               # BiometricHEClient API
│   ├── server.py               # BiometricHEServer API
│   └── benchmarks.py           # Real performance metrics recorder
├── scripts/
│   ├── gen_keys.sh
│   └── benchmark.sh
└── tests/
    ├── test_params.py
    ├── test_crypto.py
    ├── test_compute.py
    ├── test_integration_p3.py
    └── test_benchmarks.py
```

## How to Run Phase 4

### 1. Install Dependencies (requires C++ build tools)
```bash
cd phase4_he
pip install -r requirements.txt
```

### 2. Generate Keys
```bash
./scripts/gen_keys.sh ./exports/he_keys
```

### 3. Run Unit & Integration Tests
```bash
pytest tests/ -v
```

### 4. Run Benchmarks
```bash
./scripts/benchmark.sh ./exports/he_keys ./exports/benchmark_report.json 100
```

### 5. Inspect Benchmark Report
```bash
cat ./exports/benchmark_report.json | jq .
```

## Expected Benchmark Results (Reference)

| Metric | Typical Value | Acceptance |
| :--- | :--- | :--- |
| Key Generation | 200-500 ms | One-time |
| Client Secret Key Size | ~2.5 MB | Storage |
| Client Public Key Size | ~1.8 MB | Network |
| Server Public Key Size | ~1.8 MB | Storage |
| Galois Keys | ~15 MB | Network (one-time) |
| Relinearization Keys | ~5 MB | Network (one-time) |
| Ciphertext Size | ~200 KB | Per template |
| Encryption Latency | 5-15 ms | Client |
| Decryption Latency | 1-3 ms | Client |
| Homomorphic Dot Product | 30-80 ms | Server |
| Full Roundtrip | 50-120 ms | End-to-end |
| Max Relative Error | < 1e-3 | Accuracy |
| Memory Overhead (100 ct) | 50-100 MB | Server RAM |

## Acceptance Criteria Checklist

| Criterion | Target | Verification |
| :--- | :--- | :--- |
| CKKS Parameters | N=8192, 200-bit chain, 128-bit security | `test_params.py::test_default_security_128bit` |
| Encrypt/Decrypt Roundtrip | Relative error < 1e-3 | `test_crypto.py::test_encrypt_decrypt_roundtrip` |
| Homomorphic Dot Product | Matches plaintext cosine < 1e-3 rel error | `test_compute.py::test_homomorphic_dot_vs_plaintext` |
| Self-Similarity | 1.0 ± 1e-3 | `test_compute.py::test_self_similarity_is_one` |
| Orthogonal Templates | ~0 ± 1e-3 | `test_compute.py::test_orthogonal_templates_near_zero` |
| Key Rotation Unlinkability | Cross-version similarity < 0.15 | `test_integration_p3.py::test_key_rotation_changes_template` |
| Phase 3 Integration | FiLM output → HE → correct score | `test_integration_p3.py::test_full_verification_flow` |
| Benchmark Report | Generated with all metrics | `scripts/benchmark.sh` produces JSON |

## Real vs Simulated Status

| Component | Status | Notes |
| :--- | :--- | :--- |
| CKKS Encryption | REAL | TenSEAL / Microsoft SEAL library |
| Homomorphic Computation | REAL | Actual ciphertext arithmetic |
| Key Generation | REAL | Cryptographically secure parameters |
| Numerical Accuracy | MEASURED | Benchmark relative error vs plaintext |
| Key Storage | FILESYSTEM | Dev: filesystem; Prod: TEE/HSM sealed |
| Network Transport | LOCAL CALLS | Phase 5 adds FastAPI/TLS transport |
