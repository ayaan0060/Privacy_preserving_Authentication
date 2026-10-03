# phase1_encoder/src/engine/trainer.py
import torch
import torch.nn as nn
import pytorch_lightning as pl
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts
from typing import Dict, Any, Optional
import logging

from ..models.backbone import FingerprintEncoder
from ..models.heads import ArcFaceHead
from ..models.loss import ArcFaceLoss, CenterLoss
from ..config import load_config # Helper to load yaml

log = logging.getLogger(__name__)

class FingerprintTrainer(pl.LightningModule):
    def __init__(self, config: Dict[str, Any], num_train_classes: int):
        super().__init__()
        self.save_hyperparameters(config)
        self.config = config
        
        # Model
        self.encoder = FingerprintEncoder(
            embedding_dim=config['model']['embedding_dim'],
            pretrained=config['model']['pretrained'],
            dropout=config['model']['dropout']
        )
        
        # Heads
        self.arcface_head = ArcFaceHead(
            in_features=config['model']['embedding_dim'],
            num_classes=num_train_classes,
            scale=config['arcface']['scale'],
            margin=config['arcface']['margin'],
            easy_margin=config['arcface']['easy_margin']
        )
        
        # Losses
        self.arcface_loss = ArcFaceLoss(self.arcface_head)
        
        use_center = config['training'].get('use_center_loss', False)
        if use_center:
            self.center_loss = CenterLoss(
                num_classes=num_train_classes,
                feat_dim=config['model']['embedding_dim'],
                lambda_c=config['training'].get('center_loss_weight', 0.01)
            )
        else:
            self.center_loss = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Inference path: returns L2-normalized embeddings."""
        return self.encoder(x)

    def training_step(self, batch, batch_idx):
        x, y = batch
        embeddings = self.encoder(x) # (B, 256) Normalized
        
        loss_arc = self.arcface_loss(embeddings, y)
        loss = loss_arc
        
        if self.center_loss:
            loss_center = self.center_loss(embeddings, y)
            loss = loss + loss_center
            self.log('train/loss_center', loss_center, prog_bar=False)
            
        self.log('train/loss_arcface', loss_arc, prog_bar=True)
        self.log('train/loss_total', loss, prog_bar=True)
        return loss

    def validation_step(self, batch, batch_idx):
        # Validation in identification tasks usually requires full gallery/probe split.
        # We skip heavy metric calc here; run separate evaluation script (scripts/evaluate.py)
        # This step just logs val loss for overfitting check.
        x, y = batch
        embeddings = self.encoder(x)
        loss_arc = self.arcface_loss(embeddings, y)
        self.log('val/loss_arcface', loss_arc, prog_bar=True)
        return loss_arc

    def configure_optimizers(self):
        # Different LR for backbone vs head (Head needs higher LR)
        params = [
            {'params': self.encoder.backbone.parameters(), 'lr': self.config['training']['lr_backbone']},
            {'params': self.encoder.embedding_head.parameters(), 'lr': self.config['training']['lr_head']},
            {'params': self.arcface_head.parameters(), 'lr': self.config['training']['lr_head']},
        ]
        if self.center_loss:
            params.append({'params': self.center_loss.parameters(), 'lr': self.config['training']['lr_head']})

        optimizer = torch.optim.AdamW(params, weight_decay=self.config['training']['weight_decay'])
        
        scheduler = CosineAnnealingWarmRestarts(
            optimizer, 
            T_0=self.config['training']['warmup_epochs'], 
            T_mult=1, 
            eta_min=1e-6
        )
        
        return {
            'optimizer': optimizer,
            'lr_scheduler': {'scheduler': scheduler, 'interval': 'epoch'}
        }
