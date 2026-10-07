#!/usr/bin/env python3
"""
scripts/provenance.py

Manifest recorder and provenance audit framework.
Enforces Rule R1 and Stage 0:
- Every file in results/final and results/raw must be recorded in results/final/manifest.json.
- Verifies SHA256 hashes of results and their producing scripts.
- Detects if results were modified after their manifest entry.
- Checks scripts/ for forbidden numeric literals assigned to metric keys.
"""

import os
import sys
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent
FINAL_DIR = ROOT_DIR / "results" / "final"
RAW_DIR = ROOT_DIR / "results" / "raw"
MANIFEST_PATH = FINAL_DIR / "manifest.json"


def sha256_file(path: Path) -> str:
    """Computes SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def record_manifest_entry(
    output_path: Path,
    script_path: Path,
    protocol: str = "N/A",
    seed: any = "N/A",
    metadata: dict = None
):
    """Records an artifact into results/final/manifest.json."""
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    rel_out = str(output_path.resolve().relative_to(ROOT_DIR))
    rel_script = str(script_path.resolve().relative_to(ROOT_DIR))

    out_hash = sha256_file(output_path)
    script_hash = sha256_file(script_path)
    mtime = output_path.stat().st_mtime
    iso_time = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    manifest[rel_out] = {
        "output_file": rel_out,
        "sha256": out_hash,
        "producing_script": rel_script,
        "producing_script_sha256": script_hash,
        "timestamp_utc": iso_time,
        "protocol": protocol,
        "seed": seed,
        "metadata": metadata or {}
    }

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def audit_provenance() -> bool:
    """
    Audits the manifest and scripts for integrity:
    1. Every file in results/final and results/raw must be in manifest.
    2. Hashes must match exactly.
    3. No script in scripts/ may assign numeric literals to metric keys.
    """
    print("=" * 70)
    print("RUNNING PROVENANCE AND INTEGRITY AUDIT")
    print("=" * 70)

    if not MANIFEST_PATH.exists():
        print(f"[FAIL] Manifest missing: {MANIFEST_PATH.relative_to(ROOT_DIR)}")
        return False

    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)

    failures = []
    passes = []

    # 1. Audit files in results/final and results/raw
    target_dirs = [FINAL_DIR, RAW_DIR]
    all_files = []
    for d in target_dirs:
        if d.exists():
            for p in d.rglob("*"):
                if p.is_file() and p.name != "manifest.json" and not p.name.startswith("."):
                    all_files.append(p)

    for p in all_files:
        rel = str(p.resolve().relative_to(ROOT_DIR))
        if rel not in manifest:
            failures.append(f"UNTRACKED_FILE: {rel} is not registered in manifest.json")
            continue

        entry = manifest[rel]
        current_hash = sha256_file(p)
        if current_hash != entry["sha256"]:
            failures.append(
                f"HASH_MISMATCH: {rel} current hash {current_hash[:8]} != manifest {entry['sha256'][:8]}"
            )
            continue

        script_p = ROOT_DIR / entry["producing_script"]
        if not script_p.exists():
            failures.append(
                f"MISSING_SCRIPT: {rel} producing script {entry['producing_script']} does not exist"
            )
            continue

        current_script_hash = sha256_file(script_p)
        if current_script_hash != entry["producing_script_sha256"]:
            failures.append(
                f"SCRIPT_HASH_MISMATCH: producing script {entry['producing_script']} changed after output was written"
            )
            continue

        passes.append(f"VERIFIED: {rel} (by {entry['producing_script']})")

    # 2. Check for forbidden numeric literals assigned to metric keys in scripts/
    # Forbidden patterns: variable names like auc_*, throughput, service_time, tau, far_*, frr_*
    # assigned directly from a float or integer literal (e.g., auc_mlp = 0.7162)
    metric_assign_regex = re.compile(
        r"""^\s*(?:[\w\.]*?)?(auc_\w*|throughput\w*|service_time\w*|tau\w*|far_\w*|frr_\w*)\s*=\s*([0-9]+\.[0-9]+|[0-9]+)\s*(?:#.*)?$"""
    )
    # Exclude harmless defaults in function headers or standard constants like MASTER_SEED / DIM / default params
    exempt_names = {"dim", "num_groups", "group_size", "n_boot", "seed", "k", "n"}

    script_files = list((ROOT_DIR / "scripts").glob("*.py"))
    for sf in script_files:
        if sf.name in ["audit_provenance.py", "provenance.py"]:
            continue
        with open(sf, "r") as f:
            for line_no, line in enumerate(f, 1):
                clean = line.strip()
                if clean.startswith("#"):
                    continue
                m = metric_assign_regex.match(clean)
                if m:
                    key, val = m.group(1), m.group(2)
                    if key.lower() not in exempt_names:
                        failures.append(
                            f"FORBIDDEN_NUMERIC_LITERAL in {sf.name}:{line_no}: '{key} = {val}'"
                        )

    print(f"\nAudit completed: {len(passes)} artifacts verified, {len(failures)} failures.")
    for p in passes[:15]:
        print(f"  [✓] {p}")
    if len(passes) > 15:
        print(f"  ... and {len(passes) - 15} more verified files.")

    for f in failures:
        print(f"  [✗] {f}")

    print("=" * 70)
    return len(failures) == 0


if __name__ == "__main__":
    if not audit_provenance():
        sys.exit(1)
    print("PROVENANCE AUDIT PASSED")
