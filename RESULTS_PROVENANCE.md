# Results Provenance Matrix (Single Source of Truth)

This document provides a strict, verifiable mapping between every quantitative macro generated in `results/final/macros.tex` (and utilized in `paper.tex` and `Research.tex`), the underlying execution script, raw output artifact in `results/final/`, random seeds, and evaluation configurations.

All results are regenerated automatically via a single command:
```bash
make reproduce && make verify
```

---

## 1. Headline Accuracy, Verification, and Representation Schemes

- **Master Output File:** `results/final/metrics.json`
- **Raw Array Artifacts:** `results/final/verification_arrays.npz`
- **Generating Script:** `scripts/run_all_experiments.py` (Step 2: `run_verification_eval`)
- **Evaluation Set:** Held-out SOCOFing test split (90 subjects, 900 unique identities, 8,227 images: 900 real, 2,687 easy, 2,551 medium, 2,089 hard).
- **Pair Protocol:** 10,000 pairs (5,000 mated genuine, 5,000 non-mated impostor). Seeds: 42, 123, 456.

| Macro | Value in Paper | Source Field in `metrics.json` | Provenance / Methodology |
| :--- | :--- | :--- | :--- |
| `\HeadlineEER` | $2.89\%$ | `verification.headline_eer` | Single-seed canonical EER on held-out test split |
| `\HeadlineEERCILow` | $2.57\%$ | `verification.headline_eer_ci_lower` | 1,000-iteration non-parametric bootstrap 95% CI lower bound |
| `\HeadlineEERCIHigh` | $3.24\%$ | `verification.headline_eer_ci_upper` | 1,000-iteration non-parametric bootstrap 95% CI upper bound |
| `\MultiSeedEER` | $2.96\% \pm 0.05\%$ | Multi-seed evaluation | Mean $\pm$ std across seeds 42, 123, and 456 |
| `\OperatingThresholdTau` | $0.9218$ | `verification.tau_threshold` | Operating threshold selected at validation EER |
| `\NominalTestFAR` | $2.88\%$ | `verification.nominal_test_far` | Empirical FAR evaluated on nominal test set at $\tau$ |
| `\NominalTestFRR` | $2.90\%$ | `verification.nominal_test_frr` | Empirical FRR evaluated on nominal test set at $\tau$ |
| `\ROPIsometryMaxDiff` | $1.79 \times 10^{-7}$ | `verification.rop_isometry_max_diff` | Max $|s_{\text{ROP}} - s_{\text{plaintext}}|$ confirming isometric inner-product preservation |
| `\GenuineMean` | $0.979$ | `verification.schemes.rop.stolen_key.genuine_mean` | Genuine pair cosine similarity mean ($\sigma = 0.022$) |
| `\StolenImpostorMean` | $0.797$ | `verification.schemes.rop.stolen_key.impostor_mean` | Stolen-key impostor cosine similarity mean ($\sigma = 0.081$) |
| `\DPrimeStolen` | $3.05$ | `verification.schemes.rop.stolen_key.d_prime` | Decidability index under stolen-key condition |
| `\TARAtFAROnePct` | $94.58\%$ | `verification.schemes.rop.stolen_key.TAR_at_FAR_1pct` | True Accept Rate at 1.0% False Accept Rate |
| `\TARAtFARZeroOnePct` | $79.46\%$ | `verification.schemes.rop.stolen_key.TAR_at_FAR_01pct` | True Accept Rate at 0.1% False Accept Rate |
| `\LegitImpostorMean` | $-0.001$ | `verification.schemes.rop.legitimate_key.impostor_mean` | Cross-user legitimate-key impostor mean ($\sigma = 0.062$) |
| `\DPrimeLegit` | $20.92$ | `verification.schemes.rop.legitimate_key.d_prime` | Decidability index under legitimate-key token decorrelation |
| `\LegitEER` | $0.00\%$ | `verification.schemes.rop.legitimate_key.EER_percent` | Legitimate-key EER (known token decorrelation artifact) |
| `\CrossEntropyEER` | $7.19\%$ | Cross-entropy baseline | EER of unconstrained cross-entropy ResNet-18 ($\pm 0.09\%$) |
| `\RankOneStolen` | $96.8\%$ | Identification test | 1:$N$ closed-set Rank-1 identification accuracy (stolen-key mode) |
| `\RankOneLegit` | $98.9\%$ | Identification test | 1:$N$ closed-set Rank-1 identification accuracy (legitimate-key mode) |
| `\PlaintextEER` | $2.89\%$ | `verification.schemes.plaintext.stolen_key.EER_percent` | Baseline ArcFace ResNet-18 stolen-key EER |
| `\SignOnlyEER` | $2.89\%$ | `verification.schemes.sign_only.stolen_key.EER_percent` | Random bipolar sign flips stolen-key EER |
| `\SignPermEER` | $2.89\%$ | `verification.schemes.sign_permutation.stolen_key.EER_percent` | Sign flips + permutation stolen-key EER |
| `\FiLMOnlyEER` | $3.00\%$ | `verification.schemes.film_only.stolen_key.EER_percent` | Continuous FiLM modulation (no signs) stolen-key EER |
| `\BipolarFiLMEER` | $2.95\%$ | `verification.schemes.bipolar_film.stolen_key.EER_percent` | Bipolar FiLM modulation stolen-key EER |
| `\BioHashingEER` | $4.26\%$ | `verification.schemes.biohashing.stolen_key.EER_percent` | BioHashing ($M=256$) stolen-key EER |
| `\IoMEER` | $5.46\%$ | `verification.schemes.iom.stolen_key.EER_percent` | Index-of-Max ($K=64, M=8$) stolen-key EER |

---

## 2. Dataset Audit & File Counts

- **Generating Script:** `scripts/run_all_experiments.py` (Step 1: `audit_dataset`)
- **Root Path:** `data/SOCOFing`

| Macro | Value in Paper | Source Field in `metrics.json` | Provenance |
| :--- | :--- | :--- | :--- |
| `\DiskRealCount` | $6,000$ | `dataset.disk_real_count` | Physical files on disk under `Real/` |
| `\DiskEasyCount` | $17,931$ | `dataset.disk_altered_easy_count` | Physical files on disk under `Altered/Altered-Easy/` |
| `\DiskMedCount` | $17,067$ | `dataset.disk_altered_medium_count` | Physical files on disk under `Altered/Altered-Medium/` |
| `\DiskHardCount` | $14,272$ | `dataset.disk_altered_hard_count` | Physical files on disk under `Altered/Altered-Hard/` |
| `\DiskTotalAltered`| $49,270$ | `dataset.disk_total_altered_count` | Total altered files on disk |
| `\DiskTotalDataset`| $55,270$ | `dataset.disk_total_dataset_count` | Total images found on disk |
| `\PublishedDatasetCount` | $55,273$ | `dataset.published_dataset_count` | Officially published SOCOFing count |
| `\DiscrepancyCount` | $3$ | `dataset.discrepancy_count` | 3 missing/unreadable files documented in paper |
| `\TestRealCount` | $900$ | `dataset.test_real_count` | Real impressions in held-out test split |
| `\TestEasyCount` | $2,687$ | `dataset.test_altered_easy_count` | Easy impressions in held-out test split |
| `\TestMedCount` | $2,551$ | `dataset.test_altered_medium_count` | Medium impressions in held-out test split |
| `\TestHardCount` | $2,089$ | `dataset.test_altered_hard_count` | Hard impressions in held-out test split |
| `\TestTotalImages` | $8,227$ | `dataset.test_total_images` | Total test images |
| `\TestSubjectsCount`| $90$ | `dataset.test_subjects_count` | Held-out test subjects (900 identities) |

---

## 3. ISO/IEC 24745 Unlinkability & Attack Benchmarks

- **Master Output File:** `results/final/metrics.json`
- **Raw Array Artifacts:** `results/final/unlinkability_arrays.npz`
- **Generating Script:** `scripts/run_all_experiments.py` (Step 3: `run_unlinkability_eval`)
- **Pairs Evaluated:** 10,000 mated pairs (two DIFFERENT impressions of the same subject under independent random keys) and 10,000 non-mated pairs (different subjects, verified `id_a != id_b`).
- **Null Calibration:** 1,000 label-permutation shuffles estimating finite-sample histogram noise floor.

| Macro | Value in Paper | Source Field in `metrics.json` | Provenance |
| :--- | :--- | :--- | :--- |
| `\NullNoiseFloorMean` | $0.0249$ | `unlinkability.null_noise_floor_mean` | Permutation null distribution mean |
| `\NullNoiseFloorP` | $0.0291$ | `unlinkability.null_noise_floor_p95` | Permutation null distribution 95th percentile |
| `\SameServiceAUC` | $0.9956$ | `unlinkability.same_service_linkability_auc` | Same-key within-service linkage AUC (inner products preserved) |
| `\ROPCosAUC` | $0.5015$ | `unlinkability.unlinkability_table.rop.auc_cosine` | ROP Cosine linkage AUC |
| `\ROPAbsAUC` | $0.5031$ | `unlinkability.unlinkability_table.rop.auc_abs_val` | ROP Absolute-value linkage AUC |
| `\ROPSortAUC` | $0.5053$ | `unlinkability.unlinkability_table.rop.auc_sort_mag` | ROP Sorted-magnitude linkage AUC |
| `\ROPLearnedAUC` | $0.5121$ | `unlinkability.unlinkability_table.rop.auc_learned_mlp` | ROP Learned neural MLP linkage AUC |
| `\ROPWorstDsys` | $0.0275$ | `unlinkability.unlinkability_table.rop.D_sys_worst` | ROP Worst-case $D_{\leftrightarrow}^{\mathit{sys}}$ ($\le \text{Null } p_{95} = 0.0291$) |
| `\ROPWorstOmega` | $0.9725$ | `unlinkability.unlinkability_table.rop.omega_worst` | ROP Worst-case overlap metric $\Omega$ |
| `\SignOnlyCosAUC` | $0.5020$ | `unlinkability.unlinkability_table.sign_only.auc_cosine` | Sign Flips Cosine linkage AUC |
| `\SignOnlyAbsAUC` | $0.9595$ | `unlinkability.unlinkability_table.sign_only.auc_abs_val` | Sign Flips Abs-Val linkage AUC (magnitude leak) |
| `\SignOnlySortAUC`| $0.7170$ | `unlinkability.unlinkability_table.sign_only.auc_sort_mag` | Sign Flips Sorted-magnitude linkage AUC |
| `\SignOnlyLearnedAUC`| $0.9577$ | `unlinkability.unlinkability_table.sign_only.auc_learned_mlp` | Sign Flips Learned MLP linkage AUC |
| `\SignOnlyWorstDsys`| $0.7452$ | `unlinkability.unlinkability_table.sign_only.D_sys_worst` | Sign Flips Worst-case $D_{\leftrightarrow}^{\mathit{sys}}$ |
| `\SignPermAbsAUC` | $0.5000$ | `unlinkability.unlinkability_table.sign_permutation.auc_abs_val` | Sign + Permutation Abs-Val linkage AUC |
| `\SignPermSortAUC`| $0.7170$ | `unlinkability.unlinkability_table.sign_permutation.auc_sort_mag` | Sign + Permutation Sorted-Mag linkage AUC (multiset leak) |
| `\SignPermLearnedAUC`| $0.7170$ | `unlinkability.unlinkability_table.sign_permutation.auc_learned_mlp` | Sign + Permutation Learned MLP linkage AUC |
| `\SignPermWorstDsys`| $0.2402$ | `unlinkability.unlinkability_table.sign_permutation.D_sys_worst` | Sign + Permutation Worst-case $D_{\leftrightarrow}^{\mathit{sys}}$ |
| `\FiLMAbsAUC` | $0.9448$ | `unlinkability.unlinkability_table.bipolar_film.auc_abs_val` | Bipolar FiLM Abs-Val linkage AUC |
| `\FiLMSortAUC` | $0.5493$ | `unlinkability.unlinkability_table.bipolar_film.auc_sort_mag` | Bipolar FiLM Sorted-Mag linkage AUC |
| `\FiLMLearnedAUC` | $0.9448$ | `unlinkability.unlinkability_table.bipolar_film.auc_learned_mlp` | Bipolar FiLM Learned MLP linkage AUC |
| `\FiLMWorstDsys` | $0.6955$ | `unlinkability.unlinkability_table.bipolar_film.D_sys_worst` | Bipolar FiLM Worst-case $D_{\leftrightarrow}^{\mathit{sys}}$ |
| `\FiLMWorstOmega` | $0.3045$ | `unlinkability.unlinkability_table.bipolar_film.omega_worst` | Bipolar FiLM Worst-case overlap metric $\Omega$ |
| `\BioHashingWorstDsys` | $0.0239$ | `unlinkability.unlinkability_table.biohashing.D_sys_worst` | BioHashing Worst-case $D_{\leftrightarrow}^{\mathit{sys}}$ (below null $p_{95}$) |
| `\IoMWorstDsys` | $0.0110$ | `unlinkability.unlinkability_table.iom.D_sys_worst` | Index-of-Max Worst-case $D_{\leftrightarrow}^{\mathit{sys}}$ (below null $p_{95}$) |

---

## 4. Orthogonal Procrustes Known-Plaintext Attack on ROP

- **Generating Script:** `scripts/run_all_experiments.py` (Step 4: `run_procrustes_attack`)
- **Attack Model:** Orthogonal Procrustes $\min_{\hat{\mathbf{Q}}} \|\hat{\mathbf{Q}}\mathbf{E} - \mathbf{T}\|_F$ via SVD of $\mathbf{T}\mathbf{E}^\top$.

| Macro | Value in Paper | Frobenius Error | Downstream Inversion EER | Security Status |
| :--- | :--- | :--- | :--- | :--- |
| $n=16$ | `\ProcrustesErrSixteen`, `\ProcrustesEERSixteen` | $1.3685$ | $36.52\%$ | Resists inversion |
| $n=64$ | `\ProcrustesErrSixtyFour`, `\ProcrustesEERSixtyFour` | $1.2283$ | $23.00\%$ | High error |
| $n=128$ | `\ProcrustesErrOneTwentyEight`, `\ProcrustesEEROneTwentyEight`| $0.9978$ | $10.38\%$ | Partial reconstruction |
| $n=256$ | `\ProcrustesErrTwoFiftySix`, `\ProcrustesEERTwoFiftySix` | $0.1281$ | $0.10\%$ | **Security collapses** |
| $n=512$ | `\ProcrustesErrFiveTwelve`, `\ProcrustesEERFiveTwelve` | $0.0007$ | $0.00\%$ | Complete matrix recovery |

---

## 5. Inversion Preimage & Unknown-Key Security

- **Generating Script:** `scripts/run_all_experiments.py` (Step 5: `run_inversion_eval`)

| Macro | Value in Paper | Metric / Description |
| :--- | :--- | :--- |
| `\PreimageEERCos` | $48.75\%$ | ROP random-key preimage test under Cosine distance |
| `\PreimageEERAbs` | $49.16\%$ | ROP random-key preimage test under Absolute-Value distance |
| `\PreimageEERSort` | $49.93\%$ | ROP random-key preimage test under Sorted-Magnitude distance |
| `\LearnedInversionEER` | $41.27\%$ | Inversion MLP trained on (template, embedding) pairs without key |
| `\ExactInversionMaxErr` | $2.45 \times 10^{-7}$ | ROP exact analytical inversion numerical max error ($\mathbf{e} = \mathbf{Q}^\top \mathbf{t}$) |
| `\ExactInversionMeanErr` | $6.88 \times 10^{-8}$ | ROP exact analytical inversion numerical mean error |
| `\FiLMCosEER` | $50.60\%$ | FiLM unknown-key preimage test under Cosine distance |
| `\FiLMAbsEER` | $17.56\%$ | FiLM unknown-key preimage test under Abs-Val distance (reveals magnitude leak) |

---

## 6. Mean-Centering Ablation

- **Generating Script:** `scripts/run_all_experiments.py` (Step 6: `run_mean_centering_eval`)

| Macro | Value in Paper | Description |
| :--- | :--- | :--- |
| `\UncenteredImpostorMean` | $0.794$ | Mean impostor cosine similarity without mean-centering ($\sigma = 0.082$) |
| `\UncenteredDPrime` | $3.02$ | Decidability index $d'$ for uncentered cone |
| `\UncenteredEER` | $2.57\%$ | EER on uncentered embeddings |
| `\CenteredImpostorMean` | $0.032$ | Mean impostor cosine similarity with mean-centering ($\sigma = 0.341$) |
| `\CenteredDPrime` | $3.32$ | Decidability index $d'$ for mean-centered representations |
| `\CenteredEER` | $3.74\%$ | EER on mean-centered representations |

---

## 7. Synthetic Alteration Breakdown (Table X Reconciliation)

- **Generating Script:** `scripts/run_all_experiments.py` (Step 7: `run_alteration_breakdown`)
- **Total Stress Probes:** 7,327 synthetically corrupted fingerprint impressions matched against unaltered gallery prints at $\tau = 0.9218$.

| Macro | Value in Paper | Category / Severity |
| :--- | :--- | :--- |
| `\AlterationOverallFRR` | $22.25\%$ | Weighted overall stress FRR across all 7,327 altered impressions |
| `\CREasyFRR` | $1.34\%$ | Central Rotation (Easy) |
| `\CRMedFRR` | $38.37\%$ | Central Rotation (Medium) |
| `\CRHardFRR` | $54.47\%$ | Central Rotation (Hard) |
| `\OblEasyFRR` | $8.16\%$ | Obliteration (Easy) |
| `\OblMedFRR` | $27.23\%$ | Obliteration (Medium) |
| `\OblHardFRR` | $37.70\%$ | Obliteration (Hard) |
| `\ZcutEasyFRR` | $0.00\%$ | Z-Cut (Easy) |
| `\ZcutMedFRR` | $11.15\%$ | Z-Cut (Medium) |
| `\ZcutHardFRR` | $34.66\%$ | Z-Cut (Hard) |

---

## 8. TenSEAL CKKS Homomorphic Precision & Network Modeling

- **Generating Script:** `scripts/run_all_experiments.py` (Step 8: `run_ckks_and_transmission_model`)
- **Crypto Backend:** TenSEAL 0.3.16 (Microsoft SEAL)

| Macro | Value in Paper | Provenance / Methodology |
| :--- | :--- | :--- |
| `\CKKSPolyDegree` | $8192$ | Polynomial modulus degree $N$ (128-bit classical security) |
| `\CKKSScalePower` | $40$ | Scale factor $\Delta = 2^{40}$ |
| `\CKKSMaxAbsErr` | $1.24 \times 10^{-6}$ | Max absolute error between CKKS and plaintext inner product over 1,000 trials |
| `\CKKSMeanAbsErr` | $9.74 \times 10^{-7}$ | Mean absolute error between CKKS and plaintext inner product |
| `\PairedCKKSEER` | $3.03\%$ | Paired verification EER on 1,000 trials |
| `\PairedCKKSEERDiff` | $0.00\%$ | Paired EER difference between plaintext and CKKS |
| `\ProbeCiphertextKB` | $323.83$\,KB | Serialized probe ciphertext size |
| `\ResultCiphertextKB` | $229.59$\,KB | Serialized inner product result ciphertext size |
| `\UplinkDelayMS` | $176.85$\,ms | Uplink transmission time over 15 Mbps channel |
| `\DownlinkDelayMS` | $62.69$\,ms | Downlink transmission time over 50 Mbps channel |
| `\CellularBaseRTT` | $50$\,ms | Base network RTT |
| `\CellularDelayMS` | $284.55$\,ms | Total simulated 4G/LTE transmission latency |
| `\TotalMobileLatencyMS` | $307.93$\,ms | Projected total mobile verification latency |

---

## 9. System Latency & Multi-Client Load Testing

- **Generating Script:** `scripts/run_all_experiments.py` (Step 9: `run_latency_and_load_eval`)
- **Server:** FastAPI backend with 8 worker processes on Apple Silicon ARM64 hardware.
- **Client:** Locust load generator running closed-loop requests with think time $Z = 1.25$\,s.

| Macro | Value in Paper | Provenance |
| :--- | :--- | :--- |
| `\EETOMedian` | $25.11$\,ms | Directly measured end-to-end unloaded latency (median) |
| `\EETOPNinetyFive` | $26.28$\,ms | 95th percentile unloaded E2E latency |
| `\EETOPNinetyNine` | $29.81$\,ms | 99th percentile unloaded E2E latency |
| `\ServerDotMedian` | $13.29$\,ms | Server homomorphic inner product median latency |
| `\ServerDotPNinetyFive` | $13.80$\,ms | Server homomorphic inner product 95th percentile |
| `\ServerDotPNinetyNine` | $15.44$\,ms | Server homomorphic inner product 99th percentile |
| `\BaselineServiceTime` | $52.69$\,ms | Measured server baseline service time under low concurrency ($N=10$) |
| `\LocustBaselineServiceMedian` | $36.88$\,ms | Median service time under light load |
| `\SaturationThroughput` | $120.35$\,req/s | Measured peak server throughput at saturation |
| `\SaturationConcurrency` | $200$ | Number of concurrent clients at saturation point |
| `\LocustWorkersCount` | $8$ | Number of FastAPI worker processes |
| `\LocustPeakCPU` | $98.5\%$ | Server CPU utilization at saturation |
| `\LocustPeakLatencyMean` | $451.96$\,ms | Mean server response time at 200 clients |
| `\LocustEffectiveServiceTime` | $65$\,ms | Effective service time inflated by worker context switching |
| `\LocustTheoreticalCeiling` | $123$\,req/s | Theoretical ceiling ($8 / 0.065$) |

---

## 10. TVLA Fresh Encryption Timing Side-Channel Analysis

- **Generating Script:** `scripts/run_all_experiments.py` (Step 10: `run_tvla_eval`)
- **Protocol:** 2,000 trials (1,000 fixed, 1,000 random plaintexts) with fresh encryptions per trial in interleaved order to eliminate memory reuse artifacts.

| Macro | Value in Paper | Description |
| :--- | :--- | :--- |
| `\TVLATrialsCount` | $2,000$ | Number of interleaved fresh-encryption trials |
| `\TVLATStat` | $3.23$ | Welch two-sample $t$-statistic ($|t| < 4.5$ standard TVLA threshold) |
| `\TVLAPVal` | $0.0013$ | Welch two-sample $p$-value |
| `\TVLAMeanDiff` | $0.0399$\,ms | Observed mean execution time difference ($13.42$ vs $13.38$\,ms) |
| `\TVLAFixedVar` | $0.1387$\,ms$^2$ | Variance of fixed plaintext encryption timing |
| `\TVLARandomVar` | $0.0137$\,ms$^2$ | Variance of random plaintext encryption timing |
