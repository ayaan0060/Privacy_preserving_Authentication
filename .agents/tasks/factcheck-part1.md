# Adversarial Fact-Check Report — Part 1
**Reviewer:** Adversarial independent audit (automated)  
**Workspace:** `/Users/ayaanwani/biometric-auth-system-Kiro_updated(10)`  
**Date:** 2025  
**Files read:** Research.tex (full), macros.tex, metrics.json, protocol_results.json, attestation_benchmark.json, core/keys.py, core/protocol.py, core/film.py, core/unlinkability.py, android_he_service/main.py, android_he_service/he_keys/params.yaml, scripts/run_all_experiments.py, scripts/run_attestation_benchmark.py, all tables/*.tex, DISCREPANCY_REPORT.md, results/raw/inversion_results.json, scripts/make_macros.py, scripts/extract_embeddings.py, phase1_encoder/model/encoder.py, phase1_encoder/model/loss.py, phase1_encoder/model/backbone.py

---

## Section A — Number-by-Number Verification Table

| # | Claimed Value | Source in Paper | Found in macros.tex | Found in metrics.json | Match? | Status |
|---|---|---|---|---|---|---|
| 1 | EER 9.90% (all-alteration ROP) | Abstract, §IV, §V | `\HeadlineEER{9.90\%}`, `\AllAlterationEER{9.90\%}` | `verification.all_alteration.eer_percent: 9.9` | ✓ | **VERIFIED** |
| 2 | Easy-only EER 2.84% | Abstract, §V | `\EasyOnlyEER{2.84\%}` | `verification.easy_only.eer_percent: 2.84` | ✓ | **VERIFIED** |
| 3 | Multi-seed EER text "9.90 ± 0.24%" | Abstract, §I, §V | `\MultiSeedEER{9.90\% ± 0.24\%}`, `\MultiSeedEERText` | `verification.multi_seed_rop_mean: 9.9, std: 0.24` | ✓ | **VERIFIED** |
| 4 | CKKS max absolute error 1.43e-06 | §V (HE section), tab_he.tex | `\CKKSMaxAbsErr{1.43e-06}` | `ckks.ckks_max_abs_error: "1.43e-06"` | ✓ | **VERIFIED** — *but see Note 1 below* |
| 5 | CKKS mean absolute error 1.16e-06 | tab_he.tex | `\CKKSMeanAbsErr{1.16e-06}` | `ckks.ckks_mean_abs_error: "1.16e-06"` | ✓ | **VERIFIED** |
| 6 | ΔEER = 0.00% (zero HE degradation) | §V | `\PairedCKKSEERDiff{0.00\%}` | `ckks.paired_eer.delta_eer: 0.0` | ✓ | **VERIFIED** |
| 7 | Server dot-product latency 13.36 ms median | §V, tab_latency.tex | `\ServerDotMedian{13.36\,ms}` | `performance.server_dot_product_median_ms: 13.36` | ✓ | **VERIFIED** |
| 8 | End-to-end latency 27.19 ms median | Abstract, §V | `\EETOMedian{27.19\,ms}` | `performance.e2e_median_ms: 27.19` | ✓ | **VERIFIED** |
| 9 | FiLM AUC (abs-val attack) 0.9413 | §III-C, §V, tab_unlinkability.tex | `\FiLMAbsAUC{0.9413}` | `unlinkability.unlinkability_table.bipolar_film.auc_abs_val: 0.9413` | ✓ | **VERIFIED** |
| 10 | ROP worst-case AUC (learned attack) 0.5070 | Abstract, §III, §V | `\ROPLearnedAUC{0.5070}` | `unlinkability.unlinkability_table.rop.auc_learned_mlp: 0.507` | ✓ | **VERIFIED** |
| 11 | ROP Dsys = 0.0353 | §III, §V, tab_unlinkability.tex | `\ROPWorstDsys{0.0353}` | `unlinkability.unlinkability_table.rop.D_sys_worst: 0.0353` | ✓ | **VERIFIED** |
| 12 | ROP Ω = 0.9647 | §III, §V | `\ROPWorstOmega{0.9647}` | `unlinkability.unlinkability_table.rop.omega_worst: 0.9647` | ✓ | **VERIFIED** |
| 13 | Null noise floor p-value 0.0443 | §V | `\NullNoiseFloorP{0.0443}` | `unlinkability.null_noise_floor_p95: 0.0443` | ✓ | **VERIFIED** |
| 14 | Sustainable throughput 6.07 req/s | Abstract, §V | `\SustainableThroughput{6.07\,req/s}` | `performance.sustainable_throughput_req_s: 6.07` | ✓ | **VERIFIED** |
| 15 | Sustainable concurrency N=10 | Abstract, §V | `\SustainableConcurrency{10}` | `performance.sustainable_concurrency: 10` | ✓ | **VERIFIED** |
| 16 | P95 latency at N=10: 1114.84 ms | Abstract, §V | `\SustainableLatencyPNinetyFive{1114.84\,ms}` | `load_testing[0].p95_latency_ms: 1114.84` | ✓ | **VERIFIED** |
| 17 | Saturation throughput 11.44 req/s | Abstract, §V | `\SaturationThroughput{11.44\,req/s}` | `performance.saturation_throughput_req_s: 11.44` | ✓ | **VERIFIED** |
| 18 | Saturation concurrency N=300 | Abstract, §V | `\SaturationConcurrency{300}` | `performance.saturation_concurrency: 300` | ✓ | **VERIFIED** |
| 19 | Worker count = 4 | Abstract (table caption), §V | `\LocustWorkersCount{4}` | `performance.load_test_host_info: "...4 server worker threads..."` | ✓ | **VERIFIED** |
| 20 | TAR@1%FAR = 71.72% | tab_encoder_eval.tex, §V | `\TARAtFAROnePct{71.72\%}` | `verification.all_alteration.tar_at_far_1pct: 71.72` | ✓ | **VERIFIED** |
| 21 | Operating threshold τ = 0.8910 | §IV-B, §V | `\OperatingThresholdTau{0.8910}`, `\AllAlterationTau{0.8910}` | `verification.all_alteration.tau_threshold: 0.891` | ✓ | **VERIFIED** |
| 22 | Validation-transfer threshold τ_val = 0.8943 | §V | `\ValTransferTau{0.8943}` | `verification.val_transfer_tau: 0.8943` | ✓ | **VERIFIED** |
| 23 | FiLM inversion error max ~2.87e-08 | §III-B, §VI | `\FiLMInversionMaxErr{2.87e-08}` | **NOT in metrics.json** — hardcoded in make_macros.py line 275 | ⚠ | **PARTIALLY UNVERIFIED** — *see Note 2* |
| 24 | ArcFace margin m=0.5 rad, scale s=64 | §IV-B | Hardcoded literal in Research.tex | `phase1_encoder/model/loss.py: margin=0.5, scale=64.0` | ✓ | **VERIFIED** |
| 25 | ResNet-18 output dimension 256 | §IV-B, §IV, abstract | Hardcoded literal | `phase1_encoder/model/encoder.py: embedding_dim=256` | ✓ | **VERIFIED** |
| 26 | Total pair count ALL=14,654 | §V, tab_encoder_eval.tex | `\AllAlterationTotalPairs{14,654}` | `verification.all_alteration.pair_counts.total_pairs: 14654` | ✓ | **VERIFIED** |
| 27 | Total pair count EASY=5,374 | §V | `\EasyOnlyTotalPairs{5,374}` | `verification.protocols.EASY.pair_counts_seed42.total: 5374` | ✓ | **VERIFIED** |
| 28 | Nominal benchmark 5,000 gen + 5,000 imp | §IV, §V | `\NominalBenchmarkGenuine{5,000}`, `\NominalBenchmarkImpostor{5,000}` | `verification.nominal_benchmark.genuine_pairs: 5000, impostor_pairs: 5000` | ✓ | **VERIFIED** |
| 29 | CKKS polynomial modulus N=8192 | §IV-C, tab_he.tex | `\CKKSPolyDegree{8192}` | `ckks.ckks_poly_degree: 8192` | ✓ | **VERIFIED** |
| 30 | 128-bit classical security | Abstract, §IV-C, §VI | Hardcoded literal text | `android_he_service/he_keys/params.yaml: security_level: 128` | ✓ | **VERIFIED** |
| 31 | `metrics.json headline_eer = 2.89` | NOT in paper | N/A | `verification.headline_eer: 2.89` | ⚠ | **INTERNAL INCONSISTENCY** — *see Note 3* |
| 32 | `metrics.json ckks.paired_eer.max_ckks_error = 1.91e-06` | Paper cites 1.43e-06 | `\CKKSMaxAbsErr{1.43e-06}` | `ckks.paired_eer.max_ckks_error: 1.9065e-06` | ❌ | **INTERNAL INCONSISTENCY** — *see Note 1* |
| 33 | Cross-entropy EER 7.19% ± 0.11% | §V, tab_encoder_eval.tex | `\CrossEntropyEER{7.19\%}`, `\CrossEntropyEERStd{0.11\%}` | `verification.cross_entropy_eer_mean: 7.19` | ✓ | **VERIFIED** (minor: protocol_results.json shows EASY eer_mean=7.18) |
| 34 | Null noise floor mean = 0.0382 | §V | `\NullNoiseFloorMean{0.0382}` | `unlinkability.null_noise_floor_mean: 0.0382` | ✓ | **VERIFIED** |

---

### Notes on Key Discrepancies

**Note 1 — CKKS Max Error Internal Inconsistency:**  
`ckks.ckks_max_abs_error` = "1.43e-06" (matches paper claim).  
`ckks.paired_eer.max_ckks_error` = 1.9065e-06 (different value, ~33% higher).  
These two fields represent different experiments: the former comes from `results/raw/latency_summary.json` (or a dedicated CKKS precision run), the latter from the 1,000 paired ALL-protocol CKKS trials. The paper reports only 1.43e-06. The paired-EER block measurement is 1.91e-06 — a discrepancy within metrics.json itself. The paper's claim (1.43e-06) is not falsified but there exists an unreported higher measurement within the same file.

**Note 2 — FiLM Inversion Max Error (2.87e-08) Not in metrics.json:**  
`\FiLMInversionMaxErr{2.87e-08}` is **hardcoded** in `scripts/make_macros.py` line 275 and does NOT derive from any field in metrics.json or inversion_results.json. The `results/raw/inversion_results.json` file contains no `film_known_key` entry. Independent reproduction on 500 real embeddings yielded max error 4.47e-08, mean 1.93e-08 — both higher than the claimed values. The claim is plausible (inversion is analytical and errors are governed by floating-point precision) but **CANNOT BE TRACED to an experiment output file**. Status: UNVERIFIED via metrics.json provenance chain.

**Note 3 — `metrics.json` `headline_eer = 2.89` vs paper's 9.90%:**  
In `metrics.json`, `verification.headline_eer` = 2.89, while `\HeadlineEER` in macros.tex = 9.90%.  
This is a labeling inconsistency within metrics.json: the field `headline_eer` refers to the **nominal 10,000-pair benchmark** EER (easy-only, 5k+5k), whereas the paper uses "headline EER" to mean the **all-alteration protocol** EER (9.90%). `macros.tex` correctly sources from `all_alteration.eer_percent = 9.9`, not from `headline_eer = 2.89`. The paper's 9.90% is consistent with the ALL protocol data. However, the ambiguous `headline_eer` field in metrics.json could mislead readers who inspect the JSON directly.

---

## Section B — Code vs Paper Consistency

### B1. ResNet-18 encoder, 256-dim, unit-norm, trained from scratch, ArcFace

| Claim | Code Evidence | Status |
|---|---|---|
| ResNet-18 architecture | `phase1_encoder/model/backbone.py`: `BasicBlock, [2,2,2,2]` (standard ResNet-18 config), `resnet18_backbone()` | **VERIFIED** |
| 256-dimensional output | `phase1_encoder/model/encoder.py`: `embedding_dim=256` default; `FingerprintEncoder(embedding_dim=256)` | **VERIFIED** |
| Unit-norm embeddings | `phase1_encoder/model/encoder.py`: `norm_embeddings=True` default; EmbeddingHead performs L2 normalization | **VERIFIED** |
| Trained from scratch | `phase1_encoder/model/backbone.py` docstring: "No pretrained weights (fingerprint domain is too different from ImageNet)"; constructor does NOT use `weights=` or `pretrained=True` | **VERIFIED** |
| ArcFace loss | `phase1_encoder/model/loss.py`: `ArcFaceLoss` class implements angular margin formula; `margin=0.5`, `scale=64.0` matches paper | **VERIFIED** |
| ArcFace formula matches Deng 2019 | Code: `phi = cosine*cos_m - sine*sin_m` with `th = cos(π-m)`, `mm = sin(π-m)*m`; this is the standard ArcFace formula | **VERIFIED** |
| single-channel (grayscale) input | `phase1_encoder/model/backbone.py`: `conv1 = nn.Conv2d(in_channels, ...)`, `resnet18_backbone(in_channels=1)` | **VERIFIED** |

> **Minor gap:** `run_all_experiments.py` imports `from evaluator import compute_eer_metrics` and `load_state_dict(torch.load(ROOT_DIR / 'exports' / 'film_generator.pt'))` — but the actual encoder training code is in `phase1_encoder/train/trainer.py`, not in `run_all_experiments.py`. The benchmark uses pre-computed embeddings from `results/raw/socofing_test_embeddings.npz`. The encoder architecture cannot be independently validated purely from `run_all_experiments.py` — one must trace through `phase1_encoder/`. This matches the paper's description fully.

---

### B2. HKDF-SHA256 → AES-256-CTR-DRBG → uint64 → Box-Muller → QR with Mezzadri

| Step | Code Evidence | Status |
|---|---|---|
| HKDF-SHA256 with `info = f"{user_id}\|v{version}"` | `keys.py:derive_hkdf_bytes`: `HKDF(algorithm=hashes.SHA256(), ..., info=f"{user_id}\|v{version}".encode())` | **VERIFIED** |
| L=32 output (AES-256 key) | `keys.py:derive_hkdf_bytes(length=32)` in `derive_haar_matrix` | **VERIFIED** |
| AES-256-CTR-DRBG | `keys.py:CryptoDRBG`: `Cipher(algorithms.AES(key_bytes), modes.CTR(nonce))` with 32-byte key | **VERIFIED** |
| uint64 mapping to (0,1) | `keys.py:get_uniform_floats`: `np.frombuffer(dtype=np.uint64)`, `(u + 1.0) / (2**64 + 2.0)` | **VERIFIED** |
| Gaussian via Box-Muller | `keys.py:get_gaussian_floats`: explicit Box-Muller transform `r = sqrt(-2*log(u1))`, `z1 = r*cos(theta)`, `z2 = r*sin(theta)` | **VERIFIED** |
| QR with Mezzadri sign correction | `keys.py:derive_haar_matrix`: `Q, R = np.linalg.qr(G)`, `ph = np.sign(d)`, `Q = Q * ph` | **VERIFIED** |
| Isometry assertion `max\|Q^T Q - I\| < 1e-5` | `keys.py:derive_haar_matrix`: `diff = np.max(np.abs(Q.T @ Q - np.eye(dim)))`, raises `ValueError` if `> 1e-5` | **VERIFIED** |
| **AES-CTR nonce hardcoded to zeros** | `keys.py:CryptoDRBG.__init__`: `nonce = b'\x00' * 16` | **UNDISCLOSED** — *see Note 4* |

**Note 4 — Zero Nonce in AES-CTR:** `keys.py` uses a **hardcoded zero nonce** (`b'\x00' * 16`). The paper describes the derivation as `AES-256-CTR-DRBG(K_AES)` without mentioning the nonce. This is a design disclosure gap. A fixed zero nonce is standard for DRBG construction (NIST SP 800-90A CTR_DRBG sets the initial counter to 0), since the key uniqueness (from HKDF per user/version) provides the necessary diversification. However, the paper does not disclose this, leaving the reader to assume the nonce selection is standard or irrelevant. This should be noted in the security analysis. It is NOT an error, but a **DISCLOSURE GAP**.

---

### B3. FiLM architecture: two-branch MLP, Softplus for γ, tanh for β

| Claim | Code Evidence | Status |
|---|---|---|
| Two-branch MLP | `film.py:FiLMGenerator`: separate `self.gamma_net` and `self.beta_net` Sequential modules | **VERIFIED** |
| Softplus for γ | `film.py:FiLMGenerator.forward`: `gamma = F.softplus(raw_g)` | **VERIFIED** |
| tanh for β | `film.py:FiLMGenerator.forward`: `beta = torch.tanh(raw_b)` | **VERIFIED** |
| Applied as t = γ⊙e + β | `film.py:apply_film_modulation`: `scaled = gamma * e; t = scaled + beta; t / norm(t)` | **VERIFIED** |
| Hidden activations: GELU (not stated in paper) | `film.py:FiLMGenerator.__init__`: `layers_g.append(nn.GELU())` — GELU in hidden layers | **PAPER OMITS GELU** — Paper's Eq.8 shows only output activations Softplus/tanh; not incorrect but incomplete |
| Identity initialization: Softplus bias → 1.0 | `film.py:_init_identity_weights`: `gamma_bias = log(exp(1.0)-1.0)` then `self.gamma_net[-1].bias.fill_(gamma_bias)` | **VERIFIED** |

---

### B4. CKKS with TenSEAL at N=8192, 128-bit security

| Claim | Evidence | Status |
|---|---|---|
| `poly_modulus_degree = 8192` | `params.yaml: poly_modulus_degree: 8192`; `android_he_service/main.py: poly_modulus_degree=8192` | **VERIFIED** |
| `coeff_mod_bit_sizes = [60,40,40,60]` | `params.yaml: coeff_mod_bit_sizes: [60,40,40,60]`; `android_he_service/main.py: coeff_mod_bit_sizes=[60, 40, 40, 60]` | **VERIFIED** |
| 128-bit security | `params.yaml: security_level: 128`; tab_he.tex header hardcoded "> 128 bits" | **VERIFIED** |
| `scale_bits = 40` | `params.yaml: scale_bits: 40`; `android_he_service/main.py: context.global_scale = 2**40` | **VERIFIED** |
| `std_dev = 3.2` | `params.yaml: std_dev: 3.2` — standard value, not contradicted | **VERIFIED** |
| `run_all_experiments.py` uses the same parameters | `run_ckks_evaluation()` in run_all_experiments.py uses `poly_modulus_degree=8192, coeff_mod_bit_sizes=[60,40,40,60], global_scale=2**40` | **VERIFIED** |

---

### B5. ROP isometry: `max |Q^T Q - I| < 1e-5`

| Claim | Evidence | Status |
|---|---|---|
| Enforced in code | `keys.py:derive_haar_matrix`: assertion `diff > 1e-5` raises `ValueError` | **VERIFIED** |
| Reported value `\ROPIsometryMaxDiff{1.79e-07}` | `metrics.json: verification.rop_isometry_max_diff: 1.7881393e-07` | **VERIFIED** |
| Value is well below 1e-5 | 1.79e-07 < 1e-05 ✓ | **VERIFIED** |

---

### B6. ECDSA attestation: `σ = ECDSA-P256(sk_dev, H(d ‖ n_s ‖ v))`

| Claim | Evidence | Status |
|---|---|---|
| P-256 curve | `run_attestation_benchmark.py`: `ec.SECP256R1()`, `ec.generate_private_key(ec.SECP256R1())` | **VERIFIED** |
| Payload = H(d ‖ n_s ‖ v) | `_create_payload()`: `raw = pack(">B", decision) + nonce + pack(">I", version)`, then `hashlib.sha256(raw).digest()` | **VERIFIED** |
| ECDSA signing | `_sign()`: `private_key.sign(payload, ec.ECDSA(hashes.SHA256()))` | **VERIFIED** |
| 1-bit decision (not score) | `score_concealment` test verifies payload contains only boolean byte 0x00/0x01, not float score | **VERIFIED** |
| Nonce replay blocked | Test 5: checks `replayed_nonce in used_nonces` (set membership) | **VERIFIED** — *but see Note 5* |

**Note 5 — Nonce replay is set-membership test only:** The attestation benchmark's replay test (Test 5) merely checks if the nonce is already in an in-memory set. It does NOT test a persistent nonce store, TTL expiry, or server-side rejection. This is adequate for a benchmark smoke test but does not exercise the full anti-replay protocol described in §III-A.

---

### B7. ISO/IEC 24745 unlinkability: Gómez-Barrero with null calibration

| Claim | Evidence | Status |
|---|---|---|
| Gómez-Barrero D_sys formula | `unlinkability.py:compute_gomez_barrero`: `d_local = max(0, 2*ratio - 1)`, `d_sys = sum(d_local * p_mated * bin_widths)` — matches reference formula | **VERIFIED** |
| Null permutation calibration | `unlinkability.py:compute_null_calibration`: permutes mated/non-mated labels, computes D_sys under H0 | **VERIFIED** |
| Bootstrap CIs for D_sys | `unlinkability.py:compute_bootstrap_cis`: bootstrap over mated/non-mated separately | **VERIFIED** |
| Reference: Gómez-Barrero et al. TIFS 2018 | Docstring cites correctly | **VERIFIED** |

---

### B8. AES-CTR nonce hardcoded to zeros — paper disclosure

The paper does not disclose this. Text (§IV-B): `"AES-256-CTR-DRBG(K_AES)"` with no mention of nonce. This is a **DISCLOSURE GAP** (not an error). For a DRBG use case, zero initial counter/nonce is standard and safe if keys are unique per user/version (ensured by HKDF with domain separation). However, the paper omits this detail, which may matter for security-sensitive readers.

---

## Section C — Experiment Methodology Findings

### C1. Train/test split — does test touch training?

- `scripts/extract_embeddings.py`: `train_test_split(subjects, test_size=0.15, random_state=42)` performs a deterministic subject-level split; subjects 420/90/90 (approx.) for train/val/test.
- The test embeddings are stored in `results/raw/socofing_test_embeddings.npz` and loaded directly in `run_all_experiments.py` without any reference to the training set.
- EER evaluation uses only `socofing_test_embeddings.npz` and `socofing_val_embeddings.npz`.
- **No evidence of test leakage into training** — split is subject-level and partition files are separate.

### C2. 90 held-out test subjects truly held out

- `extract_embeddings.py`: `test_size=0.15` of 600 subjects → 90 subjects; `random_state=42` ensures reproducibility.
- `run_all_experiments.py` loads only the pre-split test embedding file and counts subjects: `test_subjs = len(set(get_user_id_from_path(p) for p in test_paths))` → `metrics.json: test_subjects_count: 90`.
- **VERIFIED**: 90 subjects confirmed.

### C3. Pair sampling — duplicates or contamination risk

- `core/protocol.py:build_pairs`: genuine pairs sampled by exhaustive cross-product (all Real × Altered for same subject-finger), so no duplicates possible in the genuine set.
- Impostor pairs: a `seen` set prevents exact duplicate pairs, but sampling is cross-subject Real × Real only.
- **POTENTIAL CONCERN**: Impostor pairs are sampled with `random.Random(seed)` and capped at `n_needed*200` attempts. For the ALL protocol, we need 7,327 impostor pairs from 90 subjects' real images. With 90 subjects × 10 fingers = 900 real images, there are ~900×899/2 ≈ 404,550 possible cross-subject pairs. Requested 7,327 is well within supply — no contamination or repetition risk.
- **VERIFIED**: No contamination.

### C4. EER threshold selection — is it done on test data?

- `protocol.py` docstring: "tau chosen on the validation split under the SAME protocol, transferred to test."
- `run_all_experiments.py` computes `all_alt_tau` from the **validation** split (`socofing_val_embeddings.npz`), then evaluates FAR/FRR on test.
- The paper reports both `τ = 0.8910` (test EER crossover, reported for transparency per-seed) and `τ_val = 0.8943` (validation-derived threshold, used for FAR/FRR evaluation).
- **VERIFIED**: Threshold selected on validation, not test. No threshold selection bias.
- **NUANCE**: The per-seed EER τ (0.8910) *is* computed on test data — but this is the EER crossover, not a separately selected threshold. EER by definition finds the FAR=FRR crossover on the test split. This is standard ISO/IEC 19795 practice and the paper discloses both thresholds explicitly.

### C5. Three evaluation seeds — pair sampling only, not model training

- `run_all_experiments.py` uses `SEEDS = [42, 123, 456]` for pair sampling only (RNG in impostor pair selection).
- The encoder is trained once; embeddings are extracted once and fixed. Seeds affect only which random impostor pairs are sampled.
- **VERIFIED**: Seeds affect pair sampling variance, NOT model training variance. Paper correctly describes this as "pair-sampling variance across three evaluation seeds on a single trained encoder."

### C6. SOCOFing dataset — real images, not synthetic

- `run_all_experiments.py`: dataset path `~/.cache/kagglehub/datasets/ruizgara/socofing/versions/2/SOCOFing/SOCOFing`; real images at `/Real/`, alterations at `/Altered/Altered-{Easy,Medium,Hard}/`.
- Paper clearly states: "The dataset includes synthetically modified impressions" — the alterations are synthetic, but the source images in `/Real/` are real fingerprints.
- `eval/eer_benchmark/dataset_fvc/finger_001/imp_01.png` etc. — this appears to be an FVC-style dataset used for a separate (earlier) benchmark, not the SOCOFing test split.
- **VERIFIED**: SOCOFing `/Real/` images are real captured fingerprints (6,000 real impressions from 600 subjects); alterations are synthetic modifications.

---

## Section D — Mathematical Verification

### D1. σ_cross ≈ 1/√D = 1/√256 = 0.0625

- Computed: 1/√256 = 0.0625 ✓
- Paper claims 0.0625. **VERIFIED**.

### D2. FiLM energy fraction: 1/(1+‖β‖₂²) ≈ 90%

- From metrics.json: `FiLMNormBeta = 0.3276` (‖β‖₂ = 0.3276)
- Computed: 1/(1 + 0.3276²) = 1/(1 + 0.1073) = 1/1.1073 = 0.9031 ≈ 90.3%
- Paper claims ~90%. **VERIFIED** ✓

### D3. CKKS "four orders of magnitude" margin

- Genuine mean = 0.950, τ = 0.8910 → margin = 0.0590
- CKKS max error = 1.43e-06
- Ratio = 0.0590 / 1.43e-06 = 41,259 → log₁₀ = 4.62 orders of magnitude
- Paper claims "four orders of magnitude." **VERIFIED** (slightly over 4, approximately stated) ✓

### D4. Little's Law verification for each load test row (N = X(R + Z), Z=1.25s)

| N | X (req/s) | R (ms) | X·(R+Z)/1000 | Disc% | Reported Disc% |
|---|---|---|---|---|---|
| 10 | 6.07 | 394.8 | 9.98 | 0.16% | 0.34% |
| 25 | 9.93 | 1276.5 | 25.09 | 0.35% | 0.19% |
| 50 | 13.09 | 2591.6 | 50.29 | 0.57% | 0.38% |
| 100 | 14.60 | 5721.4 | 101.78 | 1.78% | 0.34% |
| 150 | 14.14 | 9408.0 | 150.70 | 0.47% | 0.47% |
| 200 | 15.45 | 11698.4 | 200.05 | 0.03% | 0.14% |
| 300 | 11.44 | 24900.4 | 299.16 | 0.28% | 0.62% |

**FINDING**: Little's Law holds well (all discrepancies < 2%). The reported discrepancies in DISCREPANCY_REPORT.md differ from recalculated values (the DISCREPANCY_REPORT values appear to be from a slightly different computation or different raw measurements). The paper's claim that discrepancy is within "2.7% across all load levels" is broadly supported but the reported per-row percentages do not precisely match recalculation (they appear to be std-based, not mean-based). **VERIFIED at the summary level.**

### D5. ArcFace loss formula — matches Deng et al. 2019?

- Paper Eq.1: `L_Arc = -log [e^{s·cos(θ_yi + m)} / (e^{s·cos(θ_yi + m)} + Σ_{j≠yi} e^{s·cos(θ_j)})]`
- `phase1_encoder/model/loss.py`: `phi = cosine*cos_m - sine*sin_m` (i.e., cos(θ+m)), applied to target class; other classes use raw cosine. Cross-entropy over scaled logits.
- This is the standard ArcFace formula from Deng et al. 2019. **VERIFIED** ✓

### D6. Cross-key inner product: E[e₁ᵀ Q₁ᵀ Q₂ e₂] = 0, σ = 1/√D

- For Haar-distributed Q₁, Q₂ independent, Q₁ᵀQ₂ is itself Haar-distributed and has expected inner products = 0 with std 1/√D for unit-norm embeddings.
- This is a standard result for random orthogonal matrices. **MATHEMATICALLY CORRECT** ✓

---

## Section E — Dataset Verification

### E1. SOCOFing: real Nigerian fingerprint dataset

- Paper: "SOCOFing benchmark... real fingerprint impressions from 600 subjects"
- `run_all_experiments.py` loads real images from `/Real/` path within the SOCOFing dataset.
- `eval/eer_benchmark/dataset_fvc/` contains FVC-style `imp_01.png` through `imp_08.png` per finger — this is a **separate, smaller synthetic evaluation dataset** not used for the main EER benchmark.
- The main SOCOFing images (6,000 real + 49,270 altered) are loaded from kagglehub cache.
- **VERIFIED**: Main evaluation uses real SOCOFing fingerprints + synthetic alterations.

### E2. 90 subjects held out for test

- `extract_embeddings.py`: `train_test_split(subjects, test_size=0.15, random_state=42)` → 90 subjects (15% of 600)
- `metrics.json: dataset.test_subjects_count: 90`
- **VERIFIED** ✓

### E3. All synthetic alteration levels present

- `metrics.json: dataset.disk_altered_easy_count: 17931, medium: 17067, hard: 14272`
- `run_all_experiments.py` explicitly iterates over `('Easy','Medium','Hard')` alterations
- **VERIFIED**: Easy, Medium, and Hard alterations all present in dataset and evaluated ✓

---

## Section F — Summary of UNVERIFIED, INCORRECT, or CONTRADICTED Items

### INCORRECT / INTERNALLY INCONSISTENT:

1. **`metrics.json` field `headline_eer = 2.89` is mislabeled** (INTERNAL INCONSISTENCY). The paper reports the "headline EER" as 9.90% (all-alteration protocol). The `verification.headline_eer` field in metrics.json actually stores the nominal benchmark EER (easy-only, 5k pairs) = 2.89%. The macro `\HeadlineEER` correctly uses `all_alteration.eer_percent = 9.9`, so the **paper is internally consistent**. However, anyone reading metrics.json directly would find a confusing discrepancy. **Does not affect paper correctness.**

2. **`metrics.json` CKKS max error inconsistency** (INTERNAL INCONSISTENCY): `ckks.ckks_max_abs_error = "1.43e-06"` (matches paper) but `ckks.paired_eer.max_ckks_error = 1.91e-06` (unreported, ~33% higher, from a different measurement run). The paper does not report the higher value. **This is an omission** — the paired ALL-protocol CKKS trial had a higher max error than the dedicated precision run. The paper's claim of 1.43e-06 is technically from a different trial. **POTENTIALLY INCORRECT** claim if the paired experiment (1.91e-06) is considered the correct measurement for the ALL-protocol EER evaluation.

3. **`protocol_results.json` cross-entropy EASY EER = 7.18%** but macros.tex and metrics.json use 7.19%. Minor rounding difference (7.175→7.18 or 7.19 depending on rounding). **MINOR INCONSISTENCY** — within rounding tolerance.

### UNVERIFIED:

4. **FiLM inversion max error = 2.87e-08** (macro `\FiLMInversionMaxErr`). This value is **hardcoded in `scripts/make_macros.py` line 275** and is NOT present in any stored experiment output file (metrics.json, inversion_results.json, etc.). Independent replication on 500 real embeddings yields max error 4.47e-08 (mean 1.93e-08) — both higher than claimed. The value is plausible (floating-point analytical inversion) but cannot be traced to a reproducible experiment output. **UNVERIFIED via provenance chain.**

5. **FiLM inversion mean error = 4.12e-09** — same provenance issue as above. **UNVERIFIED.**

6. **`ExactInversionMaxErr = 2.45e-07` (ROP known-key inversion)**. This value IS traceable: `results/raw/inversion_results.json: known_key.max_error = 2.4520181796106044e-07` → matches. **VERIFIED** ✓ (listed here only to contrast with the FiLM case).

### DISCLOSURE GAPS (not errors but should be flagged):

7. **AES-CTR zero nonce not disclosed**. `keys.py` uses `nonce = b'\x00' * 16`. The paper does not disclose this. Standard DRBG practice but should be stated explicitly in a security paper.

8. **FiLM MLP uses GELU hidden activations** not mentioned in paper. Paper's Eq.8 only shows Softplus/tanh output activations. The intermediate GELU layers affect the modulation function's behavior but are not documented.

9. **Nonce replay benchmark is in-memory only** — does not test persistent server-side nonce store or TTL expiry.

10. **Cross-entropy EER (7.19%) evaluated on EASY-protocol nominal pairs only**, not the full ALL-protocol. `protocol_results.json` explicitly notes: `"Unrun on ALL alterations: embeddings for medium/hard distortions were not preserved"`. The paper's comparison table acknowledges this with a footnote `†` but the abstract and §V report cross-entropy baseline without alteration-level qualification. **POTENTIALLY MISLEADING** comparison context.

---

## Section G — Overall Assessment

The paper is **largely consistent** with its supporting data. The macro derivation chain (metrics.json → macros.tex → paper) functions correctly for all headline numbers. The critical numbers (9.90% EER, 2.84% easy EER, CKKS parameters, latency, unlinkability metrics, pair counts) all check out.

**The most significant finding is:** The `FiLMInversionMaxErr = 2.87e-08` macro is hardcoded, not derived from any stored experiment output, and independent replication yields a higher value (4.47e-08). This is a reproducibility gap.

**Secondary finding:** There are two different CKKS max-error measurements within metrics.json (1.43e-06 from the dedicated CKKS precision run; 1.91e-06 from the paired ALL-protocol CKKS trial), with the paper reporting only the lower value.

All other numbers are fully traced and verified.
