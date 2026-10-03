#!/usr/bin/env python3
"""
scripts/lint_paper.py

Lints paper.tex (and Research.tex) for Rule R1 & R5 compliance:
1. No hand-typed measured literals (percentages, ms, KB, req/s, AUC, D_sys, p-values).
   Every measured value must come from a macro in results/final/macros.tex.
2. No prohibited promotional or meta-commentary claims:
   - "provably unlinkable"
   - "optimal combination"
   - "spherical diffusion" as a security property
   - "eliminate(s)"
   - "strictly prevented" / "completely prevented"
   - "learns zero information"
   - "formal security analysis"
   - "missing in the literature"
   - "disproving the claim"
   - "resolving contradictions"
3. No unresolved references ("Section ??", "??").
"""

import sys
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
PAPER_PATH = ROOT_DIR / 'paper.tex'

PROHIBITED_PHRASES = [
    r"provably unlinkable",
    r"optimal combination",
    r"\beliminat(?:e|es|ing)\b",
    r"strictly prevented",
    r"completely prevented",
    r"learns zero information",
    r"formal security analysis",
    r"missing in the literature",
    r"disproving the claim",
    r"resolving.*contradiction",
    r"Section\s+\?\?",
    r"\\ref\{\s*\?\?\s*\}",
    r"data-independent",
    r"ideal distance",
    r"full spherical",
    r"complete diffusion",
    r"validating constant-time",
]

# Patterns for hardcoded measurements outside macros
MEASUREMENT_PATTERNS = [
    (r"\b\d+\.\d+\s*(?:\\%|%|percent)", "Hardcoded percentage literal"),
    (r"\b\d+(?:\.\d+)?\s*(?:\\,)?\s*(?:ms|milliseconds)\b", "Hardcoded millisecond literal"),
    (r"\b\d+(?:\.\d+)?\s*(?:\\,)?\s*(?:KB|MB)\b", "Hardcoded kilobyte/megabyte literal"),
    (r"\b\d+(?:\.\d+)?\s*(?:\\,)?\s*(?:req/s|requests per second)\b", "Hardcoded throughput literal"),
    (r"\bAUC\s*(?:of|=|:|\\le|\\ge)?\s*0\.\d{3,4}", "Hardcoded AUC literal"),
    (r"D_{\\leftrightarrow}^{\\mathit{sys}}\s*(?:=|<|>|\\le|\\ge)?\s*0\.\d{3,4}", "Hardcoded D_sys literal"),
    (r"\\Omega\s*(?:=|<|>|\\le|\\ge)?\s*0\.\d{3,4}", "Hardcoded Omega literal"),
    (r"\bp\s*[<>=]\s*10\^\{-?\d+\}", "Hardcoded p-value literal"),
    (r"\bp\s*=\s*0\.\d+", "Hardcoded p-value literal"),
    (r"\bd'\s*=\s*\d+\.\d+", "Hardcoded d-prime literal"),
]


def lint_file(file_path: Path) -> bool:
    print(f"Linting {file_path.name} against scientific integrity & macro rules...")
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    violations = []
    
    in_tabular = False

    for idx, line in enumerate(lines, 1):
        clean_line = line.strip()
        # Skip pure comments
        if clean_line.startswith('%'):
            continue
        # Remove trailing comments
        if '%' in line:
            clean_line = line.split('%')[0].strip()

        # Check for prohibited phrases
        for phrase in PROHIBITED_PHRASES:
            if re.search(phrase, clean_line, re.IGNORECASE):
                violations.append((idx, f"Prohibited phrase '{phrase}' found: {clean_line}"))

        # Skip lines defining macros or importing tables
        if clean_line.startswith(r"\newcommand") or clean_line.startswith(r"\input") or clean_line.startswith(r"\documentclass") or clean_line.startswith(r"\usepackage"):
            continue

        # Skip BibTeX references block or bibliography
        if clean_line.startswith(r"\bibliography") or clean_line.startswith(r"\bibliographystyle"):
            continue

        # Check for bare measurement literals
        for pattern, desc in MEASUREMENT_PATTERNS:
            match = re.search(pattern, clean_line)
            if match:
                # Allowed exceptions: table column specs, standard citations, or dimensions
                matched_str = match.group(0)
                violations.append((idx, f"{desc} '{matched_str}': {clean_line}"))

    if violations:
        print(f"\n[FAIL] Found {len(violations)} lint violations in {file_path.name}:")
        for line_num, msg in violations[:30]:
            print(f"  Line {line_num}: {msg}")
        if len(violations) > 30:
            print(f"  ... and {len(violations) - 30} more.")
        return False
    else:
        print(f"[✓] {file_path.name} PASSED all integrity & single-source-of-truth lint checks!")
        return True


def main():
    ok1 = lint_file(PAPER_PATH)
    res_path = ROOT_DIR / 'Research.tex'
    ok2 = True
    if res_path.exists():
        ok2 = lint_file(res_path)

    if not (ok1 and ok2):
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
