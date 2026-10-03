# Phase 6 — TEE / Secure-World Simulation & Key Release

## Overview
Phase 6 implements the Hardware Security Boundary & Key Release Protocol. It encapsulates the similarity threshold decision inside an isolated environment (TEE or software simulation) and signs the result with an ECDSA P-256 device key.

## Project Structure
```
phase6_tee/
├── config.yaml
├── requirements.txt
├── README.md
├── tee/
│   ├── __init__.py
│   ├── interface.py            # SecureContext contract (ABC)
│   ├── simulation.py           # Software SecureContext simulation
│   ├── key_release.py          # Key release protocol & server verification
│   ├── device_keys.py          # Device ECDSA P-256 key management
│   ├── threat_model.py         # Threat model matrix & limitations
│   └── production/
│       ├── __init__.py
│       ├── android_keystore.py # StrongBox integration guide
│       ├── ios_secure_enclave.py # Secure Enclave integration guide
│       └── optee_ta.py         # OP-TEE Trusted App guide
├── scripts/
│   ├── run_simulation.py       # Simulation demo script
│   └── generate_device_keys.py # Device key provisioning
├── docs/
│   ├── THREAT_MODEL.md
│   └── HARDWARE_INTEGRATION.md
└── tests/
    ├── test_simulation.py
    ├── test_key_release.py
    ├── test_replay_protection.py
    ├── test_rotation_invalidation.py
    └── test_threat_model.py
```

## How to Run Phase 6

### 1. Install Dependencies
```bash
cd phase6_tee
pip install -r requirements.txt
```

### 2. Run Unit & Threat Model Tests
```bash
pytest tests/ -v
```

### 3. Run Key Release Simulation Demo
```bash
python scripts/run_simulation.py
```

### 4. Generate Device Signing Keys
```bash
python scripts/generate_device_keys.py --key-dir ./exports/device_keys
```

### 5. Inspect Threat Model Documentation
```bash
python -m tee.threat_model
# Or view docs/THREAT_MODEL.md
```

## Acceptance Criteria Checklist

| Criterion | Target | Verification |
| :--- | :--- | :--- |
| SecureContext Interface | ABC with verify_and_sign, get_device_identity | `tee/interface.py` |
| Software Simulation | mlock, zeroize, nonce tracking, version checks | `tee/simulation.py` + `test_simulation.py` |
| Core Logic Pure | verify_and_sign_core no side effects | `test_simulation.py::TestCoreLogic` |
| Key Release Protocol | Request/response with signature verification | `tee/key_release.py` + `test_key_release.py` |
| Nonce Replay Protection | Same nonce → NonceReplayError | `test_replay_protection.py::test_same_nonce_twice_fails` |
| Key Rotation Invalidation | Revoked version → KeyRevokedError | `test_rotation_invalidation.py` |
| Device Key Management | Generation, persistence, rotation | `tee/device_keys.py` + `test_simulation.py` |
| Threat Model Documented | Explicit simulation vs real TEE gaps | `tee/threat_model.py` + `docs/THREAT_MODEL.md` |
| Production Skeletons | Android/iOS/OP-TEE integration docs | `tee/production/*.py` + `docs/HARDWARE_INTEGRATION.md` |
| Simulation Warnings | Clear warnings in code, logs, docs | `test_threat_model.py::TestSimulationWarnings` |

## Real vs Simulated Final Boundary

| Component | Simulation | Real TEE (Production) |
| :--- | :--- | :--- |
| Memory Isolation | ❌ mlock best effort | ✅ Hardware (TrustZone/SEP) |
| RNG | ❌ /dev/urandom | ✅ Hardware TRNG |
| Attestation | ❌ Simulated | ✅ Google/Apple/OP-TEE certs |
| Debug Protection | ❌ None | ✅ Debug disable, secure boot |
| Side-Channels | ❌ None | ✅ HW countermeasures |
| Tamper Resistance | ❌ None | ✅ Secure element |
| Key Storage | ❌ Encrypted files | ✅ Sealed in TEE |
| Nonce Tracking | ❌ In-memory set | ✅ Monotonic counters |
| HE Secret Key | ⚠️ Passed from normal world | ✅ Provisioned in TEE |
| Logic (Threshold/Sign) | ✅ IDENTICAL | ✅ IDENTICAL |

## Migration from Simulation to Hardware TEE

The `SecureContext` interface is identical across implementations:

```python
# Current (simulation)
from tee.simulation import SoftwareSecureContext
ctx = SoftwareSecureContext(...)

# Production (Android StrongBox)
from tee.production.android_keystore import AndroidSecureContext
ctx = AndroidSecureContext(...)

# Production (iOS Secure Enclave)
from tee.production.ios_secure_enclave import IOSSecureContext
ctx = IOSSecureContext(...)

# Production (OP-TEE TA)
from tee.production.optee_ta import OPTEESecureContext
ctx = OPTEESecureContext(...)
```

## Key Provisioning Ceremony
- **Manufacturing**: Keys generated in HSM, injected into device TEE.
- **Enrollment**: Device generates key in TEE, sends attestation to server.
- **Server Verification**: Verifies attestation, stores device public key.
- **Rotation**: Scheduled re-enrollment with new attestation.
