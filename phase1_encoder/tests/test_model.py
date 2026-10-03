# phase1_encoder/tests/test_model.py
import pytest
import torch
import torch.nn as nn
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model.backbone import resnet18_backbone, BasicBlock
from model.head import EmbeddingHead
from model.encoder import FingerprintEncoder, build_encoder
from config import load_config

def test_backbone_forward():
    backbone = resnet18_backbone(in_channels=1)
    x = torch.randn(2, 1, 96, 96)
    out = backbone(x)
    assert out.shape == (2, 512, 12, 12)  # 96 / 8 = 12

def test_backbone_gradient_flow():
    backbone = resnet18_backbone(in_channels=1)
    x = torch.randn(1, 1, 96, 96, requires_grad=True)
    out = backbone(x)
    loss = out.sum()
    loss.backward()
    assert x.grad is not None
    assert not torch.isnan(x.grad).any()

def test_head_forward():
    head = EmbeddingHead(in_features=512, embedding_dim=256, norm_embeddings=True)
    x = torch.randn(4, 512, 12, 12)
    out = head(x)
    assert out.shape == (4, 256)
    # Check L2 norm
    norms = torch.norm(out, p=2, dim=1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)

def test_head_no_norm():
    head = EmbeddingHead(in_features=512, embedding_dim=256, norm_embeddings=False)
    x = torch.randn(4, 512, 12, 12)
    out = head(x)
    assert out.shape == (4, 256)
    norms = torch.norm(out, p=2, dim=1)
    assert not torch.allclose(norms, torch.ones_like(norms))

def test_encoder_end_to_end():
    cfg = load_config("config.yaml")
    encoder = build_encoder(cfg)
    x = torch.randn(3, 1, 96, 96)
    out = encoder(x)
    assert out.shape == (3, 256)
    norms = torch.norm(out, p=2, dim=1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)

def test_encoder_deterministic():
    cfg = load_config("config.yaml")
    encoder = build_encoder(cfg)
    encoder.eval()
    x = torch.randn(1, 1, 96, 96)
    with torch.no_grad():
        out1 = encoder(x)
        out2 = encoder(x)
    assert torch.allclose(out1, out2)
