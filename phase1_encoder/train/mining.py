# phase1_encoder/train/mining.py
"""
Hard negative mining for ArcFace is implicit in the loss (all classes compete).
But we can also implement batch-hard triplet mining as a secondary loss or for evaluation.
Here we provide a utility for semi-hard triplet mining within a batch.
"""
import torch
import torch.nn.functional as F

def batch_hard_triplet_loss(
    embeddings: torch.Tensor,
    labels: torch.Tensor,
    margin: float = 0.3,
    squared: bool = False,
) -> torch.Tensor:
    """
    Batch-hard triplet loss (Hermans et al., 2017).
    For each anchor, hardest positive and hardest negative in batch.
    """
    # Pairwise distances
    if squared:
        dist = torch.cdist(embeddings, embeddings, p=2).pow(2)
    else:
        dist = torch.cdist(embeddings, embeddings, p=2)
    
    # Mask for positives/negatives
    labels_eq = labels.unsqueeze(1) == labels.unsqueeze(0)  # (B, B)
    mask_pos = labels_eq & ~torch.eye(labels.size(0), dtype=torch.bool, device=labels.device)
    mask_neg = ~labels_eq
    
    # Hardest positive: max distance among positives
    hardest_pos_dist = torch.where(mask_pos, dist, torch.tensor(-1.0, device=dist.device)).max(dim=1)[0]
    
    # Hardest negative: min distance among negatives
    hardest_neg_dist = torch.where(mask_neg, dist, torch.tensor(float('inf'), device=dist.device)).min(dim=1)[0]
    
    # Triplet loss
    loss = F.relu(hardest_pos_dist - hardest_neg_dist + margin)
    return loss.mean()


def semi_hard_triplet_mask(
    embeddings: torch.Tensor,
    labels: torch.Tensor,
    margin: float = 0.3,
) -> torch.Tensor:
    """
    Returns boolean mask of semi-hard triplets: pos_dist < neg_dist < pos_dist + margin
    Used for mining (not a loss itself).
    """
    dist = torch.cdist(embeddings, embeddings, p=2)
    labels_eq = labels.unsqueeze(1) == labels.unsqueeze(0)
    mask_pos = labels_eq & ~torch.eye(labels.size(0), dtype=torch.bool, device=labels.device)
    mask_neg = ~labels_eq
    
    pos_dist = dist.masked_fill(~mask_pos, -1.0).max(dim=1, keepdim=True)[0]  # (B, 1)
    neg_dist = dist.masked_fill(~mask_neg, float('inf'))
    
    # Semi-hard: neg_dist > pos_dist AND neg_dist < pos_dist + margin
    semi_hard = (neg_dist > pos_dist) & (neg_dist < pos_dist + margin)
    return semi_hard
