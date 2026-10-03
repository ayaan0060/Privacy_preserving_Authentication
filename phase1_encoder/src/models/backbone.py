# phase1_encoder/src/models/backbone.py
import torch
import torch.nn as nn
import torchvision.models as models
from typing import Optional

class FingerprintEncoder(nn.Module):
    """
    ResNet18 Backbone -> Global Pool -> FC(256) -> L2 Norm.
    Input: (B, 1, 96, 96) or (B, 1, 224, 224)
    Output: (B, 256) L2-normalized embeddings.
    """
    def __init__(
        self, 
        embedding_dim: int = 256, 
        pretrained: bool = False, 
        dropout: float = 0.3,
        input_channels: int = 1
    ):
        super().__init__()
        # Load ResNet18
        backbone = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None)
        
        # Modify first conv for grayscale (1 channel)
        if input_channels != 3:
            original_conv = backbone.conv1
            backbone.conv1 = nn.Conv2d(
                input_channels, 64, kernel_size=7, stride=2, padding=3, bias=False
            )
            # Initialize by averaging RGB weights if pretrained, else Kaiming
            if pretrained:
                with torch.no_grad():
                    backbone.conv1.weight[:] = original_conv.weight.mean(dim=1, keepdim=True)
        
        # Remove final FC and AvgPool (we keep AdaptiveAvgPool2d)
        self.backbone = nn.Sequential(*list(backbone.children())[:-1]) # Output (B, 512, 1, 1) for 224x224
        
        # Embedding Head
        self.embedding_head = nn.Sequential(
            nn.Flatten(),               # (B, 512)
            nn.BatchNorm1d(512),
            nn.Dropout(dropout),
            nn.Linear(512, embedding_dim),
            nn.BatchNorm1d(embedding_dim) # No ReLU here! ArcFace expects linear features for angular margin.
        )
        
        self._init_weights()

    def _init_weights(self):
        for m in self.embedding_head.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='linear')
                if m.bias is not None: nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm1d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, 1, H, W)
        features = self.backbone(x)        # (B, 512, 1, 1)
        embedding = self.embedding_head(features) # (B, 256)
        
        # L2 Normalization (Critical for ArcFace / Cosine Similarity)
        embedding = nn.functional.normalize(embedding, p=2, dim=1)
        return embedding
