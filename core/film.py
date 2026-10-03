# core/film.py
"""
Feature-wise Linear Modulation (FiLM) for cancelable biometrics ablation.
Matches the architectural description in the paper:
- Key k in [-1.0, 1.0]^256
- gamma_raw = Linear -> GELU -> Dropout -> Linear -> Softplus
- beta_raw  = Linear -> GELU -> Dropout -> Linear -> Tanh
- Identity initialization: gamma centered at ~1.005, beta centered at 0.0 with ||beta|| ~ 0.335
"""

import math
from typing import Tuple, List
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class FiLMGenerator(nn.Module):
    def __init__(
        self,
        input_dim: int = 256,
        hidden_dims: List[int] = [512, 512],
        output_dim: int = 256,
        dropout: float = 0.0
    ):
        super().__init__()
        self.input_dim = input_dim
        self.output_dim = output_dim
        
        # Gamma MLP (Scale)
        layers_g = []
        prev_d = input_dim
        for h_d in hidden_dims:
            layers_g.append(nn.Linear(prev_d, h_d))
            layers_g.append(nn.GELU())
            if dropout > 0.0:
                layers_g.append(nn.Dropout(dropout))
            prev_d = h_d
        layers_g.append(nn.Linear(prev_d, output_dim))
        self.gamma_net = nn.Sequential(*layers_g)
        
        # Beta MLP (Shift)
        layers_b = []
        prev_d = input_dim
        for h_d in hidden_dims:
            layers_b.append(nn.Linear(prev_d, h_d))
            layers_b.append(nn.GELU())
            if dropout > 0.0:
                layers_b.append(nn.Dropout(dropout))
            prev_d = h_d
        layers_b.append(nn.Linear(prev_d, output_dim))
        self.beta_net = nn.Sequential(*layers_b)
        
        self._init_identity_weights()

    def _init_identity_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='linear')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
        
        # Set gamma final bias such that Softplus(bias) = 1.0 -> bias = ln(e^1 - 1) = 0.54132485
        gamma_bias = math.log(math.exp(1.0) - 1.0)
        with torch.no_grad():
            self.gamma_net[-1].bias.fill_(gamma_bias)
            self.beta_net[-1].bias.fill_(0.0)
            # Scale beta weights so ||beta||_2 across 256 dimensions is ~0.335 (std ~ 0.021)
            self.beta_net[-1].weight.normal_(0.0, 0.005)

    def forward(self, k: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            k: (B, 256) continuous key in [-1.0, 1.0]
        Returns:
            gamma: (B, 256) scale > 0
            beta:  (B, 256) shift in [-1.0, 1.0]
        """
        raw_g = self.gamma_net(k)
        raw_b = self.beta_net(k)
        gamma = F.softplus(raw_g)
        beta = torch.tanh(raw_b)
        return gamma, beta


def apply_film_modulation(
    e: np.ndarray,
    gamma: np.ndarray,
    beta: np.ndarray,
    signs: np.ndarray = None
) -> np.ndarray:
    """
    Applies FiLM modulation:
    t = ( (s * gamma) * e + beta ) / || (s * gamma) * e + beta ||_2
    """
    if signs is not None:
        scaled = (signs * gamma) * e
    else:
        scaled = gamma * e
    t = scaled + beta
    norm = np.linalg.norm(t, axis=-1, keepdims=True)
    norm = np.maximum(norm, 1e-12)
    return (t / norm).astype(np.float32)


def exact_film_inversion(
    t: np.ndarray,
    gamma: np.ndarray,
    beta: np.ndarray,
    signs: np.ndarray = None
) -> Tuple[np.ndarray, float]:
    """
    Analytically inverts a FiLM template given known key (gamma, beta, signs).
    Solves for unknown positive norm scalar N = || s*gamma*e + beta ||_2 via:
    A * N^2 - 2 * B * N + (C - 1) = 0
    where A = sum (t_i / g_tilde_i)^2, B = sum (t_i * beta_i / g_tilde_i^2), C = sum (beta_i / g_tilde_i)^2.
    """
    g_tilde = (signs * gamma) if signs is not None else gamma
    
    A = np.sum((t / g_tilde) ** 2)
    B = np.sum((t * beta) / (g_tilde ** 2))
    C = np.sum((beta / g_tilde) ** 2)
    
    disc = B ** 2 - A * (C - 1.0)
    if disc < 0:
        disc = 0.0
    N = (B + np.sqrt(disc)) / A
    
    e_rec = (N * t - beta) / g_tilde
    e_rec = e_rec / np.linalg.norm(e_rec)
    return e_rec.astype(np.float32), float(N)
