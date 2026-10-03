import os
import sys
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.interpolate import interp1d

def compute_eer_metrics(genuine_scores: np.ndarray, impostor_scores: np.ndarray, num_steps: int = 2000) -> dict:
    """
    Computes EER, FAR, FRR, ROC-AUC, TAR@FAR=1%, TAR@FAR=0.1%, and score distribution statistics.
    """
    genuine_scores = np.asarray(genuine_scores, dtype=np.float64)
    impostor_scores = np.asarray(impostor_scores, dtype=np.float64)

    all_scores = np.concatenate([genuine_scores, impostor_scores])
    min_score, max_score = float(np.min(all_scores)), float(np.max(all_scores))

    thresholds = np.linspace(min_score - 1e-4, max_score + 1e-4, num_steps)
    far_list = []
    frr_list = []

    n_gen = len(genuine_scores)
    n_imp = len(impostor_scores)

    for th in thresholds:
        far = np.sum(impostor_scores >= th) / float(n_imp)
        frr = np.sum(genuine_scores < th) / float(n_gen)
        far_list.append(far)
        frr_list.append(frr)

    far_arr = np.array(far_list)
    frr_arr = np.array(frr_list)
    tpr_arr = 1.0 - frr_arr

    # EER calculation
    diff = far_arr - frr_arr
    idx = np.nanargmin(np.abs(diff))

    eer_val = float((far_arr[idx] + frr_arr[idx]) / 2.0)
    eer_th = float(thresholds[idx])

    try:
        f_far = interp1d(thresholds, far_arr, kind='linear')
        f_frr = interp1d(thresholds, frr_arr, kind='linear')
        
        low, high = thresholds[0], thresholds[-1]
        for _ in range(40):
            mid = (low + high) / 2.0
            if f_far(mid) > f_frr(mid):
                low = mid
            else:
                high = mid
        eer_th = float(mid)
        eer_val = float((f_far(mid) + f_frr(mid)) / 2.0)
    except Exception:
        pass

    # ROC-AUC calculation (Trapezoidal integration of TPR vs FAR)
    # Sort by FAR ascending
    sorted_indices = np.argsort(far_arr)
    sorted_far = far_arr[sorted_indices]
    sorted_tpr = tpr_arr[sorted_indices]
    roc_auc = float(np.trapezoid(sorted_tpr, sorted_far))

    # TAR @ FAR = 1% (0.01) and TAR @ FAR = 0.1% (0.001)
    def get_tar_at_far(target_far: float) -> float:
        valid_idxs = np.where(far_arr <= target_far)[0]
        if len(valid_idxs) > 0:
            best_idx = valid_idxs[0] # lowest threshold satisfying far <= target_far
            return float(tpr_arr[best_idx])
        return 0.0

    tar_at_far_1pct = get_tar_at_far(0.01)
    tar_at_far_01pct = get_tar_at_far(0.001)

    gen_min, gen_max = float(np.min(genuine_scores)), float(np.max(genuine_scores))
    gen_mean, gen_std = float(np.mean(genuine_scores)), float(np.std(genuine_scores))
    
    imp_min, imp_max = float(np.min(impostor_scores)), float(np.max(impostor_scores))
    imp_mean, imp_std = float(np.mean(impostor_scores)), float(np.std(impostor_scores))

    total_pairs = n_gen + n_imp
    eer_percent_str = f"EER: {eer_val * 100.0:.2f}% (N={total_pairs:,})"

    metrics = {
        'total_pairs': total_pairs,
        'num_genuine_pairs': n_gen,
        'num_impostor_pairs': n_imp,
        'EER_percent': round(eer_val * 100.0, 4),
        'EER_threshold': round(eer_th, 4),
        'EER_formatted_string': eer_percent_str,
        'FAR_at_threshold': round(float(far_arr[idx]), 6),
        'FRR_at_threshold': round(float(frr_arr[idx]), 6),
        'ROC_AUC': round(roc_auc, 6),
        'TAR_at_FAR_1pct': round(tar_at_far_1pct * 100.0, 4),
        'TAR_at_FAR_01pct': round(tar_at_far_01pct * 100.0, 4),
        'genuine_stats': {
            'min': round(gen_min, 4),
            'max': round(gen_max, 4),
            'mean': round(gen_mean, 4),
            'std': round(gen_std, 4)
        },
        'impostor_stats': {
            'min': round(imp_min, 4),
            'max': round(imp_max, 4),
            'mean': round(imp_mean, 4),
            'std': round(imp_std, 4)
        },
        'thresholds': thresholds.tolist(),
        'far': far_arr.tolist(),
        'frr': frr_arr.tolist(),
        'tpr': tpr_arr.tolist()
    }

    return metrics

def plot_eer_curves(metrics: dict, output_png: Path, title: str):
    """Plots FAR/FRR vs Threshold alongside the ROC curve."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    thresholds = metrics['thresholds']
    far = metrics['far']
    frr = metrics['frr']
    tpr = metrics['tpr']

    # Subplot 1: FAR & FRR vs Threshold
    ax1.plot(thresholds, far, label='FAR (False Acceptance Rate)', color='#d9534f', linewidth=2)
    ax1.plot(thresholds, frr, label='FRR (False Rejection Rate)', color='#0275d8', linewidth=2)
    eer_th = metrics['EER_threshold']
    ax1.axvline(eer_th, color='#5cb85c', linestyle='--', linewidth=1.8, label=f"EER Threshold ({eer_th:.4f})")
    ax1.set_xlabel('Similarity Threshold', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Error Rate', fontsize=11, fontweight='bold')
    ax1.set_title(f"{title}\n{metrics['EER_formatted_string']}", fontsize=12, fontweight='bold')
    ax1.legend(loc='center right', fontsize=10)
    ax1.grid(True, linestyle=':', alpha=0.6)

    # Subplot 2: ROC Curve (TAR vs FAR)
    ax2.plot(far, tpr, color='#5bc0de', linewidth=2, label=f"ROC (AUC = {metrics['ROC_AUC']:.4f})")
    ax2.plot([0, 1], [0, 1], color='gray', linestyle='--', alpha=0.7)
    ax2.set_xlabel('False Acceptance Rate (FAR)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('True Acceptance Rate (TAR = 1 - FRR)', fontsize=11, fontweight='bold')
    ax2.set_title(f"ROC Curve\nTAR @ 1% FAR: {metrics['TAR_at_FAR_1pct']:.2f}%", fontsize=12, fontweight='bold')
    ax2.legend(loc='lower right', fontsize=10)
    ax2.grid(True, linestyle=':', alpha=0.6)

    plt.tight_layout()
    fig.savefig(output_png, dpi=300)
    plt.close(fig)
    print(f"[✓] EER & ROC Curve plots saved to: {output_png}")
