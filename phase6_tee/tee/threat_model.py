# phase6_tee/tee/threat_model.py
"""
FORMAL THREAT MODEL — Secure Context Boundary.

This document explicitly states what is protected by the SIMULATION
vs what REQUIRES real hardware (TEE/StrongBox/Secure Enclave/HSM).

READ THIS BEFORE DEPLOYING.
"""
from typing import List

THREAT_MODEL = """
================================================================================
CANCELABLE BIOMETRIC AUTHENTICATION — THREAT MODEL
================================================================================

SYSTEM OVERVIEW:
- Client: Fingerprint sensor → Encoder (normal world) → FiLM (normal world) 
          → HE Encrypt (normal world) → SecureContext (TEE/simulation)
- Server: Stores Enc(template) → Computes Enc(score) → Returns Enc(score)
- SecureContext: Decrypts score → Threshold check → Signs nonce → Returns signature

TRUST BOUNDARIES:
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

================================================================================
SIMULATION LIMITATIONS
================================================================================

================================================================================
REAL TEE GUARANTEES
================================================================================

| Threat                          | Simulation | Real TEE | Mitigation |
|---------------------------------|------------|----------|------------|
| Memory scraping (read RAM)      | NO         | YES      | Hardware memory isolation, encryption |
| Key extraction via debugger     | NO         | YES      | Debug disable, secure boot |
| Key extraction via side-channel | NO         | YES      | Constant-time, hardware countermeasures |
| Malicious OS/kernel             | NO         | YES      | Hardware isolation (TrustZone/SEP) |
| Physical device theft           | NO         | YES      | Secure element, tamper resistance |
| Rollback to old firmware        | NO         | YES      | Verified boot, rollback protection |
| Nonce replay (if storage leak)  | PARTIAL    | YES      | Monotonic counters in hardware |
| HE secret key extraction        | NO         | YES      | Key never leaves TEE |

================================================================================
THREATS MITIGATED BY BOTH SIMULATION AND REAL TEE (LOGIC-LEVEL)
================================================================================

| Threat                          | Mitigation |
|---------------------------------|------------|
| Template replay                 | Server nonce challenge |
| Score manipulation              | HE encryption + TEE threshold check |
| Key rollback                    | Key version in signed payload |
| Device impersonation            | Device signing key + attestation |
| Session hijacking               | Short-lived signed nonce |
| Biometric revocation            | Key rotation → new key vector → unlinkable template |

================================================================================
"""


def print_threat_model():
    """Print the threat model for documentation."""
    print(THREAT_MODEL)


def get_simulation_limitations() -> List[str]:
    """Return list of simulation limitations for documentation."""
    return [
        "No hardware memory isolation (keys in process memory)",
        "No hardware RNG (uses /dev/urandom)",
        "No remote attestation (simulated device identity)",
        "No protection against root/OS compromise",
        "No tamper resistance",
        "No side-channel resistance (timing, power, EM)",
        "No verified boot chain",
        "HE secret key exists in normal world (passed to simulation)",
        "Nonce tracking in normal world memory (replay possible if memory dumped)",
    ]


def get_real_tee_guarantees() -> List[str]:
    """Return list of guarantees provided by real TEE hardware."""
    return [
        "Hardware-enforced memory isolation (TrustZone/SEP/Secure Element)",
        "Hardware RNG with entropy certification",
        "Hardware-attested device identity (StrongBox/SE attestation)",
        "Protection against OS/kernel compromise",
        "Tamper resistance (physical)",
        "Side-channel countermeasures",
        "Verified boot / rollback protection",
        "Keys never leave hardware boundary (including HE secret key)",
        "Monotonic counters for nonce freshness",
    ]


if __name__ == "__main__":
    print_threat_model()
