# core/unlinkability.py
"""
ISO/IEC 24745 Unlinkability Evaluation Framework
Reference: Gómez-Barrero, Galbally, Rathgeb, Busch,
"General Framework to Evaluate Unlinkability in Biometric Template Protection Systems",
IEEE TIFS 2018.

Implements:
1. Gómez-Barrero D_sys (system linkability) and Omega (system unlinkability).
2. Explicit degenerate / constant score distribution handling.
3. Permutation null calibration to establish the estimator finite-sample noise floor.
4. Bootstrap confidence intervals for D_sys and ROC-AUC.
"""

from typing import Tuple, Dict, Any, Optional
import numpy as np
from sklearn.metrics import roc_auc_score


def compute_gomez_barrero(
    mated_scores: np.ndarray,
    non_mated_scores: np.ndarray,
    num_bins: int = 100,
    rule: str = 'uniform'
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Computes ISO/IEC 24745 system linkability D_sys and unlinkability Omega.
    
    Returns:
        d_sys: float in [0.0, 1.0] (0 = fully unlinkable, 1 = fully linkable)
        omega: float in [0.0, 1.0] (1 - d_sys)
        details: dict containing local curves and binning metadata
    """
    mated_scores = np.asarray(mated_scores, dtype=np.float64)
    non_mated_scores = np.asarray(non_mated_scores, dtype=np.float64)
    all_scores = np.concatenate([mated_scores, non_mated_scores])
    
    s_min = float(np.min(all_scores))
    s_max = float(np.max(all_scores))
    
    # Degenerate case: constant score distributions (e.g. BioHashing abs-val / IoM sorted-mag)
    # If mated and non-mated scores are identical point masses, they carry zero discriminatory information.
    if np.isclose(s_min, s_max) or (np.std(mated_scores) < 1e-8 and np.std(non_mated_scores) < 1e-8 and np.isclose(np.mean(mated_scores), np.mean(non_mated_scores))):
        return 0.0, 1.0, {
            's_min': s_min, 's_max': s_max, 'num_bins': num_bins,
            'is_degenerate': True, 'd_local': np.array([0.0]),
            'bin_centers': np.array([s_min])
        }
    
    # Choose bin edges
    if rule == 'freedman_diaconis':
        iqr = np.percentile(all_scores, 75) - np.percentile(all_scores, 25)
        if iqr > 1e-6:
            h = 2.0 * iqr / (len(all_scores) ** (1.0 / 3.0))
            k = int(np.clip(np.ceil((s_max - s_min) / h), 20, 300))
        else:
            k = num_bins
        bins = np.linspace(s_min, s_max, k + 1)
    else:
        bins = np.linspace(s_min, s_max, num_bins + 1)
    
    p_mated, _ = np.histogram(mated_scores, bins=bins, density=True)
    p_nonmated, _ = np.histogram(non_mated_scores, bins=bins, density=True)
    bin_widths = np.diff(bins)
    bin_centers = 0.5 * (bins[:-1] + bins[1:])
    
    denom = p_mated + p_nonmated + 1e-12
    ratio = p_mated / denom
    # Gómez-Barrero local linkability: D_local(s) = max(0, 2 * ratio - 1)
    d_local = np.maximum(0.0, 2.0 * ratio - 1.0)
    
    # System linkability: D_sys = \int D_local(s) * p(s | mated) ds
    d_sys = float(np.sum(d_local * p_mated * bin_widths))
    d_sys = float(np.clip(d_sys, 0.0, 1.0))
    omega = 1.0 - d_sys
    
    return round(d_sys, 4), round(omega, 4), {
        's_min': s_min, 's_max': s_max, 'num_bins': len(bin_widths),
        'is_degenerate': False, 'd_local': d_local,
        'bin_centers': bin_centers, 'p_mated': p_mated, 'p_nonmated': p_nonmated
    }


def compute_null_calibration(
    mated_scores: np.ndarray,
    non_mated_scores: np.ndarray,
    num_permutations: int = 1000,
    num_bins: int = 100,
    seed: int = 42
) -> Dict[str, float]:
    """
    Computes finite-sample noise floor for D_sys under permutation of mated/non-mated labels.
    Under H_0: mated and non-mated scores follow the identical distribution.
    """
    rng = np.random.RandomState(seed)
    n_m = len(mated_scores)
    n_nm = len(non_mated_scores)
    pooled = np.concatenate([mated_scores, non_mated_scores])
    
    null_d_sys = np.empty(num_permutations, dtype=np.float64)
    for i in range(num_permutations):
        perm = rng.permutation(len(pooled))
        pseudo_m = pooled[perm[:n_m]]
        pseudo_nm = pooled[perm[n_m:]]
        d_val, _, _ = compute_gomez_barrero(pseudo_m, pseudo_nm, num_bins=num_bins)
        null_d_sys[i] = d_val
        
    return {
        'null_mean': round(float(np.mean(null_d_sys)), 4),
        'null_std': round(float(np.std(null_d_sys)), 4),
        'null_p95': round(float(np.percentile(null_d_sys, 95)), 4),
        'null_p99': round(float(np.percentile(null_d_sys, 99)), 4),
    }


def compute_bootstrap_cis(
    mated_scores: np.ndarray,
    non_mated_scores: np.ndarray,
    num_bootstraps: int = 1000,
    num_bins: int = 100,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Computes 95% bootstrap confidence intervals for ROC-AUC, D_sys, and Omega.
    """
    rng = np.random.RandomState(seed)
    n_m = len(mated_scores)
    n_nm = len(non_mated_scores)
    
    y_true = np.concatenate([np.ones(n_m), np.zeros(n_nm)])
    scores = np.concatenate([mated_scores, non_mated_scores])
    auc_point = float(roc_auc_score(y_true, scores))
    dsys_point, omega_point, _ = compute_gomez_barrero(mated_scores, non_mated_scores, num_bins=num_bins)
    
    auc_samples = np.empty(num_bootstraps, dtype=np.float64)
    dsys_samples = np.empty(num_bootstraps, dtype=np.float64)
    
    for b in range(num_bootstraps):
        idx_m = rng.choice(n_m, size=n_m, replace=True)
        idx_nm = rng.choice(n_nm, size=n_nm, replace=True)
        b_m = mated_scores[idx_m]
        b_nm = non_mated_scores[idx_nm]
        
        b_scores = np.concatenate([b_m, b_nm])
        # AUC
        auc_samples[b] = roc_auc_score(y_true, b_scores)
        # D_sys
        d_val, _, _ = compute_gomez_barrero(b_m, b_nm, num_bins=num_bins)
        dsys_samples[b] = d_val
        
    return {
        'auc_point': round(auc_point, 4),
        'auc_ci_lower': round(float(np.percentile(auc_samples, 2.5)), 4),
        'auc_ci_upper': round(float(np.percentile(auc_samples, 97.5)), 4),
        'dsys_point': round(dsys_point, 4),
        'dsys_ci_lower': round(float(np.percentile(dsys_samples, 2.5)), 4),
        'dsys_ci_upper': round(float(np.percentile(dsys_samples, 97.5)), 4),
        'omega_point': round(omega_point, 4),
        'omega_ci_lower': round(float(1.0 - np.percentile(dsys_samples, 97.5)), 4),
        'omega_ci_upper': round(float(1.0 - np.percentile(dsys_samples, 2.5)), 4),
    }
