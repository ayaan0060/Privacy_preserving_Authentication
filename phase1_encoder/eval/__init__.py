# phase1_encoder/eval/__init__.py
from .metrics import (
    compute_eer,
    compute_verification_metrics,
    compute_identification_rank1,
    get_genuine_impostor_scores,
    plot_roc_det,
)
from .evaluate import main as evaluate_main

__all__ = [
    "compute_eer",
    "compute_verification_metrics",
    "compute_identification_rank1",
    "get_genuine_impostor_scores",
    "plot_roc_det",
    "evaluate_main",
]
