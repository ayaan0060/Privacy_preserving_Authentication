# Deployment Guide

## Prerequisites

### Infrastructure
- PostgreSQL 16+
- Redis 7+
- TLS certificates (valid CA-signed for production)
- Hardware Security Module (HSM) or TEE-enabled devices

### Android Deployment
- Android 9+ (API 28) devices with StrongBox
- `android.hardware.keystore.strongbox` feature
- BiometricPrompt API (FaceID/Fingerprint)

### iOS Deployment
- iOS 13+ / macOS 10.15+
- Secure Enclave (A7+ / T1/T2/M1)
- LocalAuthentication framework

### Server Deployment
- Linux with OP-TEE (for server-side TEE) OR
- Cloud HSM (AWS CloudHSM, Azure Dedicated HSM, GCP Cloud HSM)

## Configuration

### Environment Variables
```bash
# Required
export CONFIG_PATH=/etc/bioauth/config.yaml
export KEYSTORE_MASTER_KEY=<32-byte-hex-from-HSM>
export DEVICE_KEY_PASSWORD=<strong-password>
export JWT_SECRET=<32-byte-random>
export DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/bioauth
export REDIS_URL=redis://host:6379/0

# TLS
export TLS_CERT_FILE=/etc/bioauth/certs/server.crt
export TLS_KEY_FILE=/etc/bioauth/certs/server.key
export TLS_CA_FILE=/etc/bioauth/certs/ca.crt  # For mTLS
```

## Infrastructure Setup

```bash
cd phase5_backend
docker-compose -f docker/docker-compose.yml up -d postgres redis
./scripts/migrate.sh
```

## Key Provisioning Ceremony

### 1. Generate HE Keys (offline, air-gapped)
```bash
python -m he.context --key-dir /secure/he_keys
# Distribute client_secret.key to client devices via secure channel
# Distribute server_public.key to servers
```

### 2. Provision Device Keys (per device, in TEE)
- **Android**: Generate in StrongBox via `KeyGenParameterSpec`
- **iOS**: Generate in Secure Enclave via `SecKeyCreateRandomKey`
- **Server**: Generate in OP-TEE TA or HSM

### 3. Enroll Users
```bash
# Client captures fingerprint
# Client: x = Encoder(fingerprint)
# Client: k = Keystore.get_key_vector()
# Client: t = FiLM(x, k)
# Client: Enc(t) = HE_Encrypt(t)
# Client → Server: POST /enroll {Enc(t), pk_he, key_version}
```

## Docker Deployment

```bash
# Production docker-compose
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d

# With nginx reverse proxy
docker-compose -f docker/docker-compose.yml up -d nginx
```

### Production Overrides (`docker-compose.prod.yml`)
```yaml
services:
  backend:
    environment:
      - CONFIG_PATH=/etc/bioauth/config.yaml
      - KEYSTORE_MASTER_KEY_FILE=/run/secrets/keystore_master_key
    secrets:
      - keystore_master_key
    volumes:
      - ./certs:/app/certs:ro
      - ./exports/he_keys:/app/exports/he_keys:ro

secrets:
  keystore_master_key:
    external: true
```

## Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bioauth-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bioauth-backend
  template:
    spec:
      containers:
      - name: backend
        image: bioauth/backend:latest
        ports:
        - containerPort: 8443
        envFrom:
        - secretRef:
            name: bioauth-secrets
        volumeMounts:
        - name: certs
          mountPath: /app/certs
          readOnly: true
        - name: he-keys
          mountPath: /app/exports/he_keys
          readOnly: true
      volumes:
      - name: certs
        secret:
          secretName: bioauth-certs
      - name: he-keys
        secret:
          secretName: bioauth-he-keys
```

## Monitoring & Alerting

### Key Metrics
- **Latency**: p50, p95, p99 for each phase
- **Throughput**: req/s, concurrent users
- **Error Rate**: 5xx, 4xx, HE failures, TEE failures
- **Security**: Failed verifications, replay attempts, rotation events

### Prometheus Alerts
```yaml
groups:
- name: bioauth
  rules:
  - alert: HighVerificationLatency
    expr: histogram_quantile(0.95, rate(bioauth_verify_latency_seconds_bucket[5m])) > 0.5
    for: 2m
    labels:
      severity: warning
  - alert: VerificationErrorRate
    expr: rate(bioauth_verify_errors_total[5m]) > 0.05
    for: 1m
    labels:
      severity: critical
  - alert: ReplayAttackDetected
    expr: rate(bioauth_nonce_replay_total[5m]) > 10
    for: 1m
    labels:
      severity: critical
```

## Security Hardening Checklist

- [ ] TLS 1.3 only, valid certificates
- [ ] mTLS for inter-service communication
- [ ] HSM for keystore master key
- [ ] TEE attestation verification enabled
- [ ] Rate limiting configured per endpoint
- [ ] Audit log aggregation (immutable storage)
- [ ] Log redaction verified in production
- [ ] HE keys rotated per policy
- [ ] Device keys rotated per policy
- [ ] Third-party security audit completed
- [ ] Legal/compliance review (GDPR, BIPA, CCPA)
- [ ] Incident response plan documented
- [ ] Penetration testing scheduled

## Rollback Procedure
- **Database**: Alembic downgrade (tested in staging)
- **HE Keys**: Maintain previous key generation, support multiple versions
- **Model**: Keep previous ONNX exports, versioned in storage
- **Config**: Git-managed, instant rollback via git revert

## Capacity Planning

| Component | Baseline | 10x Growth | 100x Growth |
|---|---|---|---|
| PostgreSQL | 2 CPU, 8 GB | 8 CPU, 32 GB | Cluster (Citus) |
| Redis | 1 CPU, 2 GB | 4 CPU, 16 GB | Redis Cluster |
| Backend | 2 CPU, 4 GB | 8 CPU, 16 GB | K8s HPA (50 pods) |
| HE Compute | CPU | CPU + GPU | Dedicated HE Accelerators |

## Launch Application

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend.main:app \
  --certfile /etc/bioauth/certs/server.crt \
  --keyfile /etc/bioauth/certs/server.key \
  --bind 0.0.0.0:8443
```
