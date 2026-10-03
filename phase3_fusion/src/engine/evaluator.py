# phase3_fusion/src/engine/evaluator.py
import torch
import torch.nn.functional as F
import numpy as np
from sklearn.metrics import roc_curve, auc
from scipy.optimize import brentq
from scipy.interpolate import interp1d
from tqdm import tqdm
from typing import Dict, List, Tuple
import logging

log = logging.getLogger(__name__)

@torch.no_grad()
def evaluate_verification(
    trainer: torch.nn.Module, 
    gallery_loader: torch.utils.data.DataLoader, 
    probe_loader: torch.utils.data.DataLoader,
    device: torch.device
) -> Dict:
    """
    Standard 1:1 Verification.
    Gallery: 1 template per user (Fixed Key Version).
    Probe:  Other impressions (Same Key Version).
    """
    trainer.eval()
    trainer.to(device)
    
    gallery_templates = {}
    gallery_labels = {}
    
    for x, k, labels, uids, versions in tqdm(gallery_loader, desc="Building Gallery"):
        x, k = x.to(device), k.to(device)
        t = trainer(x, k)
        t_np = t.cpu().numpy()
        
        for i, uid in enumerate(uids):
            if uid not in gallery_templates:
                gallery_templates[uid] = t_np[i]
                gallery_labels[uid] = labels[i].item()
    
    gallery_uids = list(gallery_templates.keys())
    gallery_embs = np.stack([gallery_templates[u] for u in gallery_uids])
    gallery_lbls = np.array([gallery_labels[u] for u in gallery_uids])
    
    genuine_scores, impostor_scores = [], []
    
    for x, k, labels, uids, versions in tqdm(probe_loader, desc="Probing"):
        x, k = x.to(device), k.to(device)
        t_probe = trainer(x, k).cpu().numpy()
        
        sims = t_probe @ gallery_embs.T
        
        for i, uid in enumerate(uids):
            if uid in gallery_templates:
                g_idx = gallery_uids.index(uid)
                genuine_scores.append(sims[i, g_idx])
            
            imp_mask = gallery_lbls != labels[i].item()
            impostor_scores.extend(sims[i, imp_mask].tolist())
    
    y_true = np.concatenate([np.ones(len(genuine_scores)), np.zeros(len(impostor_scores))])
    y_score = np.concatenate([genuine_scores, impostor_scores])
    
    fpr, tpr, thresh = roc_curve(y_true, y_score)
    roc_auc = auc(fpr, tpr)
    
    try:
        eer = brentq(lambda x: 1. - x - interp1d(fpr, tpr)(x), 0., 1.)
        eer_th = float(interp1d(fpr, thresh)(eer))
    except Exception:
        eer, eer_th = 1.0, 0.0
    
    return {
        'EER': float(eer), 'EER_Threshold': eer_th, 'AUC': float(roc_auc),
        'FPR': fpr, 'TPR': tpr, 'Thresholds': thresh,
        'Genuine_Count': len(genuine_scores), 'Impostor_Count': len(impostor_scores)
    }

@torch.no_grad()
def evaluate_unlinkability(
    trainer: torch.nn.Module,
    data_loader: torch.utils.data.DataLoader,
    device: torch.device,
    num_trials: int = 1000
) -> Dict:
    """
    CRITICAL TEST: Cancelability / Unlinkability.
    For SAME user (same x), different key versions (k1 vs k2):
    Template t1 = FiLM(x, k1), t2 = FiLM(x, k2).
    Measure Cosine Similarity. Should be ~0 (Random).
    """
    trainer.eval()
    trainer.to(device)
    
    user_embeddings = {}
    for x, k, labels, uids, versions in data_loader:
        for i, uid in enumerate(uids):
            if uid not in user_embeddings:
                user_embeddings[uid] = []
            user_embeddings[uid].append(x[i].numpy())
    
    similarities = []
    uids = list(user_embeddings.keys())
    
    for _ in range(num_trials):
        uid = np.random.choice(uids)
        if len(user_embeddings[uid]) < 1: continue
        
        x_np = np.random.choice(user_embeddings[uid])
        x_tensor = torch.from_numpy(x_np).unsqueeze(0).to(device)
        
        k1 = torch.rand(1, 256, device=device) * 2 - 1
        k2 = torch.rand(1, 256, device=device) * 2 - 1
        
        t1 = trainer.fusion(x_tensor, k1)[0]
        t2 = trainer.fusion(x_tensor, k2)[0]
        
        sim = F.cosine_similarity(t1, t2).item()
        similarities.append(sim)
    
    sims = np.array(similarities)
    mean_sim = sims.mean()
    std_sim = sims.std()
    
    log.info(f"Unlinkability: Mean CosSim={mean_sim:.6f}, Std={std_sim:.6f} (Theory Std=0.0625)")
    
    return {
        'mean_cosine_similarity': float(mean_sim),
        'std_cosine_similarity': float(std_sim),
        'theoretical_std': 1.0 / np.sqrt(256),
        'max_abs_sim': float(np.max(np.abs(sims)))
    }
