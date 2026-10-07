# Comprehensive Publication Audit Report
## "Privacy-Preserving Fingerprint Authentication Using Cancelable Templates and CKKS Homomorphic Encryption"

**Audit Date:** This audit  
**Auditor:** Systematic automated + manual inspection against all project artifacts  
**Source of Truth:** `results/final/metrics.json`, `results/final/macros.tex`, `core/*.py`, `android_he_service/`, acceptance/consistency test outputs

---

## A. Overall Publication-Readiness Verdict

**REQUIRES MAJOR REVISION**

**Evidence summary:**

The paper has undergone substantial remediation and the automated test suites (42/42 acceptance, 8/8 consistency, 14/14 unit) all pass on the current state. However, the independent audit uncovered the following blocking issues:

1. **The abstract hardcodes "8-worker server"** but the actual experiment used 4 workers (`\LocustWorkersCount = 4` in macros.tex, DISCREPANCY_REPORT confirms 4). This is a factual error on the paper's most-read paragraph.

2. **HKDF key-derivation equation (Eq. 3) contains three substantive mismatches with the implementation** in `core/keys.py`: wrong output length (L=1024 in paper vs L=32 in code), wrong integer width (uint32 vs uint64), and wrong info-string format (`biometric-auth|u|v|Key` vs `{user_id}|v{version}`). These errors make the described cryptographic protocol non-reproducible.

3. **Table III caption still says "10,000 Pairs"** even though the headline evaluation uses 14,654 pairs (ALL protocol) and the secondary uses 5,374 (EASY). This confuses readers who look at the caption to understand the experiment scale.

4. **FiLM inversion error in the threat-model section (§III-B) is hardcoded to `2.5 × 10⁻⁷`** while the corresponding macro `\FiLMInversionMaxErr` is `2.87 × 10⁻⁸` — a 10× discrepancy in the same section that claims numerical precision.

5. **The "validation EER operating point" label for τ is misleading**. τ = 0.8910 is the test-set EER crossover (where FAR = FRR = 10.17%); the validation-transferred threshold is τ_val = 0.8943. Line 434 calls τ the "validation EER operating point," contradicting the actual protocol (τ chosen on test).

6. **RESULTS_PROVENANCE.md is substantially out of date** — it documents an earlier experimental run and has been superseded by current macros.tex values; it still ships with the repository and will mislead reviewers who read it.

7. **Paper claims ROPWorstOmega = 0.9725** (from RESULTS_PROVENANCE) but the current macro is `\ROPWorstOmega = 0.9647`. Minor but verifiable.

8. **The CKKS paired EER claim in RESULTS_PROVENANCE states 3.03%**, while the current macro and paper correctly report 8.60%. RESULTS_PROVENANCE is thus actively misleading.

9. **Multiple figures and the ROC caption refer to "10,000 evaluation pairs"** but the headline protocol uses 14,654 (ALL) — requires correction in three places.

10. **ECDSA/1-bit attestation protocol is not implemented in the auditable codebase.** The `core/protocol.py` contains pair-sampling logic only; `android_he_service/main.py` provides encrypt/decrypt but no attestation signing; ECDSA signing exists only in `phase5_backend/`. As a claimed contribution the code backing this claim is buried in a separate phase not covered by the Makefile reproduce target.

None of these render the experimental results fabricated — the underlying measurements appear sound and traceably provenance'd from `metrics.json`. The issues are primarily: (a) three places in the paper that disagree with the code/macros on specific values, (b) an equation that cannot be used to reproduce the cryptographic implementation, and (c) a misleading supporting document.

---

## B. Critical Errors That MUST Be Fixed

### B-1. Abstract: "8-worker server" ← HARDCODED, WRONG
- **Location:** Research.tex, line 49 (abstract)
- **What is wrong:** The abstract states "On an **8-worker server**"
- **Evidence:** `results/final/macros.tex`: `\newcommand{\LocustWorkersCount}{4}`. `DISCREPANCY_REPORT.md §1`: "FastAPI/Uvicorn with **4 dedicated worker processes**." The load test table caption uses `\LocustWorkersCount` (= 4) correctly everywhere in the body; only the abstract is hardcoded.
- **Why wrong:** The experiment ran with 4 workers, not 8. The abstract is the most-read part of a paper and an incorrect server configuration is a reproducibility error.
- **Exact correction:**
```latex
% CURRENT (wrong):
On an 8-worker server, the architecture achieves a sustainable operating point of \SustainableThroughput{} at ...
% CORRECTED:
On a $\LocustWorkersCount$-worker server, the architecture achieves a sustainable operating point of \SustainableThroughput{} at ...
```

### B-2. Equation 3 (HKDF Derivation): Three mismatches with `core/keys.py`
- **Location:** Research.tex, lines 340–345 (§IV-C, Eq. 3)
- **What is wrong (mismatch a):** Paper states `OKM = HKDF-Expand(PRK, info_{u,v}, L=1024)`. Code calls `derive_hkdf_bytes(master_seed, user_id, version, 32)` — deriving only 32 bytes. The 32-byte output becomes the AES-256-CTR key for the DRBG; the DRBG then generates the Gaussian entries, not HKDF-Expand directly.
- **What is wrong (mismatch b):** Paper states `k_i = uint32(OKM[4i:4i+4]) / (2^32 - 1) × 2.0 - 1.0`. Code uses `uint64` (8-byte words) via `np.frombuffer(raw_bytes, dtype=np.uint64)`.
- **What is wrong (mismatch c):** Paper states `info_{u,v} = biometric-auth|u|v|Key`. Code uses `f"{user_id}|v{version}"` — no `biometric-auth` prefix and no `|Key` suffix.
- **Evidence:** `core/keys.py` lines 21-27, 68-73, 39-44.
- **Why wrong:** Anyone attempting to re-implement the protocol from the paper will derive a different key stream, making the claimed scheme non-reproducible. This is a critical reproducibility defect for a cryptographic system.
- **Correct information:** The paper should describe the two-stage pipeline: (1) HKDF-SHA256 derives a 32-byte AES-256 key, (2) AES-256-CTR DRBG (CryptoDRBG) generates pseudorandom bytes, (3) uniform floats derived via uint64 scaling, (4) Gaussian entries via Box-Muller.
- **Exact correction:**
```latex
% CURRENT (wrong):
\begin{align}
  \text{PRK} &= \text{HMAC-SHA256}(\text{salt}=\mathbf{0}_{32}, \text{IKM}=\mathbf{s}) \nonumber \\
  \text{OKM} &= \text{HKDF-Expand}(\text{PRK}, \text{info}_{u, v}, L=1024) \nonumber \\
  k_i &= \frac{\text{uint32}(\text{OKM}[4i : 4i+4])}{2^{32} - 1} \times 2.0 - 1.0
  \label{eq:hkdf_derivation}
\end{align}
where $\text{info}_{u, v} = \texttt{biometric-auth|u|v|Key}$ binds the derivation to user ID $u$ and key version $v$.

% CORRECTED (matches keys.py):
\begin{align}
  \text{PRK} &= \text{HMAC-SHA256}(\text{salt}=\mathbf{0}_{32}, \text{IKM}=\mathbf{s}) \nonumber \\
  K_{\text{AES}} &= \text{HKDF-Expand}(\text{PRK}, \text{info}_{u, v}, L=32) \nonumber \\
  \{r_i\} &= \text{AES-256-CTR-DRBG}(K_{\text{AES}}) \xrightarrow{\text{uint64}} (0,1)^D
  \label{eq:hkdf_derivation}
\end{align}
where $\text{info}_{u, v} = \texttt{\{user\_id\}|v\{version\}}$ binds the derivation to user ID $u$ and key version $v$.
The output key vector $\mathbf{k}$ is obtained by mapping uniform floats to $[-1, 1]^D$; for ROP, a Gaussian matrix is generated via Box-Muller transformation and orthogonalized via QR decomposition with Mezzadri sign correction.
```

### B-3. Table III Caption: Hardcoded "10,000 Pairs" — incorrect
- **Location:** Research.tex, line 548
- **What is wrong:** Caption reads "Verification and Identification Performance Across Representation Schemes (**10,000 Pairs**, Evaluation Seeds 42, 123, 456)". The headline ALL protocol uses 14,654 pairs; the EASY protocol uses 5,374 pairs. There is no experiment over exactly 10,000 pairs reported in this table.
- **Evidence:** `results/final/metrics.json` `pair_counts.total_pairs = 14654`; `results/final/macros.tex` `\AllAlterationTotalPairs{14,654}`, `\EasyOnlyTotalPairs{5,374}`.
- **Why wrong:** Readers using the table caption to understand sample size will be misinformed by a factor of ~1.5×.
- **Exact correction:**
```latex
% CURRENT:
\caption{Verification and Identification Performance Across Representation Schemes (10,000 Pairs, Evaluation Seeds 42, 123, 456)}
% CORRECTED:
\caption{Verification and Identification Performance Across Representation Schemes
(ALL Protocol: \AllAlterationTotalPairs{} pairs; EASY Protocol: \EasyOnlyTotalPairs{} pairs; Evaluation Seeds 42, 123, 456)}
```

### B-4. FiLM Inversion Error Hardcoded Incorrectly in Threat Model (§III-B)
- **Location:** Research.tex, line 202
- **What is wrong:** Text states FiLM inversion achieves `‖ê − e‖₂ < 2.5 × 10⁻⁷`. The corresponding macro `\FiLMInversionMaxErr` is `2.87e-08`, which is 10× smaller (better) than the stated value.
- **Evidence:** `results/final/macros.tex`: `\newcommand{\FiLMInversionMaxErr}{2.87e-08}`.
- **Why wrong:** This is a hardcoded literal in the threat-model section that disagrees with the empirical measurement. It overstates the inversion error by 10×.
- **Exact correction:**
```latex
% CURRENT:
with the unique positive real root recovering $\mathbf{e}$ up to machine precision ($\|\hat{\mathbf{e}} - \mathbf{e}\|_2 < 2.5 \times 10^{-7}$).
% CORRECTED:
with the unique positive real root recovering $\mathbf{e}$ up to machine precision ($\|\hat{\mathbf{e}} - \mathbf{e}\|_2 < \FiLMInversionMaxErr$).
```

### B-5. "Validation EER Operating Point" Label Is Incorrect for τ = 0.8910
- **Location:** Research.tex, line 434 (§IV-E, Eq. 4 caption)
- **What is wrong:** `τ = \OperatingThresholdTau{} (validation EER operating point)`. τ = 0.8910 is the **test-set** EER crossover (FAR = FRR = 10.17% on seed 42 test pairs). The validation-transfer threshold is τ_val = 0.8943 (macro `\ValTransferTau`). Calling 0.8910 a "validation" threshold is factually incorrect and contradicts the CONSISTENCY_BEFORE check H which was fixed.
- **Evidence:** `metrics.json`: `"all_alteration.tau_threshold": 0.891` (test-set threshold). `metrics.json`: `"val_transfer_tau": 0.8943`. CONSISTENCY_AFTER CHECK_H: PASS.
- **Why wrong:** Reviewers will question whether the threshold was tuned on test data (it is the test-set EER crossover, which raises a legitimate methodological concern that needs to be stated honestly).
- **Correct information:** τ = 0.8910 is the threshold at which FAR = FRR on the test set (i.e., the test-EER operating point for reporting). The independently validated threshold τ_val = 0.8943 transfers to FAR = 8.82%, FRR = 11.06%.
- **Exact correction:**
```latex
% CURRENT:
where operating threshold $\tau = \OperatingThresholdTau{}$ (validation EER operating point).
% CORRECTED:
where operating threshold $\tau = \OperatingThresholdTau{}$ is the test-set EER crossover point (FAR = FRR at $\tau$); the independently-tuned validation-transfer threshold is $\tau_{\text{val}} = \ValTransferTau{}$ (see Section~\ref{sec:exp}).
```

### B-6. ROC/DET Figure Caption and Distribution Figure Caption: Wrong Pair Count
- **Location:** Research.tex, lines 491, 507, 513 (§V-B)
- **What is wrong:** Three consecutive statements say "10,000 evaluation pairs" and "10,000 pairs each". The headline protocol uses 14,654 pairs. The distribution figure may show scores from a separate 10,000-pair sampling, but this is not documented in macros or RESULTS_PROVENANCE, making these numbers unverifiable with current artifacts.
- **Evidence:** ALL protocol: 14,654 pairs; EASY: 5,374 pairs; nominal: 10,000 pairs (EASY-only based). No macro for "10,000 pairs for figures" is defined.
- **Why wrong:** If the figures use the nominal 10,000-pair protocol, their EERs will differ from the headline 14,654-pair ALL protocol, creating a disconnect between the figures and the reported headline result.
- **Required action:** Clarify in the caption which protocol the figures show, use macros rather than the literal "10,000". If figures use the nominal benchmark, state that explicitly.
- **Exact correction (assuming figures show nominal benchmark):**
```latex
% Lines 491, 507:
% CURRENT: "...on the SOCOFing test partition across 10{,}000 evaluation pairs"
% CORRECTED: "...on the SOCOFing test partition under the nominal 10{,}000-pair benchmark (5{,}000 Easy genuine, 5{,}000 impostor)"

% Line 513:
% CURRENT: "...genuine, stolen-key impostor, legitimate-key impostor, and cross-key pairs (10{,}000 pairs each)."
% CORRECTED: "...genuine, stolen-key impostor, legitimate-key impostor, and cross-key pairs (sampled from the nominal 10{,}000-pair benchmark)."
```

---

## C. Incorrect or Unverifiable Data

### C-1. RESULTS_PROVENANCE.md Contains Outdated Values (Document-Level Issue)
RESULTS_PROVENANCE.md documents an earlier experimental run that has been superseded. Key values in the document that no longer match macros.tex:

| Metric | RESULTS_PROVENANCE value | Current macros.tex value | Direction |
|--------|------------------------|--------------------------|-----------|
| EasyOnlyEER | 2.85% | 2.84% | Small drift |
| NullNoiseFloorMean | 0.0249 | 0.0382 | +53% |
| NullNoiseFloorP (p95) | 0.0291 | 0.0443 | +52% |
| SameServiceAUC | 0.9956 | 0.9592 | −4% |
| ROPLearnedAUC | 0.5121 | 0.5070 | −1% |
| ROPWorstDsys | 0.0275 | 0.0353 | +28% |
| ROPWorstOmega | 0.9725 | 0.9647 | −0.8% |
| BioHashingWorstDsys | 0.0239 | 0.0281 | +18% |
| CKKSMaxAbsErr | 1.24×10⁻⁶ | 1.43×10⁻⁶ | +15% |
| CKKSMeanAbsErr | 9.74×10⁻⁷ | 1.16×10⁻⁶ | +19% |
| PairedCKKSEER | 3.03% | 8.60% | +185% |
| EETOMedian | 25.11 ms | 27.19 ms | +8% |
| ServerDotMedian | 13.29 ms | 13.36 ms | Negligible |
| TVLATStat | 3.23 | 0.75 | Different run |
| TVLAPVal | 0.0013 | 0.4547 | Different run |
| TVLATrialsCount | 2,000 | 10,000 | Different |
| TVLAFixedVar | 0.1387 ms² | 9.581 ms² | Different |
| SaturationThroughput | 120.35 req/s | 11.44 req/s | −91% |
| SaturationConcurrency | 200 | 300 | +50% |
| LocustWorkersCount | 8 | 4 | −50% |
| LocustPeakCPU | 98.5% | 40.0% | −60% |
| LearnedInversionEER | 41.27% | 37.40% | −4% |
| AlterationOverallFRR | 22.25% | 10.17% | −55% |
| CREasyFRR | 1.34% | 0.22% | Significant |
| CRMedFRR | 38.37% | 15.35% | Significant |
| CRHardFRR | 54.47% | 25.56% | Significant |

**Verdict:** RESULTS_PROVENANCE.md is severely out of date and should either be regenerated from the final `metrics.json` or clearly labelled as a historical document representing a prior run, not the submission-ready results.

### C-2. AlterationOverallFRR: PROVENANCE says 22.25%, macros say 10.17%
The RESULTS_PROVENANCE alteration breakdown claims `\AlterationOverallFRR = 22.25%` at threshold τ = 0.9218 (nominal). The current macros set it to `10.17%` at τ = 0.8910 (ALL protocol). The paper body uses the macro correctly (`\AlterationOverallFRR`), so this is internally consistent in the compiled paper. The discrepancy exists between PROVENANCE and macros, not in the paper itself.

### C-3. PreimageEERCos: PROVENANCE says 48.75%, macros say 48.95%
Minor drift; paper uses macro; no paper error.

### C-4. LearnedInversionEER: PROVENANCE says 41.27%, macros say 37.40%
Paper uses `\LearnedInversionEER` (37.40%). The improvement is real — the text "substantial degradation relative to genuine matching, it remains below the 50% chance baseline" is correct for 37.40% too. No paper error.

### C-5. UNVERIFIABLE: HERS (Engelsma et al.) benchmark dataset
- **Location:** Research.tex line 664: "Engelsma et al. evaluate HERS on **LFW** face images"
- **Issue:** LITERATURE_SEARCH.md Table 3 lists HERS as evaluated on IJB-C. The CHANGELOG_EXPERIMENTS.md F12 says "HERS corrected to Face on **LFW**." The actual Engelsma et al. (TPAMI 2022) paper uses IJB-C, not LFW (verifiable only from the original paper, not available in this repository).
- **Status:** UNVERIFIABLE from repository alone; the paper text claims LFW, which may be wrong. If HERS uses IJB-C, the comparison table entry is incorrect.
- **Required action:** Verify against the actual Engelsma et al. paper. If IJB-C, correct line 664 to "IJB-C face images" and update the comparison table.

### C-6. UNVERIFIABLE: Procrustes EER Values from RESULTS_PROVENANCE vs macros
Minor discrepancy: PROVENANCE states n=128 → EER 10.38%, macros say 10.82%; n=256 → 0.10% vs 0.05%; n=64 → 23.00% vs 22.79%. These are small variations consistent with different evaluation seeds. Paper uses macros (correct source of truth).

---

## D. Paper ↔ Code Mismatches

### D-1. HKDF Equation (§IV-C, Eq. 3) vs `core/keys.py`

| Aspect | Paper | Code |
|--------|-------|------|
| HKDF output length | L = 1024 bytes | L = 32 bytes (AES-256 key only) |
| Integer width for k_i | uint32 (4 bytes/element) | uint64 (8 bytes/element) |
| Normalization denominator | 2³² − 1 | 2⁶⁴ + 2 (open-interval mapping) |
| info string | `biometric-auth\|u\|v\|Key` | `{user_id}\|v{version}` (no prefix, no \|Key) |
| Pipeline | HKDF → k_i directly | HKDF → AES-CTR DRBG → Box-Muller → QR |

**Severity:** HIGH. The equation as written cannot reproduce the key material used in experiments.

### D-2. FiLM Inversion Error: Hardcoded literal vs macro
- **Paper line 202:** hardcoded `2.5 × 10⁻⁷`
- **Macro \FiLMInversionMaxErr:** `2.87e-08`
- **Mismatch factor:** ~8.7×

### D-3. Worker Count: Abstract hardcoded "8" vs macro "\LocustWorkersCount" = 4
- See B-1.

### D-4. Android HE Service: Attestation Not Implemented
- **Paper claims:** "The client attests only to a 1-bit boolean decision... client signs the result using its device ECDSA private key: σ = ECDSA-P256(sk_dev, H(d ‖ n_s ‖ v))"
- **Code in `android_he_service/main.py`:** Only provides `/he/encrypt` and `/he/decrypt` endpoints. No attestation, no ECDSA signing, no nonce handling, no 1-bit decision interface.
- **Code in `core/protocol.py`:** Contains pair-sampling logic only, no protocol simulation of attestation.
- **ECDSA code found at:** `phase5_backend/backend/api/verification.py`, `phase6_tee/tee/simulation.py` — outside the `make reproduce` pipeline.
- **Severity:** The 1-bit attestation is listed as a core contribution (Contribution 3). The attestation implementation is not exercised by `make reproduce` and is not covered by the unit test suite or acceptance tests. Reviewers checking the codebase will not find it in the evaluated pipeline.
- **Required correction:** Either wire the attestation into the evaluated pipeline (android_he_service or a combined script), or explicitly state in the paper that the attestation is a protocol specification implemented in the system but not included in the standalone benchmark scripts.

### D-5. CryptoDRBG: `float32` Gaussian floats stored as `float32` but HKDF key is used differently
- `core/keys.py` line `g_floats = drbg.get_gaussian_floats(dim * dim)` returns `float32`.
- `G = g_floats.reshape(dim, dim)` uses float32 for the Gaussian matrix before QR.
- Paper describes Box-Muller without specifying float32 precision — not a major mismatch, but worth noting for reproducibility.

### D-6. AES-CTR nonce hardcoded to zeros
- `core/keys.py` line: `nonce = b'\x00' * 16` — fixed zero nonce.
- Paper does not describe the nonce. For a DRBG this is acceptable (the key is unique per user/version), but should be documented for reproducibility.

---

## E. Experimental/Evaluation Problems

### E-1. Single Trained Encoder: Variance Reported Is Pair-Sampling Only
- **Location:** Abstract, §V-C (Table III), §VI
- **Issue:** The paper repeatedly states "three pair-sampling evaluation seeds" and "pair-sampling variance, not training variance" — this is honestly disclosed. However, the paper does not report training variance from multiple encoder training runs, meaning the headline EER 9.90% ± 0.24% captures only the variance from pair selection, not the variance from model initialization. This is a legitimate limitation that should be in §V-J (Failure Modes and Limitations), and it is partially present there. However, the abstract does not use the phrase "pair-sampling variance" consistently (it does use it once with the macro `\MultiSeedEERText`).
- **Assessment:** Acceptable for a systems paper on a single hardware configuration, but reviewers may ask why only one encoder was trained. A single sentence acknowledging this in the limitations section would help.

### E-2. Stolen-Key EER = 10.17% as Headline Metric
- **Issue:** Because ROP is an isometry, stolen-key EER equals plaintext EER exactly. This means the headline EER reflects the discriminability of the backbone, not any additional benefit of the cancelable scheme. The paper correctly explains this (§III-D), but it means the headline metric cannot improve beyond the backbone and reviewers may ask why ArcFace on SOCOFing achieves only 9.90% when simpler approaches with this dataset can do better.
- **Assessment:** Correctly characterized in the paper. Not a mismatch, but a potential reviewer question.

### E-3. EASY-Only Benchmark Used in ROC/DET Figures
- **Issue (from C-6):** The ROC and DET figures caption says "10,000 evaluation pairs," which corresponds to the nominal benchmark (EASY genuine only, 5,000 genuine + 5,000 impostor). The headline EER used throughout the text is from the ALL protocol (14,654 pairs). Figure 2 and Figure 3 may therefore visually depict an EER different from the headline. No macro for the nominal benchmark EER is explicitly checked in the figure captions.
- **Assessment:** UNVERIFIABLE without regenerating figures. The acceptance test `ROC_FIGURE_LIMITS` checks y-axis bounds but not which protocol is plotted.

### E-4. Load Test Saturation Point Changed Substantially
- The RESULTS_PROVENANCE stated saturation at N=200, X=120.35 req/s (8 workers). The current results show saturation at N=300, X=11.44 req/s (4 workers). This is an 10× reduction in peak throughput and represents a very different system performance claim. The abstract still says "reaching saturation throughput of \SaturationThroughput{}" which now resolves to 11.44 req/s — a realistic value, but the abstract narrative was originally written when the peak was 120 req/s and retains phrasing optimized for that context.

### E-5. Sustainable Operating Point: N=10, X=6.07 req/s, Mean Latency 394ms
- **Issue:** The mean response time at N=10 is 394.77 ms — **not** sub-second in the practical sense. The p95 is 1114.84 ms. For a biometric authentication system, 394 ms mean latency at 10 concurrent users is a modest throughput. The paper correctly reports these numbers but does not contextualize them relative to practical authentication requirements in §V-E.
- **Assessment:** Numbers are correct; framing as a "sustainable operating point" is somewhat misleading given p95 > 1 second even at the lowest tested concurrency.

### E-6. PairedCKKSEER: 8.60% (not 3.03% as in PROVENANCE)
The paired CKKS EER changed from 3.03% to 8.60%, which is consistent with the ALL protocol replacing the EASY protocol as the basis for the paired test. Both plaintext and CKKS EER are 8.60% with ΔEERs = 0.00% — the zero-degradation claim is intact. No paper error; PROVENANCE is outdated.

---

## F. Mathematical/Equation Issues

### F-1. Eq. 3 (HKDF) — See B-2 Above (Critical)

### F-2. Eq. 8 (HE Dot Product): Notation Ambiguity
- **Location:** Research.tex, line 425, Eq. `\label{eq:he_dot}`
- **Issue:** The equation `Enc(sim) = Enc_pk(t_enr) ⊙ Enc_pk(t_prb)` uses `⊙` (element-wise product / Hadamard). For CKKS inner product, this is the element-wise multiplication step, but the inner product requires summation of elements. The actual CKKS inner product is `Σ(t_enr ⊙ t_prb)_i = Σ t_enr_i × t_prb_i`. The notation suggests the result is a vector, not a scalar.
- **Evidence:** `android_he_service/main.py` and TenSEAL documentation: `ckks_vector` multiplication produces element-wise products; the sum/inner product requires an additional `sum()` or rotation. The paper doesn't show the summation step.
- **Why wrong:** The notation is ambiguous — it could be read as computing an element-wise product, not an inner product. CKKS inner product requires the element-wise product followed by a sum, which involves additional rotation and accumulation operations.
- **Recommended correction:**
```latex
% CURRENT:
\text{Enc}(\text{sim}) = \text{Enc}_{\mathsf{pk}}(\mathbf{t}_{\text{enr}}) \odot \text{Enc}_{\mathsf{pk}}(\mathbf{t}_{\text{prb}})
% CORRECTED (clarify that ⊙ denotes CKKS dot product, not Hadamard):
\text{Enc}(\text{sim}) = \langle \text{Enc}_{\mathsf{pk}}(\mathbf{t}_{\text{enr}}),\, \text{Enc}_{\mathsf{pk}}(\mathbf{t}_{\text{prb}}) \rangle_{\text{CKKS}}
```
Or add a footnote: "⊙ denotes the full CKKS inner product (element-wise multiplication followed by summation via ciphertext rotations)."

### F-3. Eq. 1 (ArcFace Loss) — Correct
The ArcFace loss formula matches Deng et al. (2019) with margin m added to θ_{y_i}. Parameters s=64, m=0.5 rad match the paper and are plausible for this dataset. No error.

### F-4. ROP Isometry (Eq. 4-5) — Correct
`⟨t₁, t₂⟩ = e₁ᵀQᵀQe₂ = e₁ᵀe₂` is mathematically correct for orthogonal Q. Verified numerically: max |QᵀQ − I| = 1.79×10⁻⁷ < 10⁻⁵. No error.

### F-5. Cross-Key Inner Product Variance Claim
- **Location:** §IV-D (ROP design): "σ_cross ≈ 1/√D = 0.0625"
- **Verification:** For D=256, 1/√256 = 0.0625. This is the standard deviation under the Gaussian approximation for random orthogonal matrices. Correct.

### F-6. FiLM Energy Fraction Claim
- **Location:** §IV-D2: "biometric term accounts for 1/(1 + ‖β‖₂²) ≈ 90%"
- **With \FiLMNormBeta = 0.3276:** 1/(1 + 0.3276²) = 1/(1 + 0.1073) = 1/1.1073 ≈ 0.903 = 90.3%. Correct.

### F-7. CKKS Four Orders of Magnitude Claim
- **Location:** §V-D: "maximum homomorphic approximation error (1.43×10⁻⁶) is four orders of magnitude smaller than the margin between genuine similarity (0.950) and the operating threshold (0.8910)"
- **Calculation:** margin = 0.950 − 0.8910 = 0.059; ratio = 0.059/1.43×10⁻⁶ = 41,259 ≈ 4.6 orders of magnitude. The claim of "four orders" is correct (conservative).

---

## G. Figure/Table Issues

### G-1. Table III Caption: "10,000 Pairs" — See B-3 Above (Critical)

### G-2. Figure 2/3 Captions: "10,000 evaluation pairs" — See B-6 Above

### G-3. Table Load-Test Caption: "LocustWorkersCount Workers" — Correct
The table caption uses `\LocustWorkersCount` (= 4) correctly.

### G-4. Table VIII (Load Test) Content: Verified
DISCREPANCY_REPORT §1 provides the multi-repetition results. The five concurrency tiers {10, 25, 50, 100, 200} are confirmed (CHANGELOG §9). The N=300 row is in DISCREPANCY_REPORT but was removed from the paper for N in {10,25,50,\SustainableConcurrency,\SaturationConcurrency} = {10,25,50,10,300}. Wait — there's a potential redundancy: N={10,25,50,10,300} would be {10,25,50,300} since \SustainableConcurrency=10 and \SaturationConcurrency=300. The paper says `N ∈ {10, 25, 50, \SustainableConcurrency, \SaturationConcurrency}` which expands to `{10, 25, 50, 10, 300}` — listing N=10 twice. This is a minor authoring mistake.
- **Correction:** Replace with `N \in \{10, 25, 50, 100, \SaturationConcurrency\}` or expand to the five distinct values.

### G-5. Table II (Specifications) — TAR@1%FAR
CHANGELOG F11 documents that TAR@1%FAR (71.72%) is below the >95% design target and should show "Not Met." The ACCEPTANCE_AFTER confirms "NOT_MET_RESTRICTION: 'not met' appears strictly in TAR row." Table II content appears correct.

### G-6. Table IX (Prior Work) — BFV vs BFV Attribution
- **Location:** Research.tex line 664 and Table IX
- **Issue:** The paper states "Engelsma et al. evaluate HERS on LFW face images under BFV." The LITERATURE_SEARCH table shows the benchmark as IJB-C and HERS uses BFV/SEAL, which is correct. The dataset attribution (LFW vs IJB-C) is UNVERIFIABLE without the Engelsma et al. paper.

### G-7. Figure 1 (Pipeline Diagram)
The tikz pipeline correctly shows the 8 processing stages listed in Table VII. Labels (Client/Server) match the protocol description. No error.

### G-8. Alteration FRR Table Values — PROVENANCE vs Macros
RESULTS_PROVENANCE states CR Easy=1.34%, Medium=38.37%, Hard=54.47%. Current macros: 0.22%, 15.35%, 25.56%. These are not errors in the paper (paper uses macros), but the dramatic changes (Hard CR dropped from 54.47% to 25.56%) suggest a threshold change from τ=0.9218 to τ=0.8910 explains the improvement. This is correct — the macro is evaluated at the current threshold. Paper is consistent.

---

## H. Citation/Reference Issues

### H-1. All 26 References Present — No Unresolved Citations
ACCEPTANCE_AFTER confirms: FORBIDDEN_UNRESOLVED_REF and FORBIDDEN_DOUBLE_QMARK both PASS. All 26 cited keys (jain2016biometric, ratha2001enhancing, ratha2007generating, rathgeb2011survey, nandakumar2015biometric, gentry2009fully, boddeti2018secure, engelsma2022hers, teoh2004biohashing, jin2018ranking, deng2019arcface, schroff2015facenet, pinto2019demystifying, cheon2017homomorphic, li2021ckks, perez2018film, albrecht2018standard, shehu2018sokoto, he2016deep, wen2016discriminative, chen2018mobilefacenets, oreshkin2018tadam, benaissa2021tenseal, iso24745, gomez2018framework) are present in references.bib.

### H-2. HERS Benchmark Dataset Attribution — Potential Error
- **Location:** Line 664, Table IX
- See C-5 above. Research.tex claims LFW; LITERATURE_SEARCH.md claims IJB-C. UNVERIFIABLE from this repository.

### H-3. BioHashing Citation Correct
`teoh2004biohashing` cited for BioHashing is Teoh et al. (2004). CHANGELOG F12 confirms this was fixed from a previously broken key.

### H-4. IoM Citation Correct
`jin2018ranking` cited for Index-of-Max is Jin et al. (2018 TIFS). Correct.

### H-5. Missing Citation for Mezzadri (2007) Sign Correction
- **Location:** §IV-D1: "QR decomposition with Mezzadri diagonal sign correction produces a Haar-distributed orthonormal matrix"
- **Issue:** "Mezzadri (2007)" is referenced in the code comment (`core/keys.py`) but no corresponding citation key appears in references.bib or Research.tex.
- **Correct information:** F. Mezzadri, "How to Generate Random Matrices from the Classical Compact Groups," Notices of the AMS, 54(5):592–604, 2007.
- **Recommended correction:** Add `@article{mezzadri2007random,...}` to references.bib and add `~\cite{mezzadri2007random}` after "Mezzadri diagonal sign correction" in the text.

### H-6. Missing Citation: RFC 5869 (HKDF)
- **Location:** §IV-C: "HKDF-SHA256 (RFC 5869)"
- **Issue:** The paper mentions RFC 5869 in text but there is no `@techreport{rfc5869,...}` in references.bib.
- **Recommended correction:** Add IETF RFC 5869 to references.bib and cite it alongside the HKDF derivation equation.

---

## I. Unsupported or Exaggerated Claims

### I-1. "1-bit attestation mitigating Li–Micciancio key-recovery" — Partially Supported
- **Location:** Abstract, §I, §III-A, §VI
- **Claim:** "The client attests only to a 1-bit boolean decision, mitigating score-oracle attacks" and "concealing continuous similarity scores from the server to mitigate score-oracle and Li–Micciancio key-recovery attacks"
- **Evidence:** The ECDSA attestation protocol is not implemented in the benchmarked codebase (see D-4). The `android_he_service/main.py` returns the decrypted scalar score directly from `/he/decrypt` — it does not enforce the 1-bit decision at the service layer.
- **Assessment:** The protocol design is sound and correctly specified in the paper. However, "our protocol mitigates" these attacks implies the evaluated implementation enforces this, which it does not at the API boundary. The word "mitigating" is acceptable; "strictly prevented" would be overclaiming (which is correctly removed per CHANGELOG F13).

### I-2. "128-bit classical security" for CKKS
- **Claim:** Polynomial degree N=8192, coeff_mod = {60,40,40,60} (200 bits total) provides 128-bit classical security.
- **Evidence:** `params.yaml`: `security_level: 128`. Albrecht et al. 2018 standard: for N=8192 and log(Q) ≤ 218 bits, classical security is ≥128 bits. Current log(Q) = 200 bits < 218. **Claim is correct and well-supported.**

### I-3. "Zero Error Degradation" for CKKS
- **Claim:** CKKS yields "zero error degradation" and ΔEERs = 0.00%
- **Evidence:** macros.tex `\PairedCKKSEERDiff{0.00\%}`, `\PairedPlaintextEER{8.60\%}`, `\PairedCKKSEER{8.60\%}`.
- **Verification:** At 8.60% EER for both, the difference is 0 to at least 2 decimal places. This is on 1,000 paired comparisons, which is a limited sample. The claim should be stated as "no detectable degradation" or retain the 95% CI [0.00%, 0.00%] to fully characterize the precision.
- **Assessment:** Correct within the tested pairs; the CI shows the bound.

### I-4. "Learned Neural Inversion Achieves 37.40% EER — Below 50% Chance Baseline"
- **Claim:** §V-F: "demonstrates substantial degradation but acknowledging partial feature leakage below the 50% chance baseline"
- **Evidence:** `\LearnedInversionEER{37.40\%}`. 37.40% < 50% indicates the MLP does learn some structure (Rank better than chance), but EER at 37.40% means ~37% of attempts fail equally for both classes — so ~63% discriminability is retained in the attack.
- **Assessment:** The claim is factually correct. The wording "partial feature leakage" is appropriately measured. Previously overclaimed as "chance level" (CHANGELOG F13 removed that framing).

### I-5. "Dense Spherical Rotation" and "Dense Coordinate Diffusion"
- **Claim:** §IV-D1 and multiple locations describe ROP as providing "dense coordinate diffusion" and "dense spherical rotation"
- **Assessment:** Technically accurate — a random orthogonal matrix in ℝ²⁵⁶×²⁵⁶ with Haar distribution provides maximum diffusion (each output coordinate depends on all input coordinates). This is not overclaiming.

---

## J. Reproducibility Problems

### J-1. HKDF Equation Cannot Be Used to Reproduce Key Derivation
See B-2. The equation as written will not reproduce the actual key material.

### J-2. FiLM Generator Checkpoint Not Described (Training Details Absent)
- The FiLM generator `exports/film_generator.pt` is referenced in acceptance tests and scripts.
- The paper describes two-phase training (50+50 epochs) with joint loss (Eq. 7), but does not specify: (a) which optimizer was used for the FiLM generator jointly; (b) learning rate schedule for the joint phase; (c) batch composition strategy.
- These details are in the codebase (CHANGELOG F1) but not in the paper.

### J-3. No Random Seed for Model Training
- The paper specifies three evaluation seeds (42, 123, 456) for pair sampling, but no training seed is reported for the ResNet-18 encoder.
- For true reproducibility, the training seed (for parameter initialization and data augmentation) should be specified.

### J-4. Model Checkpoint Not Provided
- No encoder checkpoint file is included in the repository (SOCOFing is a free dataset but the trained encoder is not archived).
- `make reproduce` re-runs experiments from `results/raw/socofing_test_embeddings.npz`, suggesting the checkpoint is implicit in the pre-computed embeddings file.
- Reproducibility requires either the checkpoint or an instruction to regenerate it.

### J-5. `make reproduce` Pipeline Dependency
- `make reproduce` runs experiments from pre-computed embeddings (npz files).
- Reproducing the embeddings themselves requires: (a) downloading SOCOFing, (b) preprocessing, (c) training the encoder.
- The Makefile has no `train` target, and no training script is referenced.

### J-6. AES-CTR Nonce Is Hardcoded to Zeros
- Not documented in the paper. Reproducible (deterministic), but should be stated.

---

## K. Writing/Formatting Problems

### K-1. "Validation EER Operating Point" — Wrong Label (See B-5)
The label at line 434 is incorrect. The threshold is a test-set EER crossover.

### K-2. Inconsistent Use of "Nominal Benchmark"
The paper uses "nominal 10,000-pair benchmark" in two places (§IV-D, §V-J). Readers encounter this term before it is defined. A forward reference or earlier definition would improve clarity.

### K-3. Abstract Uses `\MultiSeedEERText` Macro
The abstract contains `\MultiSeedEERText{}` which expands to "9.90 +/- 0.24 percent" — a non-standard textual form. IEEE templates typically prefer numerics in the abstract for machine readability. Current acceptance test passes (233 words, ≤250), but the expansion is stylistically unusual.

### K-4. Conclusions Refer to "Emulated Context (Table I)" Three Times
The phrase "emulated context (Table I)" appears multiple times in Section VI (Conclusion). Since the reader has finished reading the paper, a forward reference to Table I is awkward. Simplify to "software-emulated secure context" in the conclusion.

### K-5. "As disclosed in Section~\ref{sec:encoder_design}" in Limitations (§V-J)
Section V-J Failure Mode 5 says "As disclosed in Section~\ref{sec:encoder_design}" — a self-referential disclosure note within the same section group. This is mildly redundant. Acceptable but could be streamlined.

### K-6. Abstract Claims LocustPeakLatencyMean = \LocustPeakLatencyMean = "24900.39 ms" and p99 = "34.70 s"
Both values are correctly presented through macros but a mean latency of 24.9 seconds and p99 of 34.7 seconds at saturation are striking performance numbers. These correctly characterize an overloaded server, but the abstract framing "reaching saturation throughput of 11.44 req/s under 300 clients" without contextualizing that this is a severely degraded operating point may mislead readers into thinking 11.44 req/s is a useful performance regime. The body text correctly contextualizes this; the abstract does not.

---

## L. Required Experiments or Reruns

### L-1. Regenerate RESULTS_PROVENANCE.md from Current `metrics.json`
`RESULTS_PROVENANCE.md` is severely out of date (30+ values differ from macros.tex). It must be regenerated or explicitly marked as historical. If submitted, reviewers will find contradictions with the paper.

### L-2. Verify HERS (Engelsma et al.) Dataset: LFW vs IJB-C
Check the actual Engelsma et al. TPAMI 2022 paper. If it uses IJB-C (not LFW), correct line 664 and Table IX.

### L-3. Optional: Multiple Training Runs for Training Variance
To fully support the EER claim, 3–5 independent training runs would provide training variance alongside the reported pair-sampling variance. This is optional but strengthens the claim.

### L-4. Pair Count Clarification for ROC/DET Figures
Determine which protocol the ROC/DET curves and distributions plot was generated under (nominal 10,000 or ALL 14,654) and update captions to match.

---

## M. Exact Corrections Required

### M-1 (Critical): Abstract Worker Count
See B-1. Replace hardcoded "8-worker" with `$\LocustWorkersCount$-worker`.

### M-2 (Critical): HKDF Equation
See B-2. Rewrite Eq. 3 to accurately describe the two-stage pipeline (HKDF → 32-byte AES key → AES-256-CTR DRBG → uint64 uniform floats → Box-Muller) and update info string to match code.

### M-3 (Critical): Table III Caption
See B-3. Replace "10,000 Pairs" with exact protocol-specific counts using macros.

### M-4 (Critical): FiLM Inversion Error
See B-4. Replace hardcoded `2.5 \times 10^{-7}` with `\FiLMInversionMaxErr`.

### M-5 (Important): τ Label
See B-5. Change "validation EER operating point" to "test-set EER crossover (FAR=FRR at τ)."

### M-6 (Important): ROC/DET/Distribution Figure Captions
See B-6. Update "10,000 evaluation pairs" to state which protocol. Use macros.

### M-7 (Minor): Load Test N Set Syntax
See G-4. Fix `$N \in \{10, 25, 50, \SustainableConcurrency, \SaturationConcurrency\}$` which expands to listing N=10 twice to something like `$N \in \{10, 25, 50, 100, \SaturationConcurrency\}$`.

### M-8 (Important): Add Mezzadri (2007) Citation
See H-5. Add reference and cite where "Mezzadri diagonal sign correction" is mentioned.

### M-9 (Minor): Add RFC 5869 Citation
See H-6. Add IETF RFC 5869 to references.bib and cite alongside HKDF derivation.

### M-10 (Important): Regenerate or Supersede RESULTS_PROVENANCE.md
See L-1. Either regenerate from current metrics.json or add a clear header "HISTORICAL — see results/final/macros.tex for current values."

### M-11 (Important): Clarify 1-bit Attestation Implementation Scope
Add a sentence to the software boundary section (or §V-J Failure Modes) noting that the ECDSA 1-bit attestation is implemented in `phase5_backend/` and exercised separately; the `make reproduce` benchmark exercises HE computation but evaluates attestation logic through the acceptance test suite.

### M-12 (HE Equation): Clarify CKKS Dot Product Notation
See F-2. Add a clarification that `⊙` in Eq. 8 denotes the full CKKS inner product (element-wise multiply + sum via rotations), not just a Hadamard product.

---

## N. Final Corrected Text for Sections Requiring Modification

### N-1. Abstract Line 49 (Worker Count)
```latex
% REPLACE:
On an 8-worker server, the architecture achieves a sustainable operating point of \SustainableThroughput{} at \SustainableConcurrency{} concurrent clients (p95 latency \SustainableLatencyPNinetyFive{}), reaching saturation throughput of \SaturationThroughput{} under \SaturationConcurrency{} clients (mean latency \LocustPeakLatencyMean{}, p99 \LocustPeakLatencyPNinetyNine{}).

% WITH:
On a $\LocustWorkersCount$-worker server, the architecture achieves a sustainable operating point of \SustainableThroughput{} at \SustainableConcurrency{} concurrent clients (p95 latency \SustainableLatencyPNinetyFive{}), reaching saturation throughput of \SaturationThroughput{} under \SaturationConcurrency{} concurrent clients (mean latency \LocustPeakLatencyMean{}, p99 \LocustPeakLatencyPNinetyNine{}).
```

### N-2. Section IV-C, Eq. 3 and Surrounding Text
```latex
% REPLACE (lines 340–345):
\begin{align}
  \text{PRK} &= \text{HMAC-SHA256}(\text{salt}=\mathbf{0}_{32}, \text{IKM}=\mathbf{s}) \nonumber \\
  \text{OKM} &= \text{HKDF-Expand}(\text{PRK}, \text{info}_{u, v}, L=1024) \nonumber \\
  k_i &= \frac{\text{uint32}(\text{OKM}[4i : 4i+4])}{2^{32} - 1} \times 2.0 - 1.0
  \label{eq:hkdf_derivation}
\end{align}
where $\text{info}_{u, v} = \texttt{biometric-auth|u|v|Key}$ binds the derivation to user ID $u$ and key version $v$.

% WITH:
\begin{align}
  \text{PRK} &= \text{HMAC-SHA256}(\text{salt}=\mathbf{0}_{32}, \text{IKM}=\mathbf{s}) \nonumber \\
  K_{\text{AES}} &= \text{HKDF-Expand}(\text{PRK},\, \text{info}_{u, v},\, L=32) \nonumber \\
  \{r_i\}_{i=1}^{D} &= \text{AES-256-CTR-DRBG}(K_{\text{AES}}) \xrightarrow{\text{uint64}} (0,1)^D \nonumber \\
  k_i &= r_i \times 2.0 - 1.0
  \label{eq:hkdf_derivation}
\end{align}
where $\text{info}_{u, v} = \texttt{\{user\_id\}|v\{version\}}$ binds the derivation to user ID $u$ and key version $v$; $K_{\text{AES}}$ is a 32-byte AES-256 seed; the DRBG generates 64-bit uniform integers mapped to $(0,1)$ via $(u+1)/(2^{64}+2)$.
For ROP, the DRBG additionally generates $D^2$ Gaussian entries via Box-Muller transformation~\cite{mezzadri2007random}, yielding $\mathbf{G} \sim \mathcal{N}(0,1)^{D \times D}$, from which $\mathbf{Q}$ is produced by QR decomposition with Mezzadri diagonal sign correction.
```

### N-3. Table III Caption
```latex
% REPLACE (line 548):
\caption{Verification and Identification Performance Across Representation Schemes (10,000 Pairs, Evaluation Seeds 42, 123, 456)}

% WITH:
\caption{Verification and Identification Performance Across Representation Schemes
(ALL Protocol: \AllAlterationTotalPairs{} pairs; EASY Protocol: \EasyOnlyTotalPairs{} pairs;
Evaluation Seeds 42, 123, 456; single trained encoder, pair-sampling variance only)}
```

### N-4. FiLM Inversion Error (Threat Model, Line 202)
```latex
% REPLACE:
with the unique positive real root recovering $\mathbf{e}$ up to machine precision ($\|\hat{\mathbf{e}} - \mathbf{e}\|_2 < 2.5 \times 10^{-7}$).

% WITH:
with the unique positive real root recovering $\mathbf{e}$ up to machine precision ($\|\hat{\mathbf{e}} - \mathbf{e}\|_2 < \FiLMInversionMaxErr$).
```

### N-5. Operating Threshold Label (Line 434)
```latex
% REPLACE:
where operating threshold $\tau = \OperatingThresholdTau{}$ (validation EER operating point).

% WITH:
where operating threshold $\tau = \OperatingThresholdTau{}$ is the test-set EER crossover point (FAR\,=\,FRR\,=\,\NominalTestFAR{} at $\tau$); the validation-transfer threshold $\tau_{\text{val}} = \ValTransferTau{}$ is disclosed in Section~\ref{sec:exp}.
```

### N-6. ROC/DET Figure Captions (Lines 491, 507, 513)
```latex
% REPLACE line 491:
Fig.~\ref{fig:roc_det} presents measured ROC and DET curves on the SOCOFing test partition across 10{,}000 evaluation pairs.

% WITH:
Fig.~\ref{fig:roc_det} presents measured ROC and DET curves on the SOCOFing test partition under the nominal 10{,}000-pair benchmark (5{,}000 Easy genuine, 5{,}000 impostor).

% REPLACE line 507:
\caption{Empirical verification curves on the SOCOFing test partition across 10{,}000 evaluation pairs.

% WITH:
\caption{Empirical verification curves on the SOCOFing test partition (nominal 10{,}000-pair benchmark: 5{,}000 Easy genuine, 5{,}000 impostor pairs).

% REPLACE line 513:
Fig.~\ref{fig:distributions} illustrates the empirical cosine similarity distributions for genuine, stolen-key impostor, legitimate-key impostor, and cross-key pairs (10{,}000 pairs each).

% WITH:
Fig.~\ref{fig:distributions} illustrates the empirical cosine similarity distributions for genuine, stolen-key impostor, legitimate-key impostor, and cross-key pairs (nominal 10{,}000-pair benchmark).
```

### N-7. Load Test N-Set Expansion (Line 628)
```latex
% REPLACE:
across $N \in \{10, 25, 50, \SustainableConcurrency, \SaturationConcurrency\}$ simulated clients

% WITH:
across $N \in \{10, 25, 50, 100, \SaturationConcurrency\}$ simulated clients
```

### N-8. HE Inner Product Equation (Eq. 8, Lines 424–426) — Clarification Note
```latex
% AFTER the equation, add a footnote or sentence:
% Current:
\text{Enc}(\text{sim}) = \text{Enc}_{\mathsf{pk}}(\mathbf{t}_{\text{enr}}) \odot \text{Enc}_{\mathsf{pk}}(\mathbf{t}_{\text{prb}})
% ADD clarification: "where $\odot$ denotes the CKKS inner product: element-wise ciphertext multiplication followed by homomorphic summation via ciphertext rotations."
```

### N-9. References: Add Mezzadri (2007)
```bibtex
@article{mezzadri2007random,
  author  = {Mezzadri, Francesco},
  title   = {How to Generate Random Matrices from the Classical Compact Groups},
  journal = {Notices of the American Mathematical Society},
  volume  = {54},
  number  = {5},
  pages   = {592--604},
  year    = {2007}
}
```
And in text (§IV-D1): add `~\cite{mezzadri2007random}` after "Mezzadri diagonal sign correction".

### N-10. RESULTS_PROVENANCE.md — Add Warning Header
Add the following to line 1 of RESULTS_PROVENANCE.md:
```markdown
> ⚠️ **HISTORICAL DOCUMENT — DO NOT USE AS GROUND TRUTH**  
> This provenance record documents an earlier experimental run and has been superseded by the final results in `results/final/metrics.json` and `results/final/macros.tex`. All quantitative values in the paper derive exclusively from the current macros.tex.
```

---

## Summary Table of Issues by Severity

| ID | Location | Severity | Status |
|----|----------|----------|--------|
| B-1 | Abstract line 49 | CRITICAL | Wrong worker count |
| B-2 | §IV-C, Eq. 3 | CRITICAL | 3 HKDF mismatches |
| B-3 | Table III caption | CRITICAL | Wrong pair count |
| B-4 | §III-B line 202 | CRITICAL | Hardcoded FiLM inversion error |
| B-5 | Eq. 4 line 434 | IMPORTANT | Wrong τ label |
| B-6 | Figs 2/3 captions | IMPORTANT | Wrong pair count |
| D-4 | §I/III contributions | IMPORTANT | 1-bit attestation not in main pipeline |
| F-2 | Eq. 8 | MODERATE | CKKS ⊙ notation ambiguity |
| G-4 | Load test text line 628 | MINOR | N set lists N=10 twice |
| H-5 | §IV-D1 | MODERATE | Missing Mezzadri citation |
| H-6 | §IV-C | MINOR | Missing RFC 5869 citation |
| H-2/C-5 | Table IX line 664 | IMPORTANT | HERS dataset: LFW vs IJB-C (UNVERIFIABLE) |
| K-1 | §V text | MODERATE | τ labeled "validation" again elsewhere |
| L-1 | RESULTS_PROVENANCE.md | IMPORTANT | Outdated support document |

**Blocking for submission:** B-1, B-2, B-3, B-4, B-5, H-2/C-5 (pending external verification), and the clarity of D-4.

**Non-blocking but should be fixed:** B-6, F-2, G-4, H-5, H-6, L-1.
