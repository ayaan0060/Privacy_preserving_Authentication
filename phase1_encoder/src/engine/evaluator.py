# phase1_encoder/src/engine/evaluator.py
import torch
import numpy as np
from sklearn.metrics import roc_curve, auc
from scipy.optimize import brentq
from scipy.interpolate import interp1d
from typing import Tuple, List, Dict
import logging
from tqdm import tqdm

log = logging.getLogger(__name__)

def compute_eer_and_roc(scores: np.ndarray, labels: np.ndarray) -> Dict[str, float]:
    """
    scores: Similarity scores (cosine similarity, higher=more similar)
    labels: 1 for genuine, 0 for impostor
    """
    fpr, tpr, thresholds = roc_curve(labels, scores)
    roc_auc = auc(fpr, tpr)
    
    # EER: FPR = 1 - TPR (FNR)
    # Interpolate to find threshold where FPR = FNR
    try:
        eer = brentq(lambda x: 1. - x - interp1d(fpr, tpr)(x), 0., 1.)
        eer_thresh = interp1d(fpr, thresholds)(eer)
    except ValueError:
        eer = 1.0
        eer_thresh = 0.0
        
    # TAR @ FAR=0.1%, 1%
    tar_at_far = {}
    for far_target in [0.001, 0.01]:
        if fpr[-1] < far_target:
            tar_at_far[f'TAR@FAR={far_target:.3f}'] = 0.0
        else:
            tar_at_far[f'TAR@FAR={far_target:.3f}'] = float(interp1d(fpr, tpr)(far_target))
            
    return {
        'EER': float(eer),
        'EER_Threshold': float(eer_thresh),
        'AUC': float(roc_auc),
        **tar_at_far,
        'FPR': fpr, 'TPR': tpr, 'Thresholds': thresholds # For plotting
    }

def compute_rank1_accuracy(
    probe_embeddings: np.ndarray, probe_labels: np.ndarray,
    gallery_embeddings: np.ndarray, gallery_labels: np.ndarray
) -> float:
    """
    Closed-set Identification (Rank-1).
    Assumes 1 gallery template per subject (standard FVC protocol).
    """
    # Cosine Similarity (Embeddings are L2 normalized)
    sim_matrix = probe_embeddings @ gallery_embeddings.T # (N_probe, N_gallery)
    
    # Argmax similarity
    pred_indices = np.argmax(sim_matrix, axis=1)
    pred_labels = gallery_labels[pred_indices]
    
    correct = np.sum(pred_labels == probe_labels)
    return correct / len(probe_labels)

def run_verification_eval(
    model: torch.nn.Module, 
    probe_loader: torch.utils.data.DataLoader, 
    gallery_loader: torch.utils.data.DataLoader,
    device: torch.device
) -> Dict:
    """
    Standard Verification Protocol (1:1):
    - Gallery: 1 template per subject (e.g., first impression)
    - Probe: Remaining impressions
    - Compare every probe against its genuine gallery + K impostors (or all)
    """
    model.eval()
    model.to(device)
    
    # Extract Gallery
    gallery_embs, gallery_lbls = [], []
    with torch.no_grad():
        for x, y in tqdm(gallery_loader, desc="Gallery"):
            gallery_embs.append(model(x.to(device)).cpu().numpy())
            gallery_lbls.append(y.numpy())
    gallery_embs = np.vstack(gallery_embs)
    gallery_lbls = np.hstack(gallery_lbls)
    
    # Extract Probe & Compute Scores
    genuine_scores, impostor_scores = [], []
    
    # Build index for fast genuine lookup
    gallery_idx_by_label = {lbl: i for i, lbl in enumerate(gallery_lbls)}
    
    with torch.no_grad():
        for x, y in tqdm(probe_loader, desc="Probe"):
            probe_embs = model(x.to(device)).cpu().numpy() # (B, 256)
            
            # Vectorized similarity against ALL gallery
            sims = probe_embs @ gallery_embs.T # (B, G)
            
            for i, lbl in enumerate(y.numpy()):
                # Genuine
                if lbl in gallery_idx_by_label:
                    g_idx = gallery_idx_by_label[lbl]
                    genuine_scores.append(sims[i, g_idx])
                
                # Impostors: Sample random 100 impostors per probe for speed (or all if small)
                # For full FVC eval, use ALL impostors.
                imp_mask = gallery_lbls != lbl
                impostor_scores.extend(sims[i, imp_mask].tolist())
    
    # Balance arrays for sklearn
    labels = np.concatenate([np.ones(len(genuine_scores)), np.zeros(len(impostor_scores))])
    scores = np.concatenate([genuine_scores, impostor_scores])
    
    metrics = compute_eer_and_roc(scores, labels)
    metrics['num_genuine'] = len(genuine_scores)
    metrics['num_impostor'] = len(impostor_scores)
    
    return metrics

def run_identification_eval(
    model: torch.nn.Module,
    probe_loader: torch.utils.data.DataLoader,
    gallery_loader: torch.utils.data.DataLoader,
    device: torch.device
) -> float:
    """Rank-1 Identification Accuracy."""
    model.eval()
    model.to(device)
    
    gallery_embs, gallery_lbls = [], []
    probe_embs, probe_lbls = [], []
    
    with torch.no_grad():
        for x, y in tqdm(gallery_loader, desc="Gallery (ID)"):
            gallery_embs.append(model(x.to(device)).cpu().numpy())
            gallery_lbls.append(y.numpy())
        for x, y in tqdm(probe_loader, desc="Probe (ID)"):
            probe_embs.append(model(x.to(device)).cpu().numpy())
            probe_lbls.append(y.numpy())
            
    gallery_embs = np.vstack(gallery_embs)
    gallery_lbls = np.hstack(gallery_lbls)
    probe_embs = np.vstack(probe_embs)
    probe_lbls = np.hstack(probe_lbls)
    
    rank1 = compute_rank1_accuracy(probe_embs, probe_lbls, gallery_embs, gallery_lbls)
    return rank1
