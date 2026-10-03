# phase1_encoder/model/encoder.py
"""
Full Encoder = Backbone + Head.
Exportable to ONNX/TFLite/CoreML.
"""
import torch
import torch.nn as nn
from .backbone import ResNetBackbone, resnet18_backbone
from .head import EmbeddingHead

class FingerprintEncoder(nn.Module):
    def __init__(
        self,
        backbone: ResNetBackbone | None = None,
        embedding_dim: int = 256,
        dropout: float = 0.1,
        norm_embeddings: bool = True,
        in_channels: int = 1,
    ):
        super().__init__()
        if backbone is None:
            backbone = resnet18_backbone(in_channels=in_channels)
        self.backbone = backbone
        self.head = EmbeddingHead(
            in_features=backbone.out_channels,
            embedding_dim=embedding_dim,
            dropout=dropout,
            norm_embeddings=norm_embeddings,
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, 1, H, W) in range [-1, 1]
        returns: (B, embedding_dim) L2-normalized
        """
        features = self.backbone(x)
        embedding = self.head(features)
        return embedding
    
    def get_embedding_dim(self) -> int:
        return self.head.fc.out_features


def build_encoder(cfg: dict) -> FingerprintEncoder:
    backbone = resnet18_backbone(in_channels=1)
    return FingerprintEncoder(
        backbone=backbone,
        embedding_dim=cfg["model"]["embedding_dim"],
        dropout=cfg["model"]["dropout"],
        norm_embeddings=cfg["model"]["norm_embeddings"],
    )
