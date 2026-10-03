# phase1_encoder/model/head.py
"""
Embedding head: Global pooling -> FC -> L2 norm.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

class EmbeddingHead(nn.Module):
    def __init__(
        self,
        in_features: int,
        embedding_dim: int = 256,
        dropout: float = 0.1,
        norm_embeddings: bool = True,
    ):
        super().__init__()
        self.norm_embeddings = norm_embeddings
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.dropout = nn.Dropout(dropout) if dropout > 0 else nn.Identity()
        self.fc = nn.Linear(in_features, embedding_dim, bias=False)
        self.bn = nn.BatchNorm1d(embedding_dim)
        
        # Init
        nn.init.kaiming_normal_(self.fc.weight, mode="fan_out", nonlinearity="relu")
        nn.init.constant_(self.bn.weight, 1)
        nn.init.constant_(self.bn.bias, 0)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool(x).flatten(1)  # (B, C)
        x = self.dropout(x)
        x = self.fc(x)
        x = self.bn(x)
        if self.norm_embeddings:
            x = F.normalize(x, p=2, dim=1)
        return x
