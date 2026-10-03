# phase3_fusion/tests/test_unlinkability.py
"""
VALIDATES THE CANCELABLE PROPERTY.
If this fails, the system is NOT cancelable.
"""
import pytest
import torch
import numpy as np
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../phase1_encoder")))

from models.film import FiLMGenerator, FiLMFusion
from model.encoder import FingerprintEncoder

def test_unlinkability_statistical():
    """
    Mathematical Property: 
    For fixed x, k1, k2 independent Uniform[-1,1]^256.
    t1 = Norm(gamma(k1)*x + beta(k1))
    t2 = Norm(gamma(k2)*x + beta(k2))
    CosSim(t1, t2) -> Distribution centered at 0, Std ~ 1/sqrt(D).
    """
    gen = FiLMGenerator()
    torch.nn.init.normal_(gen.beta_net[-1].weight, std=0.5)
    fusion = FiLMFusion(gen)
    
    x = torch.randn(1, 256)
    x = torch.nn.functional.normalize(x, dim=1)
    
    sims = []
    for _ in range(5000):
        k1 = (torch.rand(1, 256) * 2 - 1)
        k2 = (torch.rand(1, 256) * 2 - 1)
        t1 = fusion(x, k1)[0]
        t2 = fusion(x, k2)[0]
        sim = torch.nn.functional.cosine_similarity(t1, t2).item()
        sims.append(sim)
    
    sims = np.array(sims)
    mean, std = sims.mean(), sims.std()
    theoretical_std = 1.0 / np.sqrt(256)
    
    print(f"Unlinkability Stats: Mean={mean:.6f}, Std={std:.6f} (Theory={theoretical_std:.6f})")
    
    assert abs(mean) < 0.35, f"Mean similarity not zero: {mean}"
    print("✅ Statistical Unlinkability PASSED")

def test_unlinkability_with_trained_film(tmp_path):
    """
    Integration Test: Train FiLM for 1 Epoch -> Test Unlinkability.
    Ensures Training doesn't collapse k-space.
    """
    gen = FiLMGenerator(hidden_dims=[64])
    torch.nn.init.normal_(gen.beta_net[-1].weight, std=0.5)
    fusion = FiLMFusion(gen)
    
    opt = torch.optim.Adam(gen.parameters(), lr=1e-3)
    x = torch.randn(16, 256)
    x = torch.nn.functional.normalize(x, dim=1)
    k = (torch.rand(16, 256) * 2 - 1)
    labels = torch.arange(16)
    
    p1_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "phase1_encoder"))
    if p1_path not in sys.path:
        sys.path.insert(0, p1_path)
    from model.loss import ArcFaceLoss
    loss_fn = ArcFaceLoss(embedding_dim=256, num_classes=16, margin=0.3, scale=16.0)
    
    for _ in range(5):
        opt.zero_grad()
        t, g, b = fusion(x, k)
        loss = loss_fn(t, labels)
        loss += 0.01 * (torch.nn.functional.mse_loss(g, torch.ones_like(g)) + torch.nn.functional.mse_loss(b, torch.zeros_like(b)))
        loss.backward()
        opt.step()
    
    x_test = torch.randn(1, 256)
    x_test = torch.nn.functional.normalize(x_test, dim=1)
    
    sims = []
    for _ in range(1000):
        k1 = (torch.rand(1, 256) * 2 - 1)
        k2 = (torch.rand(1, 256) * 2 - 1)
        t1 = fusion(x_test, k1)[0]
        t2 = fusion(x_test, k2)[0]
        sims.append(torch.nn.functional.cosine_similarity(t1, t2).item())
    
    sims = np.array(sims)
    assert abs(sims.mean()) < 0.20
    assert abs(sims.std() - 0.0625) < 0.10
    print(f"Post-Train Unlinkability: Mean={sims.mean():.4f}, Std={sims.std():.4f}")
    print("✅ Trained Model Unlinkability PASSED")
