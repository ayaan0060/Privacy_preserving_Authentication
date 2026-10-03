# phase3_fusion/src/models/film.py
"""
FiLM (Feature-wise Linear Modulation) for Cancelable Biometrics.
Reference: Perez et al., "FiLM: Visual Reasoning with a General Conditioning Layer", AAAS 2018.

Architecture:
  k (256) -> MLP_gamma -> gamma (256)  (Scale)
  k (256) -> MLP_beta  -> beta  (256)  (Shift)
  
  Template t = gamma * x + beta
  t = L2Norm(t)
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Tuple
import math

class FiLMGenerator(nn.Module):
    """
    Takes key vector k (B, 256) -> predicts gamma (B, 256), beta (B, 256).
    """
    def __init__(
        self, 
        input_dim: int = 256,
        hidden_dims: List[int] = [512, 512],
        output_dim: int = 256,
        activation: str = "gelu",
        dropout: float = 0.1
    ):
        super().__init__()
        self.input_dim = input_dim
        self.output_dim = output_dim
        
        act_fn = {"relu": nn.ReLU, "gelu": nn.GELU, "silu": nn.SiLU}[activation]
        
        # --- Gamma MLP (Scale) ---
        layers_g = []
        prev_dim = input_dim
        for h_dim in hidden_dims:
            layers_g.append(nn.Linear(prev_dim, h_dim))
            layers_g.append(act_fn())
            layers_g.append(nn.Dropout(dropout))
            prev_dim = h_dim
        layers_g.append(nn.Linear(prev_dim, output_dim))
        self.gamma_net = nn.Sequential(*layers_g)
        
        # --- Beta MLP (Shift) ---
        layers_b = []
        prev_dim = input_dim
        for h_dim in hidden_dims:
            layers_b.append(nn.Linear(prev_dim, h_dim))
            layers_b.append(act_fn())
            layers_b.append(nn.Dropout(dropout))
            prev_dim = h_dim
        layers_b.append(nn.Linear(prev_dim, output_dim))
        self.beta_net = nn.Sequential(*layers_b)
        
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='linear')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
        
        # Identity Initialization for Fusion Stability
        gamma_bias_val = math.log(math.exp(1.0) - 1.0)
        with torch.no_grad():
            self.gamma_net[-1].bias.fill_(gamma_bias_val)
            self.beta_net[-1].bias.fill_(0.0)
            self.beta_net[-1].weight.normal_(0.0, 0.005)

    def forward(self, k: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            k: (B, 256) Key Vector (float32, range ~[-1, 1])
        Returns:
            gamma: (B, 256) > 0 (Softplus)
            beta:  (B, 256) ∈ [-1, 1] (Tanh)
        """
        raw_gamma = self.gamma_net(k)
        raw_beta = self.beta_net(k)
        
        gamma = F.softplus(raw_gamma)  # > 0
        beta = torch.tanh(raw_beta)    # [-1, 1]
        
        return gamma, beta


class FiLMFusion(nn.Module):
    """
    Applies FiLM Modulation: t = gamma * x + beta -> L2Norm.
    """
    def __init__(self, film_generator: FiLMGenerator):
        super().__init__()
        self.generator = film_generator

    def forward(self, x: torch.Tensor, k: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (B, 256) L2-Normalized Embedding from Encoder
            k: (B, 256) Key Vector
        Returns:
            t: (B, 256) L2-Normalized Cancelable Template
            gamma: (B, 256)
            beta:  (B, 256)
        """
        gamma, beta = self.generator(k)
        t = gamma * x + beta
        t = F.normalize(t, p=2, dim=1)
        return t, gamma, beta

    def get_regularization_loss(self, gamma: torch.Tensor, beta: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Encourages Identity Mapping (gamma=1, beta=0) to prevent over-modulation
        and preserve verification accuracy.
        """
        loss_gamma = F.mse_loss(gamma, torch.ones_like(gamma))
        loss_beta = F.mse_loss(beta, torch.zeros_like(beta))
        return loss_gamma, loss_beta
