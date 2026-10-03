# phase1_encoder/tests/test_loss.py
import pytest
import torch
import math
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model.loss import ArcFaceLoss

def test_arcface_forward():
    loss_fn = ArcFaceLoss(embedding_dim=256, num_classes=10, margin=0.5, scale=64.0)
    embeddings = torch.randn(16, 256)
    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
    labels = torch.randint(0, 10, (16,))
    
    loss = loss_fn(embeddings, labels)
    assert loss.dim() == 0
    assert loss.item() > 0
    assert not math.isnan(loss.item())

def test_arcface_gradient():
    loss_fn = ArcFaceLoss(embedding_dim=256, num_classes=10, margin=0.5, scale=64.0)
    raw_emb = torch.randn(8, 256, requires_grad=True)
    embeddings = torch.nn.functional.normalize(raw_emb, p=2, dim=1)
    labels = torch.randint(0, 10, (8,))
    
    loss = loss_fn(embeddings, labels)
    loss.backward()
    assert raw_emb.grad is not None
    assert not torch.isnan(raw_emb.grad).any()

def test_arcface_margin_schedule():
    loss_fn = ArcFaceLoss(embedding_dim=256, num_classes=10, margin=0.5, scale=64.0)
    assert abs(loss_fn.margin - 0.5) < 1e-6
    
    loss_fn.update_margin(0.3)
    assert abs(loss_fn.margin - 0.3) < 1e-6
    assert abs(loss_fn.cos_m - math.cos(0.3)) < 1e-6

def test_arcface_easy_margin():
    loss_fn = ArcFaceLoss(embedding_dim=256, num_classes=10, margin=0.5, scale=64.0, easy_margin=True)
    embeddings = torch.nn.functional.normalize(torch.randn(4, 256), p=2, dim=1)
    labels = torch.tensor([0, 1, 2, 3])
    loss = loss_fn(embeddings, labels)
    assert loss.item() > 0
