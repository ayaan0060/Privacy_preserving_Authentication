# Threat Model — Cancelable Biometric Authentication

> **Auto-generated from `tee/threat_model.py` — see source for executable version.**

## System Overview

- Client: Fingerprint sensor → Encoder (normal world) → FiLM (normal world) → HE Encrypt (normal world) → SecureContext (TEE/simulation)
- Server: Stores Enc(template) → Computes Enc(score) → Returns Enc(score)
- SecureContext: Decrypts score → Threshold check → Signs nonce → Returns signature

## Security Boundaries

### Normal World (Untrusted)
- Fingerprint sensor
- CNN Encoder (ResNet18)
- FiLM Fusion Network
- CKKS Encryption/Decryption
- Network transport (TLS 1.3)

### Secure Context (TEE / Simulation)
- HE Decryption (similarity score)
- Threshold Comparison
- Nonce Freshness Check
- Key Version Validation
- Device Signing (ECDSA P-256)

## Threat Matrix

| Threat | Simulation | Real TEE | Notes |
|---|---|---|---|
| Memory scraping | ❌ | ✅ | Requires TrustZone/SEP |
| Debugger extraction | ❌ | ✅ | Debug disable |
| Side-channels | ❌ | ✅ | HW countermeasures |
| Malicious OS | ❌ | ✅ | Hardware isolation |
| Physical theft | ❌ | ✅ | Secure element |
| Rollback | ❌ | ✅ | Verified boot |
| Template replay | ✅ | ✅ | Server nonce |
| Score manipulation | ✅ | ✅ | HE + TEE check |
| Key rollback | ✅ | ✅ | Version in payload |
| Device impersonation | ✅ | ✅ | Device key + attestation |

## Residual Risks

1. **Sensor spoofing** — Out of scope (requires liveness detection)
2. **Model extraction** — Rate limiting, watermarking
3. **Supply chain** — Reproducible builds, code signing
4. **Insider threat** — Multi-party key ceremony

## Simulation Limitations

The software simulation (`SoftwareSecureContext`) provides **correct logic** but **no hardware isolation**:

- Keys in process memory (swappable, readable by debugger)
- `/dev/urandom` instead of hardware RNG
- No attestation (simulated device identity)
- No protection against root compromise
- No side-channel resistance

## Production Requirements

Before deploying with real users:

1. [ ] Replace `SoftwareSecureContext` with hardware implementation
2. [ ] Provision device keys in StrongBox/Secure Enclave/HSM
3. [ ] Seal HE secret keys to TEE at enrollment
4. [ ] Enable attestation verification on server
5. [ ] Third-party security audit
6. [ ] Legal/compliance review (GDPR Art. 9, BIPA, CCPA)

## Hardware Integration References

- **Android StrongBox**: `tee/production/android_keystore.py`
- **iOS Secure Enclave**: `tee/production/ios_secure_enclave.py`
- **OP-TEE**: `tee/production/optee_ta.py`
