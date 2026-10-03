# phase1_encoder/eval/metrics.py
"""
Verification & Identification metrics.
- EER (Equal Error Rate)
- ROC curve (FAR vs FRR)
- DET curve (FRR vs FAR, normal deviate scale)
- Rank-1 Identification Accuracy
"""
import numpy as np
import torch
from sklearn.metrics import roc_curve, auc
from scipy.optimize import brentq
from scipy.interpolate import interp1d
from typing import Dict, Tuple, List, Optional


def cosine_similarity_matrix(embeddings: torch.Tensor) -> torch.Tensor:
    """Compute pairwise cosine similarity (already L2 normalized)."""
    return embeddings @ embeddings.T  # (N, N)


def get_genuine_impostor_scores(
    embeddings: torch.Tensor,
    labels: torch.Tensor,
    max_pairs: int = 100000,
    rng: np.random.Generator | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Sample genuine and impostor pairs for verification metrics.
    Returns (genuine_scores, impostor_scores) as numpy arrays.
    """
    if rng is None:
        rng = np.random.default_rng(42)
    
    N = embeddings.size(0)
    sim_matrix = cosine_similarity_matrix(embeddings).cpu().numpy()
    labels_np = labels.cpu().numpy()
    
    # Get indices per subject
    unique_labels = np.unique(labels_np)
    label_to_indices = {lbl: np.where(labels_np == lbl)[0] for lbl in unique_labels}
    
    genuine_scores = []
    impostor_scores = []
    
    # Genuine pairs
    for lbl, idxs in label_to_indices.items():
        if len(idxs) < 2:
            continue
        # All pairs within subject
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                genuine_scores.append(sim_matrix[idxs[i], idxs[j]])
    
    genuine_scores = np.array(genuine_scores)
    
    # Impostor pairs — sample to limit
    if max_pairs and len(unique_labels) > 1:
        # Sample cross-subject pairs
        n_impostor_target = min(max_pairs, len(genuine_scores) * 10)
        n_samples = 0
        while n_samples < n_impostor_target:
            lbl1, lbl2 = rng.choice(unique_labels, size=2, replace=False)
            i = rng.choice(label_to_indices[lbl1])
            j = rng.choice(label_to_indices[lbl2])
            impostor_scores.append(sim_matrix[i, j])
            n_samples += 1
    
    impostor_scores = np.array(impostor_scores)
    
    return genuine_scores, impostor_scores


def compute_eer(genuine: np.ndarray, impostor: np.ndarray) -> Tuple[float, float]:
    """
    Compute EER and threshold.
    Returns (EER, threshold)
    """
    # Labels: 1 for genuine, 0 for impostor
    y_true = np.concatenate([np.ones_like(genuine), np.zeros_like(impostor)])
    y_score = np.concatenate([genuine, impostor])
    
    fpr, tpr, thresholds = roc_curve(y_true, y_score)
    fnr = 1 - tpr
    
    # Find threshold where FPR == FNR
    # Interpolate
    interp_fnr = interp1d(fpr, fnr, kind='linear', bounds_error=False, fill_value=(fnr[0], fnr[-1]))
    
    def diff(x):
        return interp_fnr(x) - x
    
    try:
        eer_thresh = brentq(diff, 0.0, 1.0)
        eer = interp_fnr(eer_thresh)
    except ValueError:
        # Fallback: closest point
        idx = np.argmin(np.abs(fnr - fpr))
        eer = (fnr[idx] + fpr[idx]) / 2
        eer_thresh = thresholds[idx]
    
    return float(eer), float(eer_thresh)


def compute_verification_metrics(
    embeddings: torch.Tensor,
    labels: torch.Tensor,
    max_pairs: int = 50000,
) -> Dict[str, float]:
    """Full verification metric suite."""
    genuine, impostor = get_genuine_impostor_scores(embeddings, labels, max_pairs=max_pairs)
    
    eer, thresh = compute_eer(genuine, impostor)
    
    # AUC
    y_true = np.concatenate([np.ones_like(genuine), np.zeros_like(impostor)])
    y_score = np.concatenate([genuine, impostor])
    fpr, tpr, _ = roc_curve(y_true, y_score)
    roc_auc = auc(fpr, tpr)
    
    # TAR@FAR=0.01, 0.001, 0.0001
    tar_at_far = {}
    for target_far in [0.01, 0.001, 0.0001]:
        if len(fpr) > 1 and fpr[-1] >= target_far:
            tar = np.interp(target_far, fpr, tpr)
        else:
            tar = 0.0
        tar_at_far[f"TAR@FAR={target_far}"] = float(tar)
    
    return {
        "eer": eer,
        "threshold": thresh,
        "auc": float(roc_auc),
        "num_genuine": len(genuine),
        "num_impostor": len(impostor),
        **tar_at_far,
    }


def compute_identification_rank1(
    embeddings: torch.Tensor,
    labels: torch.Tensor,
    gallery_ratio: float = 0.5,
    rng: np.random.Generator | None = None,
) -> float:
    """
    Rank-1 identification accuracy.
    Split each subject's samples into gallery (first gallery_ratio) and probe (rest).
    For each probe, find nearest gallery embedding — correct if same subject.
    """
    if rng is None:
        rng = np.random.default_rng(42)
    
    labels_np = labels.cpu().numpy()
    unique_labels = np.unique(labels_np)
    
    gallery_embs = []
    gallery_lbls = []
    probe_embs = []
    probe_lbls = []
    
    for lbl in unique_labels:
        idxs = np.where(labels_np == lbl)[0]
        rng.shuffle(idxs)
        n_gallery = max(1, int(len(idxs) * gallery_ratio))
        gal_idx = idxs[:n_gallery]
        prb_idx = idxs[n_gallery:]
        
        if len(prb_idx) == 0:
            continue
        
        gallery_embs.append(embeddings[gal_idx])
        gallery_lbls.extend([lbl] * len(gal_idx))
        probe_embs.append(embeddings[prb_idx])
        probe_lbls.extend([lbl] * len(prb_idx))
    
    if not probe_embs:
        return 0.0
    
    gallery_embs = torch.cat(gallery_embs, dim=0)  # (G, D)
    probe_embs = torch.cat(probe_embs, dim=0)      # (P, D)
    gallery_lbls = np.array(gallery_lbls)
    probe_lbls = np.array(probe_lbls)
    
    # Cosine similarity (probe x gallery)
    sim = probe_embs @ gallery_embs.T  # (P, G)
    top1_idx = sim.argmax(dim=1).cpu().numpy()
    top1_lbl = gallery_lbls[top1_idx]
    
    rank1 = (top1_lbl == probe_lbls).mean()
    return float(rank1)


def plot_roc_det(
    genuine: np.ndarray,
    impostor: np.ndarray,
    save_path: str,
    title: str = "ROC / DET Curves",
):
    """Generate and save ROC and DET plots."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.stats import norm
    
    y_true = np.concatenate([np.ones_like(genuine), np.zeros_like(impostor)])
    y_score = np.concatenate([genuine, impostor])
    
    fpr, tpr, _ = roc_curve(y_true, y_score)
    fnr = 1 - tpr
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # ROC
    axes[0].plot(fpr, tpr, label=f"AUC = {auc(fpr, tpr):.4f}")
    axes[0].plot([0, 1], [0, 1], 'k--', alpha=0.3)
    axes[0].set_xscale('log')
    axes[0].set_xlabel("FAR (False Accept Rate)")
    axes[0].set_ylabel("TAR (True Accept Rate) = 1 - FRR")
    axes[0].set_title("ROC Curve")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # DET (normal deviate scale)
    axes[1].plot(norm.ppf(fpr.clip(1e-6, 1-1e-6)), norm.ppf(fnr.clip(1e-6, 1-1e-6)))
    axes[1].set_xlabel("FAR (Normal Deviate Scale)")
    axes[1].set_ylabel("FRR (Normal Deviate Scale)")
    axes[1].set_title("DET Curve")
    axes[1].grid(True, alpha=0.3)
    
    # Add EER point
    eer, thresh = compute_eer(genuine, impostor)
    axes[0].plot(eer, 1-eer, 'ro', label=f"EER = {eer:.4f}")
    axes[0].legend()
    
    plt.suptitle(title)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"[PLOT] Saved ROC/DET to {save_path}")
