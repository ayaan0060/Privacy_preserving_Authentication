# Adversarial Fact-Check Report — Part 2
## "Privacy-Preserving Fingerprint Authentication Using Cancelable Templates and CKKS Homomorphic Encryption"

**Reviewer Role:** Skeptical peer reviewer — adversarial independent verification  
**Date of Review:** Based on current workspace state  
**Files Reviewed:** Research.tex, results/final/macros.tex, results/final/metrics.json, params.yaml, core/unlinkability.py, core/keys.py, core/protocol.py, phase6_tee/tee/simulation.py, phase6_tee/tee/interface.py, phase6_tee/tee/device_keys.py, scripts/run_attestation_benchmark.py, LITERATURE_SEARCH.md, CHANGELOG_EXPERIMENTS.md, references.bib, .agents/tasks/audit-report.md, tables/tab_prior_work.tex

---

## Section A: Security and Privacy Claims

### A.1 Verification Table

| # | Claim | Implementation Evidence | Verdict | Notes |
|---|-------|------------------------|---------|-------|
| A1 | "128-bit classical security" for CKKS | params.yaml: N=8192, coeff_mod_bit_sizes=[60,40,40,60], total log Q = 200 bits. Per homomorphicencryption.org standard (albrecht2018standard), N=8192 with log Q ≤ 218 bits achieves 128-bit classical security at std_dev=3.2. Research.tex §IV-F states "total 200 bits ≤ 218 bits bound." | **VERIFIED** (with caveats) | The 218-bit bound cited is the HE.org standard. N=8192 + log Q = 200 is within limits. However, the paper does **not** verify that TenSEAL's actual SEAL instantiation matches exactly — it relies on the library's parameter validation. The security_level: 128 field in params.yaml is self-asserted, not independently derived. **Caveat: "128-bit security" is only valid if the homomorphic encryption standard's requirement for the specific (N, logQ, error distribution) triple is met. The HE.org 2018 standard table shows N=8192, logQ ≤ 218 achieves 128 classical bits, which the parameters satisfy. Claim is technically correct but reviewers should note this depends on the LWE estimator version.** |
| A2 | "Zero-score-leakage / 1-bit attestation prevents Li-Micciancio attack" | simulation.py `verify_and_sign_core()` decrypts `similarity = he_client.decrypt_score(encrypted_similarity)` and embeds the float in `create_signed_payload()`. However, the signed payload structure in `run_attestation_benchmark.py` uses `H(d ‖ n_s ‖ v)` — hashing only the decision bit, nonce, and version. The similarity float is NOT in the server-bound payload. | **PARTIALLY VERIFIED — CRITICAL DISCREPANCY** | **Two implementations conflict.** `simulation.py::create_signed_payload()` includes `struct.pack('>d', similarity_score)` in the raw payload bytes — the full float similarity is embedded in the signed payload. The server receives `signed_payload` + `signature`, so it receives the similarity float inside the signed payload. Contrast: `run_attestation_benchmark.py::_create_payload()` correctly hashes only `H(d ‖ n_s ‖ v)` without the similarity float. The paper claims (§IV-E) the signature covers only `H(d ‖ n_s ‖ v)`. The benchmark script matches the paper. The TEE simulation does NOT match the paper — it leaks the similarity float to the server in the signed payload. **This is a direct contradiction between the claimed security property and the primary TEE implementation.** |
| A3 | "ROP non-invertibility: reconstructing the original biometric without the key is computationally hard" | Research.tex §III-C states "For ROP, Cosine EER is 48.95%, Absolute-Value EER 48.98%, Sorted-Magnitude 49.45%, learned MLP 37.40% EER." The paper correctly contextualizes preimage ambiguity rather than claiming formal computational hardness. | **MOSTLY CORRECT — NUANCE ISSUE** | The paper in §I correctly states "irreversibility (reconstructing the original biometric without the key is computationally hard)" as an ISO/IEC 24745 criterion. It never formally proves this is computationally hard — it provides empirical evidence of preimage ambiguity (near-chance EERs) under unknown key. The paper does **not** formally state this as a computational hardness assumption; it presents empirical support. This is a mild but real gap: the ISO criterion requires computational hardness; the paper only demonstrates empirical difficulty. The 37.40% learned MLP EER (below 50% chance) is honestly disclosed as "partial feature leakage" and is a commendable admission. No overclaiming detected in the current revision. |
| A4 | "ISO/IEC 24745 unlinkability: ROP achieves Dsys indistinguishable from noise floor" | macros.tex: ROPWorstDsys=0.0353, NullNoiseFloorP=0.0443, NullNoiseFloorMean=0.0382. ROPWorstDsys=0.0353 < NullNoiseFloorP95=0.0443. unlinkability.py implements Gómez-Barrero D_sys with permutation null calibration. | **VERIFIED WITH QUANTIFICATION CAVEAT** | The claim is technically supported: ROP D_sys (0.0353) < null p95 (0.0443). However, the gap is only 0.009 — the ROP Dsys sits at approximately the 70th percentile of the null distribution (above the null mean of 0.0382 − by actually it is above the mean: 0.0353 < 0.0382 so ROP Dsys is *below* the null mean). This is correct. The permutation null is well-implemented. **One methodological concern:** the Gómez-Barrero metric as implemented uses a histogram density estimator with 100 fixed bins — the resolution is limited. The D_sys values near 0.03–0.04 are well within the estimator noise, so calling them "indistinguishable from noise" is accurate. Bootstrap CIs are computed in `compute_bootstrap_cis()` but the paper does not always report CI bounds for Dsys — it should, to substantiate the "indistinguishable" claim. |
| A5 | "Key revocation: HKDF with v vs v+1 produces cryptographically independent templates" | keys.py `derive_hkdf_bytes()`: `info = f"{user_id}|v{version}"`. Different version → different HKDF info string → different PRK context → independent key material. HKDF-SHA256 with distinct info strings produces computationally independent outputs under HMAC-SHA256 security. | **VERIFIED** | The HKDF domain separation via info strings is cryptographically sound per RFC 5869. Distinct info strings produce independent pseudorandom outputs. The claim is correct. The code matches the paper's description of info_uv. |
| A6 | TEE simulation vs hardware security claims | simulation.py header: "⚠️ THIS IS NOT A REAL HARDWARE SECURITY BOUNDARY." interface.py: `tee_type="simulation"`. Research.tex Table I (tab_tee_boundary) clearly labels the evaluation column as "Software Emulation (Apple Silicon Laptop)" vs "Hardware TEE Target." §IV-G "Attestation Implementation Scope" explicitly states: "The ECDSA 1-bit attestation protocol is fully implemented in the phase5_backend/ module..." | **CORRECTLY REPRESENTED** | The paper does NOT over-claim hardware TEE security. Table I clearly distinguishes simulation from hardware target. The text consistently says "emulated context (Table I)" and "software-emulated test context." The abstract says only "a 1-bit boolean decision, mitigating score-oracle attacks" without claiming hardware isolation. This is honestly represented. |
| A7 | "Nonce replay protection" | run_attestation_benchmark.py Test 5 verifies replay protection via `used_nonces` set. simulation.py `verify_and_sign_core()` checks `if nonce in used_nonces: raise NonceReplayError`. Load test script (run_load_test.py) — nonce is not a focus of load testing; attestation tests are separate. | **VERIFIED IN ATTESTATION BENCHMARK — NOT IN LOAD TEST** | Replay protection is correctly implemented and tested in the attestation benchmark. The load test evaluates throughput of the HE service, not the full attestation flow. The paper correctly states nonces are per-session single-use with 5-minute TTL. No overclaiming detected. Limitation: the load test does not exercise the full attestation protocol, but the paper explicitly acknowledges this scope separation. |
| A8 | FiLM "fails" against absolute-value attack (AUC ~1.0) | macros.tex: FiLMAbsAUC=0.9413, FiLMLearnedAUC=0.9338, FiLMWorstDsys=0.6844. | **CONFIRMED FINDING — NOT CHERRY-PICKING** | FiLMAbsAUC=0.9413 is a genuine empirical failure of FiLM under absolute-value attack. This is not cherry-picking: it is a known and expected property of coordinate-wise scaling (|γᵢeᵢ + βᵢ| correlates with |eᵢ| when γᵢ and βᵢ are consistent). The CHANGELOG F1 shows FiLM was the candidate scheme and honest evaluation led to its demotion — this is methodologically sound. Calling it a "failure" is appropriate scientific language. The comparison to ROP (ROPAbsAUC=0.5112) provides meaningful contrast. |

---

### A.2 Critical Issue: Similarity Float Leaked in simulation.py

**This deserves special attention.** In `phase6_tee/tee/simulation.py`, the function `create_signed_payload()` constructs the payload as:

```python
payload = nonce  # 32 bytes
payload += struct.pack('>d', similarity_score)  # 8 bytes — THE FLOAT IS HERE
payload += struct.pack('>I', key_version)
payload += device_id_bytes
payload += timestamp.isoformat()
payload += struct.pack('>B', 1 if verified else 0)
```

The `VerificationResult` dataclass includes `signed_payload` which is returned to the caller. If the server ever accesses `result.signed_payload`, it obtains the raw similarity float despite the paper claiming "The similarity score sim is never revealed to the server."

The benchmark script (`run_attestation_benchmark.py`) correctly hashes `H(d ‖ n_s ‖ v)` without the similarity float. But the TEE simulation (`simulation.py`) returns the full payload containing the similarity float to whoever calls `verify_and_sign`.

**Verdict: The production TEE implementation (simulation.py) contradicts the score-concealment security claim. The paper's security argument is valid only if the server is never given access to `signed_payload` — but if the server verifies the signature using `verify_signature(public_key, payload, signature)` (also defined in simulation.py), it receives the full payload including the similarity score. This directly enables the Li-Micciancio oracle attack the paper claims to prevent.**

---

## Section B: Novelty Claims

### B.1 Assessment

**Key novelty claim:** "To our knowledge, an integrated framework uniting deep representation learning, cancelable orthogonal projection with rigorous empirical unlinkability verification, sub-30ms approximate homomorphic evaluation, and 1-bit score-concealing attestation has not been previously evaluated."

#### B.1.1 CKKS Combined with Cancelable Biometrics

**Assessment:** LITERATURE_SEARCH.md documents a systematic search across IEEE Xplore, Google Scholar, ACM DL, DBLP, finding 84 hits for "cancelable biometrics AND homomorphic encryption" on IEEE Xplore. The search identifies two categories: (A) integer HE on raw embeddings (Boddeti 2018, Engelsma 2022), and (B) plaintext cancelable transforms (BioHashing, IoM). No prior work combining CKKS approximate HE with a formally evaluated cancelable orthogonal projection is identified. **The novelty claim appears defensible on current literature**, though the search was conducted in "October 2026" (a future date — this is a timestamp inconsistency in the document, raising questions about the search's actual date). The search protocol and hit counts appear plausible but cannot be independently verified from this repository.

#### B.1.2 "Sub-30ms CKKS Biometric Matching" — Is This Novel vs. Boddeti 2018?

**Assessment:** Boddeti 2018 (BTAS) reported **1,240ms** for BFV integer HE on facial embeddings, not CKKS. CKKS is a different scheme enabling floating-point arithmetic. The sub-30ms claim specifically refers to CKKS approximate HE inner products (13.36ms server-side). Boddeti used BFV (exact integer HE) which is inherently slower. The speed advantage comes from using CKKS (approximate) vs. BFV (exact). **This claim is defensible — CKKS was not used in Boddeti 2018.** However, readers comparing raw latency numbers should note these systems differ in HE scheme, modality (face vs. fingerprint), and embedding dimensionality.

**Independent verification needed:** The paper claims Boddeti 2018 reports 1,240ms. Per available knowledge, Boddeti (BTAS 2018) reported ~1,240ms for LFW face verification using BFV — this is consistent with the literature. **UNVERIFIED from repository alone** (no copy of the Boddeti paper is accessible).

#### B.1.3 Is the 1-bit Attestation Idea Novel?

**Assessment:** The 1-bit boolean output approach for privacy-preserving authentication is an established engineering principle. Returning only a decision rather than a score is discussed in secure computation literature (e.g., Naor et al.'s work on oblivious RAMs, secure multiparty computation protocols for threshold functions). The combination with ECDSA attestation signing is a specific system-design choice. The novelty qualifier "has not been previously **evaluated**" (emphasis mine) appropriately weakens the claim. **The 1-bit attestation is not presented as a novel cryptographic primitive but as a system design choice that closes the Li-Micciancio vulnerability — this framing is accurate.**

**Critical note:** As shown in Section A.2, the simulation.py implementation actually includes the similarity float in the signed payload, undermining the security argument in the primary implementation.

#### B.1.4 Mezzadri Sign Correction — Novel to This Paper?

**Assessment:** The paper correctly attributes the QR sign correction to Mezzadri 2007 via `\cite{mezzadri2007random}`. The references.bib entry for `mezzadri2007random` is complete and correct (Notices of AMS, 54(5):592-604, 2007). This technique is well-known in random matrix theory. **The paper does not claim novelty for this method — it properly attributes it. No issue.**

#### B.1.5 Qualifier Strength Assessment

The novelty claim uses "to our knowledge" and "has not been previously evaluated." These are appropriately epistemic qualifiers for a systems paper. The claim is further qualified to the specific combination ("uniting... sub-30ms... 1-bit...") rather than any individual component. **This framing is appropriate for a systems contribution claim.** One concern: the LITERATURE_SEARCH.md uses a future search date ("October 2026") — if this is a fabricated date, the documented search validity is questionable.

---

## Section C: Citation Verification

### C.1 Citation Accuracy Table

| Citation key | Claimed | Actual | Match? | Issue |
|---|---|---|---|---|
| boddeti2018secure | "BFV on LFW face verification, EER 2.20%, latency 1,240ms" | Boddeti (BTAS 2018) used BFV on LFW, IJB-A, IJB-B, CASIA. EER ~2.20% on LFW, latency ~1,240ms reported. | **LIKELY CORRECT** | UNVERIFIABLE from repo. Consistent with known literature. The references.bib entry is correct: BTAS 2018 conference proceedings. |
| engelsma2022hers | "MegaFace+FaceScrub, EER 1.90%, latency 4,100ms" | HERS (Engelsma, Jain, Boddeti) published in **IEEE TBIOM 2022** (Transactions on Biometrics, Behavior, and Identity Science). The references.bib entry has journal = "IEEE Transactions on Biometrics, Behavior, and Identity Science" vol 4 no 3 pp 349-360 2022. This is **not** TPAMI. Research.tex line 673 says "MegaFace+FaceScrub" but LITERATURE_SEARCH.md says "IJB-C". | **VENUE: VERIFIED (TBIOM not TPAMI — CORRECT)**. **DATASET: INTERNALLY INCONSISTENT** | The venue (TBIOM) is correctly recorded. However, the paper text (line 673) says HERS evaluated on "MegaFace+FaceScrub" while LITERATURE_SEARCH.md Table 3 says "IJB-C". This is an **internal inconsistency**. HERS actually evaluates on IJB-B and IJB-C (based on known literature, not accessible here). If HERS uses IJB-C, neither "MegaFace+FaceScrub" nor "LFW" is correct. **UNVERIFIABLE without original paper — but the internal inconsistency is a verified problem.** |
| jin2018ranking | "Index-of-Max hashing on FVC2002, EER 3.90%" | Jin et al. (TIFS 2018) "Ranking-based locality sensitive hashing-enabled cancelable biometrics." Published in IEEE TIFS vol 13 no 2 pp 393-407 2018. | **LIKELY CORRECT** | EER 3.90% on FVC2002 is consistent with known literature. BibTeX entry is complete and correctly attributed. The dataset FVC2002 and EER range are plausible. UNVERIFIABLE from repo without original paper. |
| li2021ckks | "Li-Micciancio key-recovery attack from CKKS decryption noise" | Li and Micciancio (EUROCRYPT 2021) "On the security of homomorphic encryption on approximate numbers." Pages 648-677. This is the correct citation for the passive attack showing approximate CKKS decryption noise leaks the secret key. | **CORRECTLY ATTRIBUTED** | The description matches: returning decrypted approximate values enables adversarial key recovery. The paper's description of the attack is accurate. BibTeX entry is complete. |
| deng2019arcface | "ArcFace loss with additive angular margin" | Deng et al. CVPR 2019. Research.tex Eq. 1: L_Arc = -log(e^{s·cos(θ_{yi}+m)} / (e^{s·cos(θ_{yi}+m)} + Σ_{j≠yi} e^{s·cos(θ_j)})). | **VERIFIED CORRECT** | The ArcFace formula in the paper matches Deng et al. (2019) exactly. The angular margin m is added to θ_{yi} within the cosine. Parameters s=64, m=0.5 rad are consistent with the original paper's recommendations. |
| albrecht2018standard | "128-bit classical security for N=8192" | HomomorphicEncryption.org standard (albrecht2018standard). Per the 2018 standard, N=8192 with logQ ≤ 218 achieves 128-bit classical security under the standard LWE assumption. params.yaml has total logQ = 60+40+40+60 = 200 ≤ 218. | **VERIFIED** | The BibTeX entry is a techreport from HomomorphicEncryption.org 2018. The claim is technically valid given the parameters. The author list in the entry is long but correct. |
| iso24745 | "ISO/IEC 24745 unlinkability" | references.bib entry: `@misc{iso24745, author = {{ISO/IEC 24745:2022}}, title = "Information security, cybersecurity and privacy protection — Biometric information protection"}` | **VENUE/YEAR CAVEAT** | The cited standard is 2022, but the Gómez-Barrero metric cited alongside it is from a 2018 IEEE TIFS paper (gomez2018framework). The actual ISO/IEC 24745:2022 standard does not directly define D_sys — that is the Gómez-Barrero 2018 framework. The paper cites both, which is correct; the ISO standard defines the unlinkability *requirements*, while Gómez-Barrero defines the *metric*. This citation use is appropriate. |
| mezzadri2007random | "QR sign correction for Haar-distributed orthogonal matrices" | mezzadri2007random: Notices of AMS, 54(5):592-604, 2007. Research.tex correctly cites `\cite{mezzadri2007random}` for the sign correction. | **VERIFIED CORRECT** | Attribution is correct. The BibTeX entry is complete and accurate. The method is correctly described as producing Haar-distributed matrices. |
| rfc5869 | "HKDF-SHA256" | rfc5869: RFC 5869, Krawczyk and Eronen, IETF, 2010. | **VERIFIED CORRECT** | Correct RFC number (5869), correct authors, correct year (2010). The implementation in core/keys.py uses `cryptography.hazmat.primitives.kdf.hkdf.HKDF` which implements RFC 5869. |

### C.2 HERS Dataset Attribution — Verified Internal Inconsistency

The paper body (Research.tex line 673) states: "Engelsma et al. evaluate HERS on **MegaFace+FaceScrub** face images under BFV."

LITERATURE_SEARCH.md Table 3 (same document tree) lists HERS as evaluated on "**IJB-C**."

These two values appear in documents from the same repository and they contradict each other. Based on known literature, HERS (Engelsma et al. TBIOM 2022) evaluated on **IJB-B and IJB-C**, not MegaFace+FaceScrub (which is used in a different line of face recognition research). The audit-report.md §C-5 flags this as "UNVERIFIABLE" but notes it "may be wrong."

**Verdict: The HERS dataset attribution in the paper body ("MegaFace+FaceScrub") is likely incorrect. The correct dataset is IJB-C/IJB-B. This is an unresolved factual error that was identified in audit-report.md but not corrected.**

---

## Section D: Conclusion Validity Assessment

### D.1 "ROP achieves unlinkability indistinguishable from the noise floor"

**Claim:** AUC ≤ ROPLearnedAUC (0.5070), Dsys = 0.0353, "matching the noise floor of 0.0443."

**Data:** macros.tex: ROPWorstDsys=0.0353, NullNoiseFloorMean=0.0382, NullNoiseFloorP=0.0443 (95th percentile). The ROPWorstDsys=0.0353 is actually **below the null mean** of 0.0382 — it falls in approximately the 30th-40th percentile of the null distribution.

**Assessment:** The claim is justified. ROPWorstDsys=0.0353 is strictly less than the null p95=0.0443, meaning there is no statistically significant evidence of linkability above the finite-sample noise floor at the 5% significance level. The phrasing "indistinguishable from noise floor" is accurate: one cannot reject H_0 (no linkability) at 5% significance.

**Caveat:** Bootstrap CIs for Dsys are computed in `compute_bootstrap_cis()` but the abstract and conclusion do not report CI bounds on Dsys itself — only the point estimate. A reviewer could ask: what is the 95% CI on Dsys=0.0353? Without this, "indistinguishable" is supported by the permutation test but not by a full interval estimate.

**Verdict: VALID but incompletely reported (no CI bounds on Dsys in abstract/conclusion).**

### D.2 "Zero EER Degradation from HE (ΔEERs = 0.00%)"

**Data:** macros.tex: PairedPlaintextEER=8.60%, PairedCKKSEER=8.60%, PairedCKKSEERDiff=0.00%, PairedCKKSTrials=1,000, PairedCKKSCILow=0.00%, PairedCKKSCIHigh=0.00%.

**Assessment:** Both CI bounds are 0.00%, which means in all 1,000 bootstrap resamples the EER difference was 0.00%. This is possible because the CKKS maximum absolute error (1.43×10⁻⁶) is vastly smaller than any threshold crossing margin. With a similarity threshold of 0.8910, the approximation error never changes any verification decision.

**Scientific defensibility:** The claim is technically correct within the evaluation parameters. However, "zero degradation" requires the caveat that this is guaranteed only when max CKKS error << threshold margin. The paper includes this verification (§V-D, four-orders-of-magnitude argument). The claim is scientifically defensible.

**One concern:** The paired CKKS EER changed from 3.03% (RESULTS_PROVENANCE) to 8.60% (current macros) — a 185% change. This is because the evaluation protocol changed from EASY to ALL. The claim of "zero degradation" holds in both cases (the comparison is plaintext vs. CKKS under the same protocol), so there is no error in the claim itself.

**Verdict: VALID.**

### D.3 "Sub-second latency makes it practical for mobile deployment"

**Data:** macros.tex: SustainableLatencyMean=394.77ms, SustainableLatencyPNinetyFive=1114.84ms at N=10 concurrent clients. EETOMedian=27.19ms (unloaded). TotalMobileLatencyMS=311.49ms (projected cellular).

**Assessment:** This is problematic. The paper does not claim "sub-second latency" in those exact words in the current revision. The abstract states the p95 latency explicitly (1,114.84ms) without calling it "practical." The conclusion states the sustainable operating point numbers without labeling them "practical for mobile deployment." The audit-report.md §E-5 flagged this concern.

**Reading the actual text:** Research.tex §V-E reports "mean latency SustainableLatencyMean and 95th-percentile response time SustainableLatencyPNinetyFive" and the conclusion reports these numbers. The paper does NOT explicitly claim these are "practical" — it presents the numbers and leaves evaluation to readers. The projected mobile latency (311.49ms) is labeled as a projection.

**p95 = 1,114.84ms at N=10 is questionable for real-time biometric authentication.** For comparison, FIDO Alliance recommends authenticators complete in < 1 second. The paper's latency numbers at load are actually quite high for a biometric system. However, the paper does not hide these numbers — they are explicitly reported with macros in the abstract. The absence of explicit "practical" labeling for the loaded case is appropriate.

**Verdict: NUMBERS CORRECT. The paper avoids overclaiming "practical" for the loaded latency, but the unloaded 27ms is highlighted and projected mobile latency of 311ms is moderately defensible. Still, p95=1,114ms at N=10 in the conclusion paragraph deserves explicit acknowledgment as a practical limitation — it does appear in the Failure Modes section (§V-J item 4).**

### D.4 "EER 9.90% is the headline result"

**Assessment:** The paper clearly contextualizes this EER: (1) It is the ALL-alteration protocol covering Easy, Medium, and Hard synthetic distortions; (2) The Easy-only secondary benchmark achieves 2.84%; (3) ROP exactly matches plaintext EER by isometry — so 9.90% reflects the backbone discriminability, not any privacy overhead; (4) The paper notes SOCOFing uses synthetic alterations from single captures, so real-world EER would be higher. The headline 9.90% EER is high by state-of-the-art fingerprint recognition standards (e.g., FVC2002 top-performers achieve <1% EER), but the paper correctly attributes this to the difficulty of the ALL-alteration protocol and the backbone trained from scratch on SOCOFing. The comparison is not directly against FVC2002 NFIQ-2 verified fingerprints.

**Verdict: EER IS CORRECTLY CONTEXTUALIZED but publication-worthiness as a fingerprint system headline is marginal. The paper would benefit from a stronger backbone or a clearer argument that the metric reflects alteration robustness rather than fingerprint discrimination capability.**

### D.5 "The framework achieves 128-bit classical security"

**See A.1 above.** Parameters verified: N=8192, total logQ=200≤218 bits, std_dev=3.2. This satisfies the 2018 HE.org standard. **VERIFIED.**

---

## Section E: Internal Consistency Check

| Check | Expected | Found | Status |
|---|---|---|---|
| Abstract EER = Table caption EER = macros.tex | 9.90% | Abstract uses \AllAlterationEER macro (9.90%). Table III uses macros. macros.tex \HeadlineEER = 9.90%. | **CONSISTENT** |
| Abstract worker count | Should use \LocustWorkersCount macro (=4) | Abstract line 50: "On a $\LocustWorkersCount$-worker server" — uses macro correctly | **CONSISTENT** (audit-report.md reported "8" as B-1 bug, but this has been fixed in current Research.tex) |
| τ label in §IV-E | "test-set EER crossover", not "validation operating point" | Research.tex: "where operating threshold τ = \OperatingThresholdTau{} is the test-set EER crossover point (FAR=FRR at τ); the validation-transfer threshold τ_val = \ValTransferTau{} is disclosed in Section~\ref{sec:exp}." | **CONSISTENT — FIXED** |
| τ_val = 0.8943 mentioned separately | τ_val disclosed separately from τ = 0.8910 | Research.tex §V-B: "validation-transfer threshold τ_val=0.8943... evaluates to FAR 8.82% and FRR 11.06%, honestly disclosing the empirical transfer gap." | **CONSISTENT** |
| FiLM inversion error uses macro | Should use \FiLMInversionMaxErr, not "2.5e-7" | Research.tex §III-B: "($\|\hat{\mathbf{e}} - \mathbf{e}\|_2 < \FiLMInversionMaxErr$)" — uses macro | **CONSISTENT — FIXED** (audit-report.md B-4 reported the literal 2.5e-7 bug; current version uses macro) |
| Table III caption: ALL/EASY pair counts | Should reference 14,654/5,374 not "10,000" | Table caption in Research.tex: "(ALL Protocol: \AllAlterationTotalPairs{} pairs; EASY Protocol: \EasyOnlyTotalPairs{} pairs; Evaluation Seeds 42, 123, 456; single trained encoder, pair-sampling variance only)" | **CONSISTENT — FIXED** |
| FiLM macro consistency | \FiLMInversionMaxErr = 2.87e-08 in macros.tex | macros.tex line: `\newcommand{\FiLMInversionMaxErr}{2.87e-08}`. Research.tex uses this macro. | **CONSISTENT** |
| ROPWorstDsys matches metrics.json | macros.tex should match metrics.json unlinkability | macros.tex: ROPWorstDsys=0.0353. metrics.json: unlinkability data not in the portion read (truncated). macros.tex NullNoiseFloorP=0.0443, NullNoiseFloorMean=0.0382. | **LIKELY CONSISTENT** (macros are auto-generated from metrics.json per header) |
| HERS dataset: text vs LITERATURE_SEARCH | Should be consistent | Research.tex line 673: "MegaFace+FaceScrub". LITERATURE_SEARCH.md Table 3: "IJB-C (face)" | **INCONSISTENT — UNRESOLVED** |
| Locust concurrency list | N ∈ {10, 25, 50, 100, SaturationConcurrency} | Research.tex §V-E: "N ∈ {10, 25, 50, 100, \SaturationConcurrency}" where SaturationConcurrency=300. This is 5 distinct values: {10, 25, 50, 100, 300}. audit-report.md G-4 flagged potential duplicate but current text shows 5 distinct entries. | **CONSISTENT** |

---

## Section F: Summary of All UNVERIFIED, INCORRECT, or PROBLEMATIC Findings

### F.1 CRITICAL / HIGH SEVERITY

**[CRITICAL-1] similarity.py (simulation.py) Leaks Similarity Float in Signed Payload**
- **Location:** `phase6_tee/tee/simulation.py`, function `create_signed_payload()`, and `verify_and_sign_core()` returning `VerificationResult.signed_payload`
- **Problem:** The signed payload contains the raw similarity float (`struct.pack('>d', similarity_score)`). If the server calls `verify_signature(public_key, result.signed_payload, result.signature)`, it receives the similarity score — enabling the Li-Micciancio oracle attack the paper claims to prevent.
- **Discrepancy:** `run_attestation_benchmark.py` correctly implements `H(d ‖ n_s ‖ v)` without the similarity float. The paper's formal specification (§IV-E Eq. 6) matches the benchmark, not the simulation.
- **Required fix:** Either (a) remove `similarity_score` from `create_signed_payload()`, or (b) never return `signed_payload` to the server (only return the ECDSA signature over the hash). The paper's security argument is sound only if the server never receives the full signed payload.

**[CRITICAL-2] HERS Dataset Attribution Inconsistency**
- **Location:** Research.tex line 673 ("MegaFace+FaceScrub") vs. LITERATURE_SEARCH.md Table 3 ("IJB-C")
- **Problem:** These are two documents in the same repository that contradict each other. Based on knowledge of the HERS paper, IJB-C/IJB-B is likely correct, not MegaFace+FaceScrub.
- **Required fix:** Verify against the actual Engelsma et al. 2022 paper and correct one or both documents.

**[HIGH-1] Equation 3 (HKDF Derivation) — Multiple Mismatches with core/keys.py**
- **Flagged in audit-report.md B-2 as a previous version bug.** The current Research.tex contains the corrected equation:
  - L=32 ✓ (audit-report B-2 confirms this was corrected)
  - uint64 ✓
  - info_{u,v} = `{user_id}|v{version}` ✓
  - Two-stage pipeline (HKDF → AES-CTR DRBG) ✓
- **Status:** Per current Research.tex text (§IV-C Eq. 3), this appears to have been corrected. However, the audit-report.md flagged it as a bug. **VERIFY** the current Research.tex Eq. 3 matches the corrected description — based on the read at line 340-345, the current paper shows the corrected L=32 and uint64 derivation. This specific bug appears FIXED in the current version.

### F.2 MODERATE SEVERITY

**[MODERATE-1] No Bootstrap CI Bounds Reported for Dsys in Abstract/Conclusion**
- The claim "indistinguishable from noise floor" is supported by the permutation test (p95=0.0443 > Dsys=0.0353) but the abstract and conclusion do not report the bootstrap CI on Dsys=0.0353 itself. Without a CI, readers cannot assess the precision of the Dsys estimate.
- **Recommendation:** Add "[Dsys CI_lower, CI_upper]" to the unlinkability summary.

**[MODERATE-2] Learned Inversion EER = 37.40% — Not "Chance Level"**
- macros.tex: LearnedInversionEER=37.40%
- The current paper honestly states "it remains below the 50% chance baseline, indicating partial feature leakage under black-box neural inversion" — this is correct.
- **However:** "Substantial degradation" is subjectively downplaying: 37.40% EER means a learned MLP can achieve verification accuracy meaningfully above chance using only the protected template. For a cancelable scheme claiming "unlinkability," this is a significant weakness that warrants stronger caveat language.

**[MODERATE-3] RESULTS_PROVENANCE.md Is Severely Outdated**
- Documented in audit-report.md §C-1. Key values deviate by 50-185% from current macros.
- Most critically: `PairedCKKSEER` 3.03% vs current 8.60%; `SaturationThroughput` 120.35 vs 11.44 req/s; `AlterationOverallFRR` 22.25% vs 10.17%.
- The provenance document ships with the repository and will mislead reviewers who read it.
- **Required action:** Either regenerate or clearly mark as a historical artifact.

**[MODERATE-4] Single Trained Encoder — Reported Variance Is Pair-Sampling Only**
- The headline EER 9.90% ± 0.24% captures only pair-sampling variance (three seeds), not training variance.
- The paper honestly discloses this ("pair-sampling variance, not training variance") but only in the table caption and limitations section. The abstract states the seeds but calls it just "variance across three evaluation seeds" without clarifying that training variance is uncharacterized.
- **Recommendation:** A single sentence in the abstract clarifying that only one encoder was trained and seeds reflect pair-sampling variance.

**[MODERATE-5] p95 Latency at N=10 Exceeds 1 Second**
- SustainableLatencyPNinetyFive=1,114.84ms at N=10 (the "sustainable" operating point)
- The paper reports this number accurately but the framing as a "sustainable operating point" creates a favorable impression when 1-in-20 authentications will take > 1.1 seconds even at minimal load. This is borderline for biometric authentication in practice.
- The paper does report the number in the abstract with the macro, which is transparent. This is not an error but a contextualization concern.

### F.3 LOW SEVERITY / INFORMATIONAL

**[LOW-1] Attestation Implementation Not in make reproduce Pipeline**
- The 1-bit attestation is listed as "Contribution 3." The implementation lives in phase5_backend/ and phase6_tee/, but the standalone benchmark (make reproduce) does not exercise it end-to-end.
- The paper acknowledges this scope separation (§IV-G "Attestation Implementation Scope").
- **Assessment:** Honestly disclosed, but a reviewer may still question why a "core contribution" is not in the reproducible benchmark.

**[LOW-2] Within-Service Linkability AUC Changed from 0.9956 to 0.9592**
- RESULTS_PROVENANCE states SameServiceAUC=0.9956; current macros.tex: SameServiceAUC=0.9592.
- The paper correctly uses the macro. The change is unexplained and represents a meaningful decrease in demonstrated within-service linkability. The paper uses this to show isometry within the same key (AUC=0.9592 still demonstrates high linkability).
- No paper error, but the change is suspicious and warrants an explanation in CHANGELOG.

**[LOW-3] TVLA Quiet vs Full Run Discrepancy**
- The TVLA results show two runs with different results: "quiet" run (2,000 trials): t=3.23, p=0.0013; full run (10,000 trials): t=0.75, p=0.4547.
- The paper reports the full 10,000-trial run result (t=0.75) as the primary result. The quiet run with p=0.0013 could indicate genuine timing differences under different system load conditions.
- The paper correctly notes "An unexplained variance difference remains" — this is honest. But two runs with contradictory p-values deserve more investigation.

**[LOW-4] AES-CTR Nonce Hardcoded to Zeros**
- core/keys.py: `nonce = b'\x00' * 16` for the AES-256-CTR DRBG.
- A fixed zero nonce is acceptable when the AES key is unique per (user_id, version) pair, since key+nonce together must be unique. Since the HKDF output is unique, the zero nonce does not compromise security.
- The paper does not describe this detail — acceptable for space, but should be noted for complete reproducibility.

**[LOW-5] Literature Search Timestamp Says "October 2026"**
- LITERATURE_SEARCH.md states "Date Conducted: October 2026."
- This is a future date relative to any realistic submission timeline. This appears to be a placeholder or a testing artifact. If reviewers read this document, it creates questions about the validity of the documented search.

---

## Section G: Overall Assessment Summary

### Confirmed Correct:
- 128-bit CKKS security parameters (N=8192, logQ=200 ≤ 218 bits) ✓
- ArcFace formula (Eq. 1) exactly matches Deng et al. 2019 ✓  
- HKDF key revocation independence ✓
- Mezzadri 2007 attribution (cited and implemented correctly) ✓
- RFC 5869 HKDF citation ✓
- TEE as simulation is honestly represented ✓
- Nonce replay protection in attestation benchmark ✓
- FiLM AUC=0.9413 (absolute-value attack) is a real finding, not cherry-picking ✓
- Null permutation calibration for unlinkability is methodologically sound ✓
- EER 9.90% correctly contextualized as ALL-alteration protocol ✓
- Li-Micciancio attack description is accurate ✓
- Zero CKKS EER degradation is mathematically defensible ✓
- Table III caption now uses macros (previously hardcoded "10,000") ✓
- τ label correctly says "test-set EER crossover" ✓
- Abstract worker count uses macro (\LocustWorkersCount=4) ✓

### Confirmed Problems:
1. **[CRITICAL]** `simulation.py::create_signed_payload()` leaks similarity float in signed payload — contradicts the core score-concealment security claim
2. **[HIGH]** HERS dataset attributed to "MegaFace+FaceScrub" in the paper body but "IJB-C" in LITERATURE_SEARCH.md — likely both wrong (actual: IJB-B/IJB-C)
3. **[MODERATE]** No bootstrap CI on Dsys in abstract/conclusion
4. **[MODERATE]** Learned inversion EER 37.40% underplayed as "substantial degradation"
5. **[MODERATE]** RESULTS_PROVENANCE.md is severely outdated and ships with the repository
6. **[MODERATE]** Literature search timestamp is "October 2026" (future date — credibility concern)
7. **[LOW]** Attestation implementation not exercised by reproducible benchmark pipeline
8. **[LOW]** TVLA shows contradictory p-values between 2,000-trial quiet run (p=0.0013) and 10,000-trial full run (p=0.4547)
9. **[LOW]** Within-service AUC changed from 0.9956 → 0.9592 without explanation in changelog

### UNVERIFIED Claims (require external access):
- Exact Boddeti 2018 EER (2.20%) and latency (1,240ms) — consistent with literature, not verifiable from repo
- Engelsma 2022 HERS actual dataset — likely IJB-C, not MegaFace+FaceScrub; requires original paper
- Jin 2018 IoM EER (3.90%) on FVC2002 — consistent with literature, not verifiable from repo
- Whether Li-Micciancio attack applies specifically to passive (not active) adversaries as claimed — the characterization in the paper (passive adversary reconstructing key from rounding errors) is consistent with EUROCRYPT 2021 abstract
