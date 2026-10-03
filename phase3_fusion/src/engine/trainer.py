# phase3_fusion/src/engine/trainer.py
import os
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F
import pytorch_lightning as pl
from torch.optim.lr_scheduler import CosineAnnealingLR
from typing import Dict, Any, Optional

# Import Models
from ..models.film import FiLMGenerator, FiLMFusion
from ..models.combined import EncoderWrapper

# Ensure Phase 1 src is on sys.path
phase1_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../phase1_encoder/src"))
if phase1_src not in sys.path:
    sys.path.insert(0, phase1_src)

from models.heads import ArcFaceHead
from models.loss import ArcFaceLoss

class FusionTrainer(pl.LightningModule):
    def __init__(self, config: Dict[str, Any], num_train_classes: int, encoder_ckpt_path: str, phase1_config: dict):
        super().__init__()
        self.save_hyperparameters(ignore=['encoder_ckpt_path'])
        self.config = config
        self.phase1_config = phase1_config
        
        # 1. Encoder (Frozen or Trainable)
        self.encoder = EncoderWrapper(encoder_ckpt_path, phase1_config)
        embed_dim = phase1_config['model']['embedding_dim']
        
        # 2. FiLM Generator
        film_cfg = config['film']
        self.film_generator = FiLMGenerator(
            input_dim=embed_dim,
            hidden_dims=film_cfg['generator_hidden'],
            output_dim=embed_dim,
            activation=film_cfg['activation'],
            dropout=film_cfg['dropout']
        )
        
        # 3. Fusion Layer
        self.fusion = FiLMFusion(self.film_generator)
        
        # 4. ArcFace Head (Operates on Fused Template 't')
        self.arcface_head = ArcFaceHead(
            in_features=embed_dim,
            num_classes=num_train_classes,
            scale=phase1_config['arcface']['scale'],
            margin=phase1_config['arcface']['margin'],
            easy_margin=phase1_config['arcface']['easy_margin']
        )
        self.arcface_loss = ArcFaceLoss(self.arcface_head)
        
        # Training Mode
        self.training_mode = config['film']['training_mode']
        if self.training_mode == "frozen":
            for p in self.encoder.parameters(): p.requires_grad = False
            self.encoder.eval()
        else:
            self.encoder.train()
            
        # Loss Weights
        self.loss_cfg = config['training']['loss']
        self.gamma_reg_w = self.loss_cfg.get('gamma_reg_weight', 0.0)
        self.beta_reg_w = self.loss_cfg.get('beta_reg_weight', 0.0)

    def forward(self, img: torch.Tensor, k: torch.Tensor) -> torch.Tensor:
        """Inference: Image + Key -> Template"""
        x = self.encoder(img)
        t, _, _ = self.fusion(x, k)
        return t

    def training_step(self, batch, batch_idx):
        x, k, labels, _, _ = batch
        
        # Fusion
        t, gamma, beta = self.fusion(x, k)
        
        # ArcFace Loss on Template 't'
        loss_arc = self.arcface_loss(t, labels)
        
        # Regularization (Identity Prior)
        loss_gamma, loss_beta = self.fusion.get_regularization_loss(gamma, beta)
        loss_reg = self.gamma_reg_w * loss_gamma + self.beta_reg_w * loss_beta
        
        loss = loss_arc + loss_reg
        
        self.log('train/loss_arc', loss_arc, prog_bar=True)
        self.log('train/loss_gamma_reg', loss_gamma)
        self.log('train/loss_beta_reg', loss_beta)
        self.log('train/gamma_mean', gamma.mean())
        self.log('train/beta_mean', beta.mean())
        self.log('train/gamma_std', gamma.std())
        
        return loss

    def validation_step(self, batch, batch_idx):
        x, k, labels, _, _ = batch
        t, gamma, beta = self.fusion(x, k)
        loss_arc = self.arcface_loss(t, labels)
        self.log('val/loss_arc', loss_arc, prog_bar=True)
        return loss_arc

    def configure_optimizers(self):
        params = [
            {'params': self.film_generator.parameters(), 'lr': self.config['training']['lr_film']},
            {'params': self.arcface_head.parameters(), 'lr': self.config['training']['lr_film']},
        ]
        if self.training_mode == "joint":
            params.append({'params': self.encoder.parameters(), 'lr': self.config['training']['lr_encoder_finetune']})
            
        optimizer = torch.optim.AdamW(params, weight_decay=self.config['training']['weight_decay'])
        scheduler = CosineAnnealingLR(optimizer, T_max=self.config['training']['epochs'], eta_min=1e-6)
        return {"optimizer": optimizer, "lr_scheduler": {"scheduler": scheduler, "interval": "epoch"}}
