# phase3_fusion/tests/test_film_layer.py
import pytest
import torch
import numpy as np
import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from src.models.film import FiLMGenerator, FiLMFusion

def test_film_generator_shapes():
    gen = FiLMGenerator(input_dim=256, hidden_dims=[512], output_dim=256)
    k = torch.randn(4, 256)
    gamma, beta = gen(k)
    assert gamma.shape == (4, 256)
    assert beta.shape == (4, 256)
    assert (gamma > 0).all(), "Gamma must be positive (Softplus)"
    assert (beta >= -1).all() and (beta <= 1).all(), "Beta must be in [-1, 1] (Tanh)"

def test_film_fusion_identity_init():
    """At Init, Gamma~1, Beta~0 => t ≈ x"""
    gen = FiLMGenerator(input_dim=256, hidden_dims=[512], output_dim=256)
    fusion = FiLMFusion(gen)
    
    x = torch.randn(10, 256)
    x = torch.nn.functional.normalize(x, dim=1)
    k = torch.randn(10, 256) * 0.01
    
    t, gamma, beta = fusion(x, k)
    
    assert torch.allclose(gamma.mean(), torch.tensor(1.0), atol=0.1), f"Gamma mean {gamma.mean()}"
    assert torch.allclose(beta.mean(), torch.tensor(0.0), atol=0.1), f"Beta mean {beta.mean()}"
    
    sim = torch.nn.functional.cosine_similarity(t, x).mean()
    assert sim > 0.95, f"Identity Init Failed: Sim={sim}"

def test_film_modulation_effect():
    """Verify Gamma scales, Beta shifts"""
    gen = FiLMGenerator(input_dim=256, hidden_dims=[], output_dim=256)
    with torch.no_grad():
        gen.gamma_net[-1].weight.zero_()
        gen.gamma_net[-1].bias.fill_(10.0)
        gen.beta_net[-1].weight.zero_()
        gen.beta_net[-1].bias.fill_(0.0)
    
    fusion = FiLMFusion(gen)
    x = torch.zeros(1, 256)
    x[0, 0] = 1.0
    k = torch.ones(1, 256)
    
    t, gamma, beta = fusion(x, k)
    
    assert t[0, 0] > 0.99
    assert t[0, 1:].abs().max() < 0.01
