# SecureFinger EER Evaluation Benchmark Report

## 1. Summary Comparison (OLD Small Sample vs. NEW Large-Scale Evaluation)

| Metric / Evaluation Scope | OLD Result (Small Sample) | NEW Large-Scale Result (FVC Protocol) | Evaluation & Protocol Notes |
| :--- | :--- | :--- | :--- |
| **Evaluation A: Encoder-Level EER** | EER: 1.85% (N=120) | **EER: 11.53% (N=5,400)** | Standard FVC pairwise evaluation (2,240 Genuine + 3,160 Impostor pairs) |
| **Evaluation B: Whole-System EER** | EER: 0.00% (N=120) | **EER: 29.54% (N=500)** | Full Encoder -> HKDF -> FiLM -> CKKS -> TEE balanced evaluation (250 Genuine + 250 Impostor) |

---

## 2. Detailed Score Distribution & Metrics

### Evaluation A: Encoder-Level (Raw Discriminability)
- **Sample Size**: N = 5,400 pairs (2,240 Genuine + 3,160 Impostor)
- **Metric**: **EER: 11.53% (N=5,400)** at threshold 0.9957
- **FAR at EER**: 11.68% | **FRR at EER**: 11.12%
- **Genuine Scores**: Min = 0.9912, Max = 1.0000, Mean = 0.9970 (std = 0.0011)
- **Impostor Scores**: Min = 0.8907, Max = 0.9990, Mean = 0.9691 (std = 0.0261)
- **Artifacts**: fvc_encoder_level_eer.json & fvc_encoder_level_det.png

### Evaluation B: Whole-System Pipeline (Full Cryptographic Pipeline)
- **Sample Size**: N = 500 balanced pairs (250 Genuine + 250 Impostor)
- **Metric**: **EER: 29.54% (N=500)** at threshold 0.9997
- **FAR at EER**: 29.54% | **FRR at EER**: 29.54%
- **Genuine Scores**: Min = 0.9999, Max = 1.0000, Mean = 1.0000 (std = 0.0001)
- **Impostor Scores**: Min = 0.9981, Max = 1.0000, Mean = 0.9995 (std = 0.0007)
- **Artifacts**: fvc_whole_system_eer.json & fvc_whole_system_det.png

---

## 3. Compliance & Verification Audit
1. **Zero Code/Weights Modified**: Existing production pipeline code (phase7_integration), model weights (fingerprint_encoder.pt), key derivation, FiLM, CKKS, and TEE modules were called READ-ONLY as a library.
2. **Reproducibility**: Pair dataset mappings are saved in eval/eer_benchmark/pairs/fvc_benchmark_pairs.csv.
3. **Metric Integrity**: Every reported EER metric explicitly includes the sample size N.
