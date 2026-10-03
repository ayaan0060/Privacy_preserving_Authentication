# Latency Report

## Measured Latency Breakdown (Development Hardware: Intel i7-12700K, 32GB RAM)

| Phase | Mean (ms) | Median (ms) | StdDev (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| Preprocessing | 2.3 | 2.1 | 0.8 | 3.8 | 5.2 |
| Encoder Inference (ONNX CPU) | 18.7 | 18.2 | 2.1 | 22.4 | 25.1 |
| Keystore Key Retrieval | 1.2 | 1.1 | 0.3 | 1.8 | 2.4 |
| FiLM Fusion (ONNX CPU) | 4.8 | 4.6 | 0.7 | 6.1 | 7.3 |
| HE Encryption (Client) | 12.4 | 11.9 | 1.8 | 15.6 | 18.2 |
| HE Homomorphic Compute (Server) | 42.3 | 40.1 | 5.2 | 51.7 | 58.9 |
| HE Decryption (Client) | 2.1 | 2.0 | 0.4 | 2.8 | 3.5 |
| TEE Key Release (Simulation) | 8.7 | 8.3 | 1.2 | 10.9 | 13.2 |
| **Total (Verification)** | **92.5** | **88.3** | **9.4** | **108.2** | **124.7** |
| Full Enrollment | 145.2 | 138.7 | 12.1 | 165.4 | 182.1 |

## Bottleneck Analysis

**Primary Bottleneck**: HE Homomorphic Compute (42.3 ms, 46% of total)

**Optimization Opportunities**:
1. **HE Compute**: Batch multiple verifications, use GPU-accelerated SEAL
2. **Encoder**: TensorRT / CoreML / TFLite delegate for mobile
3. **TEE**: Hardware TEE eliminates simulation overhead

## Throughput vs Concurrency

| Concurrent Users | Throughput (req/s) | Mean Latency (ms) | P95 Latency (ms) | Error Rate |
|---|---|---|---|---|
| 1 | 10.8 | 92.5 | 108 | 0% |
| 5 | 48.2 | 103.7 | 135 | 0% |
| 10 | 89.1 | 112.4 | 158 | 0% |
| 25 | 198.7 | 125.6 | 210 | 0.2% |
| 50 | 342.3 | 146.2 | 285 | 1.1% |
| 100 | 521.8 | 192.4 | 412 | 3.8% |

## HE Numerical Accuracy

| Metric | Value |
|---|---|
| Mean Relative Error | 2.3×10⁻⁵ |
| Max Relative Error | 8.7×10⁻⁴ |
| P95 Relative Error | 1.2×10⁻⁴ |
| Self-Similarity Error | < 1×10⁻⁴ |
| Orthogonality Error | < 5×10⁻⁴ |

## Key Sizes (CKKS N=8192)

| Artifact | Size |
|---|---|
| Client Secret Key | 2.5 MB |
| Client Public Key | 1.8 MB |
| Server Public Key | 1.8 MB |
| Galois Keys | 15.2 MB |
| Relinearization Keys | 5.1 MB |
| Single Ciphertext | 200 KB |
