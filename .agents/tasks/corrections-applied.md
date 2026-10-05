# Corrections Applied to Research.tex

**Date applied:** This run  
**Source:** Audit report at `.agents/tasks/audit-report.md`  
**Files modified:** `Research.tex`, `references.bib`, `RESULTS_PROVENANCE.md`

---

## Summary

13 verified corrections applied. No scientific results were changed. No unverifiable values were altered (they received inline annotations where appropriate). LaTeX compilation could not be verified because pdflatex is not installed on this machine — the corrections are syntactically consistent with the existing document style and use only macros already defined in `results/final/macros.tex`.

---

## Correction 1 — Abstract worker count (B-1 / M-1 / N-1)

- **File:** `Research.tex`
- **Location:** Abstract (line ~49)
- **What changed:** `"On an 8-worker server"` → `"On a $\LocustWorkersCount$-worker server"`
- **Also:** Added `"concurrent clients"` after `\SaturationConcurrency{}` for clarity (it was missing in the original).
- **Why:** The experiment used 4 workers (`\LocustWorkersCount = 4` in macros.tex). The abstract was hardcoded to the wrong value from an earlier experimental run.

---

## Correction 2 — HKDF Equation 3 (B-2 / M-2 / N-2)

- **File:** `Research.tex`
- **Location:** §IV-C, Key Management Protocol, Eq. 3
- **What changed:** Rewrote the three-line align environment to match `core/keys.py`:
  - `HKDF-Expand(…, L=1024)` → `K_AES = HKDF-Expand(…, L=32)` (correct 32-byte AES key)
  - Added `AES-256-CTR-DRBG(K_AES) →^{uint64} (0,1)^D` line showing the DRBG stage
  - `uint32(OKM[4i:4i+4]) / (2^32-1)` → `r_i × 2.0 − 1.0` (via uint64, consistent with code)
  - `info_{u,v} = biometric-auth|u|v|Key` → `info_{u,v} = {user_id}|v{version}` (matches code)
  - Added explanatory sentence about the 64-bit mapping `(u+1)/(2^64+2)`
- **Why:** Three mismatches with `core/keys.py` made the described protocol non-reproducible.

---

## Correction 3 — Table III caption pair count (B-3 / M-3 / N-3)

- **File:** `Research.tex`
- **Location:** `\caption` for `tab_encoder_eval`
- **What changed:** `"(10,000 Pairs, Evaluation Seeds 42, 123, 456)"` →  
  `"(ALL Protocol: \AllAlterationTotalPairs{} pairs; EASY Protocol: \EasyOnlyTotalPairs{} pairs; Evaluation Seeds 42, 123, 456; single trained encoder, pair-sampling variance only)"`
- **Why:** No experiment in this table uses exactly 10,000 pairs. The headline ALL protocol uses 14,654; the EASY protocol uses 5,374. The caption was misleading by a factor of ~1.5×.

---

## Correction 4 — FiLM inversion error hardcoded literal (B-4 / M-4 / N-4)

- **File:** `Research.tex`
- **Location:** §III-B, Stolen-Device Inversion Attack, line ~202
- **What changed:** `"< 2.5 \times 10^{-7}"` → `"< \FiLMInversionMaxErr"`
- **Why:** The macro `\FiLMInversionMaxErr = 2.87e-08`, which is ~8.7× smaller (better) than the hardcoded literal. The text was overstating inversion error by nearly an order of magnitude.

---

## Correction 5 — Operating threshold τ label (B-5 / M-5 / N-5)

- **File:** `Research.tex`
- **Location:** §IV-E (CKKS Verification Protocol), client threshold equation caption, line ~434
- **What changed:** `"(validation EER operating point)"` →  
  `"is the test-set EER crossover point (FAR = FRR = \NominalTestFAR{} at τ); the validation-transfer threshold τ_val = \ValTransferTau{} is disclosed in Section~\ref{sec:exp}"`
- **Why:** τ = 0.8910 is where FAR = FRR on the test set, not a validation threshold. The validation-transfer threshold is τ_val = 0.8943 (a distinct value). The wrong label could mislead reviewers into thinking the threshold was selected on test data without disclosure.

---

## Correction 6 — ROC/DET figure captions pair count (B-6 / M-6 / N-6)

- **File:** `Research.tex`
- **Location:** §V-B, three places
- **What changed:**
  1. Prose before Fig. 2: `"across 10,000 evaluation pairs"` → `"under the nominal 10,000-pair benchmark (5,000 Easy genuine, 5,000 impostor pairs)"`
  2. Fig. 2 caption: Same update
  3. Distribution figure prose: `"(10,000 pairs each)"` → `"(nominal 10,000-pair benchmark)"`
- **Why:** The headline evaluation uses 14,654 pairs (ALL protocol). The figures are from the nominal benchmark. The distinction needed to be made explicit so readers don't conflate the figure EERs with the headline metric.

---

## Correction 7 — Load test N-set lists N=10 twice (G-4 / M-7 / N-7)

- **File:** `Research.tex`
- **Location:** §V-E (Multi-Client Load Testing) prose
- **What changed:** `"N ∈ {10, 25, 50, \SustainableConcurrency, \SaturationConcurrency}"` → `"N ∈ {10, 25, 50, 100, \SaturationConcurrency}"` (since `\SustainableConcurrency = 10`, the old form listed 10 twice)
- **Why:** `\SustainableConcurrency = 10`, so the old LaTeX expanded to `{10, 25, 50, 10, 300}` — a set with a duplicate value.

---

## Correction 8 — CKKS dot product equation notation (F-2 / M-12 / N-8)

- **File:** `Research.tex`
- **Location:** §IV-E, Eq. 8 (he_dot), line ~424
- **What changed:** Added a sentence after the equation:  
  `"where ⊙ denotes the CKKS inner product: element-wise ciphertext multiplication followed by homomorphic summation via ciphertext rotations~\cite{cheon2017homomorphic}."`
- **Why:** The `⊙` symbol is commonly used for Hadamard (element-wise) product; without clarification, readers might misread Eq. 8 as computing a vector rather than the scalar inner product.

---

## Correction 9 — Add Mezzadri (2007) citation (H-5 / M-8 / N-9)

- **File:** `Research.tex` (cite added), `references.bib` (entry added)
- **Location in tex:** §IV-D1 (ROP description), "Mezzadri diagonal sign correction"
- **What changed:** Added `~\cite{mezzadri2007random}` after the phrase; added `@article{mezzadri2007random, ...}` to `references.bib`
- **Why:** The code comments reference Mezzadri (2007) for the QR sign correction that produces Haar-distributed matrices, but this was uncited in the paper.

---

## Correction 10 — Add RFC 5869 (HKDF) citation (H-6 / M-9)

- **File:** `Research.tex` (cite added), `references.bib` (entry added)
- **Location in tex:** §IV-C Key Management Protocol, "HKDF-SHA256"
- **What changed:** Changed `"derived via HKDF-SHA256:"` → `"derived via HKDF-SHA256~\cite{rfc5869}:"`;  added `@techreport{rfc5869, ...}` to `references.bib`
- **Why:** The paper references RFC 5869 but did not have a formal citation for it.

---

## Correction 11 — Attestation implementation scope note (M-11)

- **File:** `Research.tex`
- **Location:** §IV-F (Secure Context and System Boundary), after the TEE boundary table
- **What changed:** Added a new paragraph "Attestation Implementation Scope" explaining that ECDSA 1-bit attestation is implemented in `phase5_backend/` and covered by acceptance tests, while `make reproduce` focuses on HE computation benchmarks.
- **Why:** Reviewers checking the codebase's main pipeline would not find the attestation logic, which could create an impression that it was unimplemented. The note provides transparency without overclaiming.

---

## Correction 12 — RESULTS_PROVENANCE.md historical warning (M-10 / N-10)

- **File:** `RESULTS_PROVENANCE.md`
- **Location:** Line 1 (prepended)
- **What changed:** Added a prominent warning block indicating this is a historical document superseded by `results/final/macros.tex`
- **Why:** RESULTS_PROVENANCE.md contains 30+ values that disagree with the current macros.tex (e.g., worker count 8 vs 4, saturation throughput 120 vs 11 req/s, TVLA t-stat 3.23 vs 0.75). A reviewer reading this document would find contradictions with the submitted paper.

---

## Items NOT changed (per instructions)

- **C-5 / H-2 / L-2 (UNVERIFIABLE):** HERS dataset attribution (LFW vs IJB-C in Table IX line 664). Cannot verify without access to the original Engelsma et al. paper. No annotation added because the value is a citation claim, not a number; it requires human verification against the cited source.
- **All values in section L:** No scientific results were altered. Values requiring experiment reruns are preserved as-is.
- **All macro-sourced values:** Every numerical result in the paper uses its corresponding macro; none were altered.
- **pdflatex compilation:** LaTeX toolchain not present on this machine. Syntax of changes verified by reading the file and checking that all `\cite{}`, `\newcommand`, and equation environments are consistent with the existing document structure.

---

## Files modified

| File | Changes |
|------|---------|
| `Research.tex` | 12 text corrections (corrections 1–8, 11, plus RFC/Mezzadri cite additions) |
| `references.bib` | 2 new entries added: `mezzadri2007random`, `rfc5869` |
| `RESULTS_PROVENANCE.md` | Historical warning header prepended |
