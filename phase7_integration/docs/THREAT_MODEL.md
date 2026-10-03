# Consolidated Threat Model

## System Overview
Cancelable Biometric Authentication System with Homomorphic Encryption and TEE Key Release.

## Security Boundary Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          NORMAL WORLD (UNTRUSTED)                           │
│  ┌─────────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ Fingerprint │→ │ Encoder │→ │  FiLM    │→ │ HE Enc   │                  │
│  │   Sensor    │  │ (CNN)   │  │ Fusion   │  │ (CKKS)   │                  │
│  └─────────────┘  └─────────┘  └──────────┘  └──────────┘                  │
│        │                                                  │                  │
│        │ Plaintext biometric                            │ Ciphertext       │
│        ▼                                                  ▼                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SECURE CONTEXT (TEE / SIMULATION)                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│  │  │ HE Decrypt   │→ │ Threshold    │→ │ Device Sign              │  │   │
│  │  │ (score)      │  │ Check        │  │ (nonce||score||version)  │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Consolidated Threat Matrix

| Threat | Component | Mitigation | Verification |
|---|---|---|---|
| Plaintext Template Theft | Server Storage | CKKS Homomorphic Encryption | `test_compute.py` |
| Biometric Linkability | Database | FiLM key modulation (cosine < 0.15) | `test_inversion.py` |
| Template Replay | Transport/Server | Single-use server challenge nonces | `test_replay_tests.py` |
| Key Version Rollback | Protocol | Signed payload contains key version | `test_rotation_tests.py` |
| Score Tampering | Server/Transport | Threshold check & signing inside TEE | `test_key_release.py` |
| Database Tampering | Audit Log | SHA-256 hash-chained log | `test_database.py` |
| PII Data Leakage | Logging | Redaction middleware (regex mask) | `test_pii_logging.py` |
| Rate Limit Bypass | Backend API | Redis sliding window rate limiter | `test_api_enrollment.py` |
