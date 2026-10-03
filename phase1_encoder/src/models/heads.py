# phase1_encoder/src/models/heads.py
import torch
import torch.nn as nn
import torch.nn.functional as F
import math

class ArcFaceHead(nn.Module):
    """
    ArcFace: Additive Angular Margin Loss (Deng et al., CVPR 2019).
    
    WHY ARCFACE OVER TRIPLET LOSS FOR FINGERPRINTS?
    1. Convergence: Softmax-based (classification) converges faster and more stably than 
       triplet mining which requires careful semi-hard/hard mining strategies.
    2. Angular Margin: Directly optimizes the geodesic distance on the hypersphere, 
       which matches the cosine similarity metric used at inference.
    3. Inter-class Separation: The additive margin (m) enforces a larger angular gap 
       between classes than Triplet's relative margin (alpha).
    4. SOTA: Standard in Face Recognition (MS1M, IJB-C) and Fingerprint (NIST SD27, FVC) 
       benchmarks for years. Triplet is largely deprecated for large-scale ID tasks.
    
    Args:
        in_features: Embedding dimension (256)
        num_classes: Number of training identities (subjects)
        scale (s): Feature norm scaling factor (typically 30-64). 
                   Higher s = sharper gradients, harder optimization. 64 is standard.
        margin (m): Additive angular margin in radians (0.3 - 0.5). 0.5 is standard.
        easy_margin: If True, uses simpler margin logic (less stable).
    """
    def __init__(
        self, 
        in_features: int, 
        num_classes: int, 
        scale: float = 64.0, 
        margin: float = 0.5, 
        easy_margin: bool = False
    ):
        super().__init__()
        self.in_features = in_features
        self.num_classes = num_classes
        self.s = scale
        self.m = margin
        self.easy_margin = easy_margin
        
        # Class weights (Centers on hypersphere) - initialized orthonormal
        self.weight = nn.Parameter(torch.FloatTensor(num_classes, in_features))
        nn.init.orthogonal_(self.weight)
        
        # Pre-calculated trig values for margin
        self.cos_m = math.cos(margin)
        self.sin_m = math.sin(margin)
        self.th = math.cos(math.pi - margin) # Threshold: cos(pi - m)
        self.mm = math.sin(math.pi - margin) * margin # sin(pi - m) * m

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """
        embeddings: (B, D) L2 Normalized
        labels:     (B,) Long
        Returns: Logits (B, Num_Classes) scaled by 's' for CrossEntropyLoss.
        """
        # Normalize weights (Centers)
        weight_norm = F.normalize(self.weight, p=2, dim=1)
        
        # Cosine Similarity (Cos Theta)
        cosine = F.linear(embeddings, weight_norm) # (B, C)
        
        # ---- ArcFace Margin Logic ----
        # cos(theta + m) = cos(theta)cos(m) - sin(theta)sin(m)
        sine = torch.sqrt((1.0 - torch.pow(cosine, 2)).clamp(0, 1))
        phi = cosine * self.cos_m - sine * self.sin_m # cos(theta + m)
        
        if self.easy_margin:
            # Easy margin: only apply margin if cos(theta) > 0
            phi = torch.where(cosine > 0, phi, cosine)
        else:
            # Standard ArcFace: apply margin only if theta + m < pi (cos(theta) > cos(pi - m))
            # Equivalent to: cosine > th
            phi = torch.where(cosine > self.th, phi, cosine - self.mm)
        
        # Create One-Hot Labels
        one_hot = torch.zeros_like(cosine)
        one_hot.scatter_(1, labels.view(-1, 1).long(), 1)
        
        # Output Logits: Replace target logit with margin logit
        # logits = s * (cosine + one_hot * (phi - cosine))
        logits = cosine * (1 - one_hot) + phi * one_hot
        logits *= self.s
        
        return logits
