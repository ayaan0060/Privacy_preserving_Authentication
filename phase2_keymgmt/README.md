# Phase 2: Cancelable Keystore & Key Management

**STATUS: REAL (dev CSPRNG) / interface-ready for hardware RNG**

## 1. Project Structure

```text
phase2_keymgmt/
├── config.yaml                 # Keystore & HKDF configuration
├── requirements.txt            # Dependencies (cryptography, numpy, pytest)
├── keystore/
│   ├── __init__.py
│   ├── interface.py            # SecureKeyStore ABC (swap for TEE/HSM)
│   ├── software.py             # Software implementation (mlock, zeroize, PBKDF2 + AES-GCM)
│   ├── derivation.py           # HKDF-SHA256, domain separation, rescaling
│   ├── rotation.py             # Key versioning, revocation, invalidation
│   └── models.py               # Dataclasses: KeyRecord, KeyVersion, DerivedKeyMaterial
├── tests/
│   ├── test_interface.py       # ABC compliance tests
│   ├── test_software_store.py  # mlock, zeroize, persistence
│   ├── test_derivation.py      # HKDF vectors, domain separation, rescale
│   ├── test_rotation.py        # Revocation proof: old key -> no match
│   └── test_integration_p1.py  # Phase 1 encoder + Phase 2 key -> FiLM input
└── scripts/
    └── keycli.py               # CLI: gen, rotate, list, show, delete, test-revocation
```

---

## 2. How to Run Phase 2

```bash
cd phase2_keymgmt

# 1. Install deps
pip install -r requirements.txt

# 2. Run unit tests (includes integration with mocked Phase 1)
pytest tests/ -v

# 3. CLI smoke test
python -m scripts.keycli --storage ./test_keystore gen alice
python -m scripts.keycli --storage ./test_keystore list alice
python -m scripts.keycli --storage ./test_keystore rotate alice --reason "test"
python -m scripts.keycli --storage ./test_keystore list alice
python -m scripts.keycli --storage ./test_keystore test-revocation alice

# 4. Verify revocation test passes (core guarantee)
# Output should show: "Result: PASS (unlinkable)"
```

---

## 3. Acceptance Criteria Checklist

| Criterion | Target | Verification |
|---|---|---|
| CSPRNG seed generation | 32 bytes from `/dev/urandom` | `test_software_store.py::test_persistence_across_instances` |
| HKDF-SHA256 derivation | RFC 5869 compliant | `test_derivation.py::TestHKDF` |
| Key vector: 256-d float32 in $[-1,1]$ | Shape, dtype, range | `test_derivation.py::TestDeriveKeyVector::test_output_shape_and_range` |
| Domain separation | Different info $\rightarrow$ different output | `test_derivation.py::test_domain_separation` |
| Deterministic derivation | Same seed $\rightarrow$ same key_vector | `test_derivation.py::test_deterministic` |
| Rotation invalidates old key | `get_key_material(v_old)` raises | `test_rotation.py::test_revocation_effectiveness` |
| Revocation effectiveness | Cosine similarity < 0.15 | `test_rotation.py::test_revocation_effectiveness` |
| Grace period metadata | Timestamp recorded on rotation | `test_software_store.py::test_grace_period_metadata` |
| Encrypted storage | Wrong master key $\rightarrow$ decrypt fail | `test_software_store.py::test_wrong_master_key_fails` |
| Thread safety | Concurrent reads OK | `test_software_store.py::test_concurrent_access` |
| Interface compliance | All ABC methods implemented | `test_interface.py` (run against `SoftwareSecureKeyStore`) |
| Phase 1 integration | Embedding dim = key dim = 256 | `test_integration_p1.py` |

---

## 4. Deliverables Summary

| File / Artifact | Purpose |
|---|---|
| `keystore/interface.py` | `SecureKeyStore` ABC — swap point for TEE/HSM |
| `keystore/software.py` | Dev implementation (`mlock`, PBKDF2, AES-GCM) — SIMULATED |
| `keystore/derivation.py` | Pure HKDF + rescaling — REAL, tested with RFC vectors |
| `keystore/rotation.py` | Rotation policy + revocation proof |
| `keystore/models.py` | Immutable dataclasses (`KeyRecord`, `KeyVersion`, `DerivedKeyMaterial`) |
| `scripts/keycli.py` | Dev CLI for key lifecycle management |
| `tests/` | 25+ unit & contract tests passing |

---

## 5. Real vs Simulated Boundary

| Component | Status | Production Swap |
|---|---|---|
| CSPRNG | `/dev/urandom` (dev) | Hardware RNG in TEE / StrongBox / Secure Enclave |
| Master key | Random bytes in Python process | Derived from user auth + hardware-bound key (never in RAM) |
| Encrypted storage | AES-GCM + PBKDF2 on disk | TEE-sealed storage / HSM wrapped keys |
| `mlock`/`zeroize` | Best-effort (resource limits) | Hardware-enforced (TEE memory isolation) |
| Key derivation | **PURE FUNCTION — identical in prod** | **NO CHANGE** — same HKDF-SHA256 |
| Revocation logic | **PURE LOGIC — identical in prod** | **NO CHANGE** — versioning + grace period |

**PHASE 2 COMPLETE.**  
The keystore generates, derives, rotates, and revokes keys. The `SecureKeyStore` interface is ready for Phase 3 (FiLM Fusion Network) which consumes the 256-d key vector.
