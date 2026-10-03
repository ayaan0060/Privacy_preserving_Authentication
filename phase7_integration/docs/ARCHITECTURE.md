# System Architecture

## High-Level Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Fingerprint │────▶│   Encoder   │────▶│    FiLM     │────▶│     HE      │
│   Sensor    │     │ (ResNet18)  │     │   Fusion    │     │   Encrypt   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                    │  Embedding  │     │   Key Vec   │     │   Enc(t)    │
                    │  x ∈ ℝ²⁵⁶   │     │  k ∈ ℝ²⁵⁶   │     │   (CKKS)    │
                    └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                                                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Session   │◀────│   Server    │◀────│   TEE Key   │◀────│   Server    │
│    Token    │     │  Verifies   │     │   Release   │     │  Computes   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           ▲                   ▲                   ▲
                           │                   │                   │
                    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                    │  Signature  │     │  Threshold  │     │ Enc(score)  │
                    │  Verified   │     │    Check    │     │   (CKKS)    │
                    └─────────────┘     └─────────────┘     └─────────────┘
```

## Component Details

### Phase 1: CNN Encoder
- **Model**: ResNet18 (modified for 1-channel, 96×96 input)
- **Loss**: ArcFace (margin=0.5, scale=64)
- **Output**: 256-d L2-normalized embedding
- **Export**: ONNX (opset 17), TFLite INT8, CoreML FP16

### Phase 2: Cancelable Key Store
- **Seed**: 32 bytes CSPRNG
- **Derivation**: HKDF-SHA256 → 256-d key vector in [-1, 1]
- **Rotation**: Versioned, grace period, revocation
- **Interface**: `SecureKeyStore` ABC (swap for TEE/HSM)

### Phase 3: FiLM Fusion
- **Architecture**: γ(k), β(k) via 2-layer MLPs
- **Fusion**: t = γ ⊙ x + β → L2Norm(t)
- **Property**: Same x, different k → uncorrelated t (cosine < 0.15)
- **Training**: Post-hoc (encoder frozen)

### Phase 4: CKKS Homomorphic Encryption
- **Scheme**: CKKS (approximate arithmetic)
- **Parameters**: N=8192, logQ=200, scale=2⁴⁰
- **Security**: 128-bit classical
- **Operation**: Homomorphic dot product (mult + 8 rotations)

### Phase 5: Secure Backend
- **Framework**: FastAPI + SQLAlchemy + Redis
- **Transport**: TLS 1.3 only
- **Storage**: Encrypted templates (BYTEA), audit log (hash-chained)
- **API**: Enroll, Challenge, Verify, Admin

### Phase 6: TEE Key Release
- **Boundary**: `SecureContext` ABC
- **Simulation**: Software (mlock + zeroize)
- **Production**: StrongBox / Secure Enclave / OP-TEE
- **Protocol**: Decrypt → Threshold → Sign(nonce||score||version)

### Phase 7: Integration
- **Pipeline**: End-to-end orchestration
- **Adversarial**: Replay, rotation, inversion, side-channel, extraction
- **Benchmarks**: Latency, throughput, accuracy

## Trust Boundaries

| Boundary | Components | Trust Assumptions |
|---|---|---|
| Normal World | Sensor, Encoder, FiLM, HE Encrypt | Untrusted |
| Server | HE Compute, Storage, Audit | Honest-but-curious |
| Secure Context | HE Decrypt, Threshold, Sign | **Hardware-isolated** (TEE) |

## Security Guarantees

| Property | Mechanism | Phase |
|---|---|---|
| Cancelable | Key rotation → new k → unlinkable t | 2, 3 |
| Template Protection | HE encryption, server computes on ciphertext | 4 |
| Score Confidentiality | Decryption only in TEE | 6 |
| Replay Prevention | Server nonce + TEE nonce check | 5, 6 |
| Rollback Prevention | Key version in signed payload | 2, 6 |
| Auditability | Hash-chained audit log | 5 |
| PII-Free Logs | Redaction middleware | 5 |
