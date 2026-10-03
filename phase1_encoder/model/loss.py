# phase1_encoder/model/loss.py
"""
ArcFace Loss (Additive Angular Margin Loss)
Reference: Deng et al., "ArcFace: Additive Angular Margin Loss for Deep Face Recognition", CVPR 2019.

Why ArcFace over Triplet for fingerprints?
- Fingerprint classes (subjects) are many (hundreds/thousands) but samples per class are few (8-12).
- Triplet mining requires O(N^2) pairs or complex mining; ArcFace uses all classes in batch via classifier.
- ArcFace provides direct angular margin on hypersphere — geometrically matches cosine similarity used at inference.
- Triplet loss converges slower and is sensitive to mining strategy; ArcFace is more stable for small-sample biometrics.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import math

class ArcFaceLoss(nn.Module):
    def __init__(
        self,
        embedding_dim: int,
        num_classes: int,
        margin: float = 0.5,      # Radians (0.5 ≈ 28.6°)
        scale: float = 64.0,
        easy_margin: bool = False,
    ):
        super().__init__()
        self.embedding_dim = embedding_dim
        self.num_classes = num_classes
        self.margin = margin
        self.scale = scale
        self.easy_margin = easy_margin
        
        # Classifier weights (on hypersphere)
        self.weight = nn.Parameter(torch.FloatTensor(num_classes, embedding_dim))
        nn.init.xavier_uniform_(self.weight)
        
        # Precompute cos/sin of margin
        self.cos_m = math.cos(margin)
        self.sin_m = math.sin(margin)
        self.th = math.cos(math.pi - margin)  # Threshold for easy_margin
        self.mm = math.sin(math.pi - margin) * margin
    
    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """
        embeddings: (B, D) — already L2 normalized
        labels: (B,) — class indices in [0, num_classes)
        """
        # Normalize weights
        weight_norm = F.normalize(self.weight, p=2, dim=1)
        
        # Cosine similarity: (B, num_classes)
        cosine = F.linear(embeddings, weight_norm)
        cosine = cosine.clamp(-1 + 1e-7, 1 - 1e-7)  # Numerical stability for acos
        
        # sin(theta) = sqrt(1 - cos^2)
        sine = torch.sqrt((1.0 - cosine.pow(2)).clamp(0, 1))
        
        # cos(theta + m) = cos*cos_m - sin*sin_m
        phi = cosine * self.cos_m - sine * self.sin_m
        
        if self.easy_margin:
            # If cos(theta) > cos(pi - m), use phi, else use cosine
            phi = torch.where(cosine > self.th, phi, cosine - self.mm)
        else:
            # Standard ArcFace: apply margin only to target class
            phi = torch.where(cosine > self.th, phi, cosine - self.mm)
        
        # One-hot labels
        one_hot = torch.zeros_like(cosine)
        one_hot.scatter_(1, labels.view(-1, 1).long(), 1)
        
        # Output logits: target class gets phi, others get cosine
        output = (one_hot * phi) + ((1.0 - one_hot) * cosine)
        output *= self.scale
        
        # Cross entropy
        loss = F.cross_entropy(output, labels)
        return loss
    
    def update_margin(self, new_margin: float):
        """Call this for margin scheduling."""
        self.margin = new_margin
        self.cos_m = math.cos(new_margin)
        self.sin_m = math.sin(new_margin)
        self.th = math.cos(math.pi - new_margin)
        self.mm = math.sin(math.pi - new_margin) * new_margin


class MarginScheduler:
    """Cosine annealing of margin from initial to final over epochs."""
    def __init__(self, loss_module: ArcFaceLoss, initial_margin: float, final_margin: float, total_epochs: int):
        self.loss = loss_module
        self.initial = initial_margin
        self.final = final_margin
        self.total = total_epochs
    
    def step(self, epoch: int):
        # Cosine annealing
        progress = epoch / self.total
        margin = self.final + (self.initial - self.final) * (1 + math.cos(math.pi * progress)) / 2
        self.loss.update_margin(margin)
        return margin
