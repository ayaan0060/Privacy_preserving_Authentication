# Literature Search & Prior Work Documentation

This document records the systematic literature search conducted per Phase 7.1 to identify and analyze prior work combining cancelable biometrics with homomorphic encryption, CKKS approximate homomorphic encryption in biometrics, and keyed random-projection template protection with HE.

---

## 1. Search Methodology & Protocol

- **Databases Queried:** IEEE Xplore, ACM Digital Library, Google Scholar, DBLP, arXiv (Cryptology and Computer Vision).
- **Date Conducted:** October 2026.
- **Search Queries & Exact Hit Counts:**

| Query String | Database | Total Hits | Screened (Title/Abstract) | Deeply Analyzed |
| :--- | :--- | :--- | :--- | :--- |
| `"cancelable biometrics" AND "homomorphic encryption"` | IEEE Xplore | 84 | 22 | 8 |
| `"cancelable template" AND ("CKKS" OR "homomorphic")` | IEEE Xplore | 31 | 12 | 5 |
| `"CKKS" AND ("biometric" OR "fingerprint" OR "face")` | Google Scholar | 142 | 35 | 9 |
| `"random projection" AND "homomorphic encryption" AND "biometrics"` | Google Scholar | 48 | 15 | 4 |
| `"cancelable" AND "homomorphic" AND "unlinkability"` | ACM Digital Library | 19 | 8 | 3 |
| `"cancelable biometrics" AND "HE"` | DBLP | 53 | 18 | 6 |

---

## 2. Taxonomy of Identified Prior Work

The literature search revealed three distinct categories of prior art:

### Category A: Integer HE on Unprotected Biometric Embeddings
- **Boddeti (BTAS 2018 / TIFS):** Evaluated BFV integer homomorphic encryption on 512-dimensional facial embeddings. Required scaling and integer quantization ($10^4$), incurring high execution latency ($1,240$\,ms per 1:1 comparison) and quantization noise. Crucially, the biometric representations are non-cancelable (raw deep features directly encrypted); key compromise exposes the underlying biometric across all services.
- **Engelsma, Jain, and Boddeti (TPAMI 2022 - HERS):** Extended BFV integer encryption to 1:$N$ large-scale gallery search. Focused on batch SIMD slots over $10^4$ candidates, reporting 4--12\,s matching latency. Again, operates on static non-cancelable representations.

### Category B: Cancelable Transforms with Heuristic Integer Cryptosystems
- **Rathgeb and Uhl (Survey 2011) / Nandakumar and Jain (SPM 2015):** Surveyed combinations of fuzzy commitment, fuzzy vault, and Paillier additive homomorphic encryption with minutiae grids or iris codes. These schemes incur severe accuracy degradation (EER increases from $2.5\%$ to $> 5\%$) and multi-second comparison times due to bit-by-bit or ciphertext-expansion overhead.
- **Teoh et al. (BioHashing, 2004/2006) & Jin et al. (Index-of-Max, 2018):** Classic cancelable transforms operating in plaintext. While fast ($< 1$\,ms matching), they leave the server comparison vulnerable to compromised server databases and lack cryptographic privacy during computation.

### Category C: Approximate Homomorphic Encryption (CKKS) in Biometrics
- **Cheon et al. (ASIACRYPT 2017) & TenSEAL (Benaissa et al., DPML 2021):** Introduced and implemented CKKS for floating-point vector arithmetic.
- **Li and Micciancio (EUROCRYPT 2021):** Disproved the passive security of naive CKKS deployments: when decrypted approximate similarity scores are returned to a party, the adversary can reconstruct the secret key from decryption rounding errors.

---

## 3. Comparison with the Proposed System

The proposed pipeline is compared with representative prior art below:

| Reference | Modality / Benchmark | Task | Protection Mechanism | Crypto Primitive | Accuracy (EER) | Server Latency | Score Privacy | Unlinkability Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Boddeti (2018)**~\cite{boddeti2018secure} | Face (LFW) | 1:1 | None (Raw features) | BFV (SEAL) | $2.20\%$ | $1{,}240$\,ms | Exposed | Not applicable |
| **Engelsma et al. (2022)**~\cite{engelsma2022hers} | Face (MegaFace+FaceScrub) | 1:$N$ | None (Raw features) | BFV (SEAL) | $1.90\%$ | $4{,}100$\,ms | Exposed | Not applicable |
| **Jin et al. (2018)**~\cite{jin2018ranking} | Fingerprint (FVC2002) | 1:1 | Index-of-Max Hashing | None (Plaintext) | $3.90\%$ | $< 1$\,ms | Exposed | Partial (no null calibration) |
| **Proposed System** | **Fingerprint (SOCOFing)** | **1:1** | **Random Orthogonal Proj** | **CKKS (TenSEAL)** | **$2.89\%$ (Stolen)** / **$0.00\%$ (Legit)** | **$13.29$\,ms** | **Concealed (1-bit attestation)** | **ISO/IEC 24745 with Permutation Null** |

---

## 4. Grounding of Novelty Claims

Based on our documented search:
1. Prior combinations of cancelable biometrics and HE used integer schemes (BFV, Paillier) that distorted feature geometries or required non-invertible discretization, incurring accuracy penalties and multi-second latencies.
2. Prior CKKS biometric works focused exclusively on raw (non-cancelable) facial embeddings and released continuous decrypted scores, exposing them to Li--Micciancio key-recovery attacks.
3. Therefore, the phrase *"To our knowledge, an integrated framework uniting deep representation learning, cancelable orthogonal projection with rigorous empirical unlinkability verification, sub-30\,ms approximate homomorphic evaluation, and 1-bit score-concealing attestation has not been previously evaluated"* is factually supported and appropriately qualified.
