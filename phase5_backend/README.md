# Phase 5 — Secure Storage & Transport Backend

## Overview
Phase 5 provides a production-grade FastAPI backend with TLS 1.3, asynchronous database ORM (SQLAlchemy + asyncpg/aiosqlite), Redis rate limiting, zero-PII logging, and tamper-evident audit hashing.

## Project Structure
```
phase5_backend/
├── config.yaml
├── requirements.txt
├── README.md
├── backend/
│   ├── main.py                 # FastAPI application factory
│   ├── config.py               # Pydantic Settings management
│   ├── database.py             # SQLAlchemy Async Engine & Session
│   ├── models.py               # ORM Models (User, Enrollment, AuditLog, NonceStore)
│   ├── schemas.py              # Request / Response Pydantic models
│   ├── dependencies.py         # Common FastAPI dependencies
│   ├── startup.py              # Initialization script
│   ├── api/
│   │   ├── enrollment.py       # POST /enroll
│   │   ├── verification.py     # POST /verify/challenge, POST /verify
│   │   ├── health.py           # GET /health, GET /ready
│   │   └── admin.py            # POST /admin/keys/rotate, GET /admin/audit
│   ├── services/
│   │   ├── he_service.py       # Phase 4 HE integration
│   │   ├── keystore_service.py # Phase 2 Keystore integration
│   │   └── audit_service.py    # Tamper-evident SHA256 audit chain
│   └── security/
│       ├── tls.py              # TLS 1.3 configuration & self-signed cert generator
│       ├── rate_limit.py       # Redis sliding-window rate limiter
│       └── pii_filter.py       # PII redaction filter & middleware
├── alembic/                    # Database migrations
│   └── env.py
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
├── scripts/
│   ├── run_server.sh
│   ├── generate_certs.sh
│   ├── migrate.sh
│   └── load_test.sh
└── tests/
    ├── test_api_enrollment.py
    ├── test_api_verification.py
    ├── test_pii_logging.py
    ├── test_database.py
    └── test_integration_p4.py
```

## How to Run Phase 5

### 1. Install Dependencies
```bash
cd phase5_backend
pip install -r requirements.txt
```

### 2. Start Infrastructure (Postgres + Redis)
```bash
docker-compose -f docker/docker-compose.yml up -d postgres redis
```

### 3. Generate TLS Certs
```bash
./scripts/generate_certs.sh
```

### 4. Run Migrations
```bash
./scripts/migrate.sh
```

### 5. Run Unit & Integration Tests
```bash
pytest tests/ -v
```

### 6. Start Server
```bash
./scripts/run_server.sh
```

### 7. Test API Endpoints (cURL)

#### Enroll
```bash
curl -k -X POST https://localhost:8443/enroll \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","encrypted_template":"...","client_pk_he":"...","key_version":1}'
```

#### Challenge
```bash
curl -k -X POST https://localhost:8443/verify/challenge \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice"}'
```

#### Verify
```bash
curl -k -X POST https://localhost:8443/verify \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","nonce":"...","encrypted_probe":"...","key_version":1}'
```

## Acceptance Criteria Checklist

| Criterion | Target | Verification |
| :--- | :--- | :--- |
| TLS 1.3 Only | No TLS 1.2/1.1/1.0 | `backend/security/tls.py` |
| POST /enroll | Stores Enc(t) + pk_he, returns 201 | `test_api_enrollment.py::test_enroll_success` |
| POST /verify/challenge | Returns unique nonce, 5-min TTL | `test_api_verification.py::test_challenge_issued` |
| POST /verify | Computes HE similarity, returns score + token | `test_api_verification.py::test_verify_success` |
| Replay Protection | Nonce single-use, 401 on replay | `test_api_verification.py::test_verify_replay_attack_fails` |
| Rate Limiting | Enroll 5/min, Verify 30/min | `test_api_enrollment.py::test_enroll_rate_limit` |
| Key Rotation | Admin endpoint rotates, invalidates old | `test_integration_p4.py::test_key_rotation_invalidates_old_template` |
| No PII in Logs | Template/ciphertext/key redacted | `test_pii_logging.py` (All Pass) |
| Audit Log Hash Chain | Tamper-evident, verifiable | `test_database.py::test_audit_log_hash_chain` |
| DB Schema | FKs, unique constraints, indexes | `test_database.py` |
| HE Integration | Real CKKS encrypt/compute/decrypt | `test_integration_p4.py::test_full_enroll_verify_flow` |
| Docker Compose | Postgres + Redis + Backend healthy | `docker-compose up` + health checks |

## Real vs Simulated Status

| Component | Status | Production Notes |
| :--- | :--- | :--- |
| FastAPI + TLS 1.3 | REAL | Production-grade ASGI server |
| PostgreSQL + AsyncPG | REAL | Production database |
| Redis Rate Limiting | REAL | Distributed rate limiting |
| HE Computation | REAL | Actual CKKS via TenSEAL |
| Keystore Operations | REAL | Phase 2 logic, file-backed (dev) |
| Audit Hash Chain | REAL | Cryptographic tamper evidence |
| PII Log Redaction | REAL | Middleware + filter enforced |
| Key Storage | FILESYSTEM | Dev: files; Prod: HSM/TEE (Phase 6) |
| Session Tokens | JWT (HS256) | Dev: hardcoded secret; Prod: RS256 + rotation |
| Admin Auth | API KEY | Dev: static; Prod: mTLS + RBAC |
