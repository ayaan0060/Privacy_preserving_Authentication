#!/usr/bin/env bash
# ==============================================================================
# Master Reproduction Script
# Privacy-Preserving Fingerprint Authentication Using Cancelable Templates,
# FiLM, and CKKS Homomorphic Encryption
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

PYTHON="${SCRIPT_DIR}/.venv/bin/python"

if [ ! -f "${PYTHON}" ]; then
    echo "Virtual environment not found at .venv! Please run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

echo "======================================================================"
echo "Phase 1: Running Experiments & Generating Raw Benchmarks..."
echo "======================================================================"
"${PYTHON}" scripts/run_all_experiments.py

echo "======================================================================"
echo "Phase 2: Generating Vector Graphics Figures..."
echo "======================================================================"
"${PYTHON}" scripts/make_figures.py

echo "======================================================================"
echo "Phase 3: Generating Formatted LaTeX Tables..."
echo "======================================================================"
"${PYTHON}" scripts/make_tables.py

echo "======================================================================"
echo "Phase 4: Compiling Academic Paper PDF..."
echo "======================================================================"
if command -v tectonic &> /dev/null; then
    echo "Compiling paper.tex with Tectonic..."
    tectonic paper.tex
    echo "Compiling Research.tex with Tectonic..."
    tectonic Research.tex
elif command -v pdflatex &> /dev/null; then
    pdflatex -interaction=nonstopmode paper.tex
    bibtex paper
    pdflatex -interaction=nonstopmode paper.tex
    pdflatex -interaction=nonstopmode paper.tex
else
    echo "Warning: No LaTeX compiler found (tectonic or pdflatex). PDF compilation skipped."
fi

echo "======================================================================"
echo "Reproduction Complete! All benchmarks, figures, tables, and papers updated."
echo "======================================================================"
