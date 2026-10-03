# phase1_encoder/src/models/loss.py
import torch
import torch.nn as nn
import torch.nn.functional as F

class ArcFaceLoss(nn.Module):
    """Wrapper combining ArcFace Head + CrossEntropy."""
    def __init__(self, head: nn.Module):
        super().__init__()
        self.head = head
        self.ce = nn.CrossEntropyLoss(label_smoothing=0.1) # Label smoothing helps generalization

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        logits = self.head(embeddings, labels)
        loss = self.ce(logits, labels)
        return loss


class CenterLoss(nn.Module):
    """
    Center Loss (Wen et al., ECCV 2016) - Optional Regularizer.
    Pulls embeddings of same class closer to their learned center.
    Helps intra-class compactness, complementary to ArcFace's inter-class separation.
    """
    def __init__(self, num_classes: int, feat_dim: int, lambda_c: float = 0.01):
        super().__init__()
        self.num_classes = num_classes
        self.feat_dim = feat_dim
        self.lambda_c = lambda_c
        self.centers = nn.Parameter(torch.randn(num_classes, feat_dim))

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        batch_size = embeddings.size(0)
        centers_batch = self.centers.index_select(0, labels) # (B, D)
        
        # MSE between embeddings and their centers
        loss = F.mse_loss(embeddings, centers_batch, reduction='sum') / (2.0 * batch_size)
        return self.lambda_c * loss
