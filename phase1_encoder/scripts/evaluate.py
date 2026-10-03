# phase1_encoder/scripts/evaluate.py
"""
Evaluation script for Phase 1 Encoder.
Delegates to eval.evaluate.main.
"""
import os
import sys

# Add phase1_encoder root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eval.evaluate import main as eval_main

if __name__ == "__main__":
    eval_main()
