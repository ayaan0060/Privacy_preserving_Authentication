#!/usr/bin/env python3
"""
scripts/audit_provenance.py

Enforces Stage 0.2:
Fails if any file in results/final or results/raw is not in the manifest,
has a hash mismatch, or was modified after the manifest entry.
Also fails if any script under scripts/ contains a numeric literal assigned to a metric key.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scripts.provenance import audit_provenance

if __name__ == "__main__":
    success = audit_provenance()
    if not success:
        print("[FAIL] Audit Provenance failed integrity verification.")
        sys.exit(1)
    print("[PASS] Audit Provenance successfully verified all artifacts.")
    sys.exit(0)
