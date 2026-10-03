# phase1_encoder/train/trainer.py
"""
Training loop with:
- AMP (Automatic Mixed Precision)
- Cosine warm restarts LR schedule
- ArcFace margin scheduling (optional)
- Checkpointing (best EER + periodic)
- Gradient clipping
- TensorBoard logging (optional)
"""
import os
import math
import time
from pathlib import Path
from typing import Dict, Any, Optional

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.cuda.amp import GradScaler, autocast
from tqdm import tqdm

from ..model.encoder import FingerprintEncoder
from ..model.loss import ArcFaceLoss, MarginScheduler


class Trainer:
    def __init__(
        self,
        model: FingerprintEncoder,
        train_loader: DataLoader,
        val_loader: DataLoader,
        cfg: Dict[str, Any],
        device: torch.device,
        log_dir: Optional[Path] = None,
    ):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.cfg = cfg
        self.device = device
        self.log_dir = Path(log_dir) if log_dir else Path(cfg["train"]["checkpoint_dir"])
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Loss
        if hasattr(train_loader.dataset, 'subset'):
            base_ds = train_loader.dataset.subset.dataset
        else:
            base_ds = train_loader.dataset
        num_classes = len(base_ds.subjects)
        
        self.criterion = ArcFaceLoss(
            embedding_dim=cfg["model"]["embedding_dim"],
            num_classes=num_classes,
            margin=cfg["loss"]["margin"],
            scale=cfg["loss"]["scale"],
        ).to(device)
        
        # Optimizer
        params = list(model.parameters()) + list(self.criterion.parameters())
        if cfg["train"]["optimizer"] == "adamw":
            self.optimizer = torch.optim.AdamW(
                params,
                lr=cfg["train"]["lr"],
                weight_decay=cfg["train"]["weight_decay"],
            )
        elif cfg["train"]["optimizer"] == "sgd":
            self.optimizer = torch.optim.SGD(
                params,
                lr=cfg["train"]["lr"],
                momentum=0.9,
                weight_decay=cfg["train"]["weight_decay"],
            )
        else:
            raise ValueError(f"Unknown optimizer: {cfg['train']['optimizer']}")
        
        # Scheduler
        if cfg["train"]["scheduler"] == "cosine_warm_restarts":
            self.scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
                self.optimizer,
                T_0=cfg["train"]["warmup_epochs"],
                T_mult=2,
                eta_min=cfg["train"]["lr"] * 0.01,
            )
        elif cfg["train"]["scheduler"] == "cosine":
            self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                self.optimizer,
                T_max=cfg["train"]["epochs"],
                eta_min=cfg["train"]["lr"] * 0.01,
            )
        else:
            self.scheduler = None
        
        # Margin scheduler
        self.margin_scheduler = None
        if cfg["loss"].get("margin_schedule") == "cosine_anneal":
            self.margin_scheduler = MarginScheduler(
                self.criterion,
                initial_margin=cfg["loss"]["margin"],
                final_margin=0.3,  # Tighter margin at end
                total_epochs=cfg["train"]["epochs"],
            )
        
        # AMP
        self.scaler = GradScaler(enabled=cfg["train"]["amp"])
        
        # State
        self.epoch = 0
        self.step = 0
        self.best_eer = float('inf')
        self.history = {"train_loss": [], "val_eer": [], "lr": []}
    
    def train_epoch(self) -> float:
        self.model.train()
        self.criterion.train()
        total_loss = 0.0
        num_batches = 0
        
        pbar = tqdm(self.train_loader, desc=f"Epoch {self.epoch+1} [Train]", leave=False)
        for images, labels in pbar:
            images = images.to(self.device, non_blocking=True)
            labels = labels.to(self.device, non_blocking=True)
            
            self.optimizer.zero_grad(set_to_none=True)
            
            with autocast(enabled=self.cfg["train"]["amp"]):
                embeddings = self.model(images)
                loss = self.criterion(embeddings, labels)
            
            self.scaler.scale(loss).backward()
            
            # Gradient clipping
            if self.cfg["train"]["grad_clip"] > 0:
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(
                    list(self.model.parameters()) + list(self.criterion.parameters()),
                    self.cfg["train"]["grad_clip"]
                )
            
            self.scaler.step(self.optimizer)
            self.scaler.update()
            
            total_loss += loss.item()
            num_batches += 1
            self.step += 1
            
            if self.step % self.cfg["train"]["log_every"] == 0:
                pbar.set_postfix({"loss": f"{loss.item():.4f}", "lr": f"{self.optimizer.param_groups[0]['lr']:.2e}"})
        
        avg_loss = total_loss / max(1, num_batches)
        return avg_loss
    
    @torch.no_grad()
    def validate(self) -> float:
        self.model.eval()
        self.criterion.eval()
        
        # Extract all embeddings for validation set
        all_embeddings = []
        all_labels = []
        
        for images, labels in tqdm(self.val_loader, desc=f"Epoch {self.epoch+1} [Val]", leave=False):
            images = images.to(self.device, non_blocking=True)
            with autocast(enabled=self.cfg["train"]["amp"]):
                embeddings = self.model(images)
            all_embeddings.append(embeddings.cpu())
            all_labels.append(labels)
        
        embeddings = torch.cat(all_embeddings, dim=0)  # (N, D)
        labels = torch.cat(all_labels, dim=0)          # (N,)
        
        from ..eval.metrics import compute_verification_metrics
        metrics = compute_verification_metrics(embeddings, labels, max_pairs=50000)
        eer = metrics["eer"]
        
        return eer
    
    def save_checkpoint(self, name: str, eer: float | None = None):
        path = self.log_dir / f"{name}.pt"
        torch.save({
            "epoch": self.epoch,
            "step": self.step,
            "model_state": self.model.state_dict(),
            "criterion_state": self.criterion.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "scheduler_state": self.scheduler.state_dict() if self.scheduler else None,
            "best_eer": self.best_eer,
            "cfg": self.cfg,
        }, path)
        print(f"[CHECKPOINT] Saved {path} (EER: {eer:.4f})" if eer else f"[CHECKPOINT] Saved {path}")
    
    def load_checkpoint(self, path: Path):
        ckpt = torch.load(path, map_location=self.device)
        self.model.load_state_dict(ckpt["model_state"])
        self.criterion.load_state_dict(ckpt["criterion_state"])
        self.optimizer.load_state_dict(ckpt["optimizer_state"])
        if self.scheduler and ckpt["scheduler_state"]:
            self.scheduler.load_state_dict(ckpt["scheduler_state"])
        self.epoch = ckpt["epoch"]
        self.step = ckpt["step"]
        self.best_eer = ckpt["best_eer"]
        print(f"[RESUME] Loaded checkpoint from epoch {self.epoch}, best EER: {self.best_eer:.4f}")
    
    def fit(self, resume_from: Path | None = None):
        if resume_from:
            self.load_checkpoint(resume_from)
        
        print(f"[START] Training for {self.cfg['train']['epochs']} epochs on {self.device}")
        print(f"[CONFIG] Classes: {self.criterion.num_classes}, Embedding: {self.cfg['model']['embedding_dim']}d")
        
        for epoch in range(self.epoch, self.cfg["train"]["epochs"]):
            self.epoch = epoch
            start = time.time()
            
            # Margin scheduling
            if self.margin_scheduler:
                margin = self.margin_scheduler.step(epoch)
                print(f"  Margin: {margin:.4f}")
            
            # Train
            train_loss = self.train_epoch()
            
            # Validate
            val_eer = self.validate()
            
            # LR step
            if self.scheduler:
                self.scheduler.step()
            
            # Logging
            lr = self.optimizer.param_groups[0]["lr"]
            self.history["train_loss"].append(train_loss)
            self.history["val_eer"].append(val_eer)
            self.history["lr"].append(lr)
            
            elapsed = time.time() - start
            print(f"Epoch {epoch+1}/{self.cfg['train']['epochs']} | "
                  f"Loss: {train_loss:.4f} | Val EER: {val_eer:.4f} | LR: {lr:.2e} | Time: {elapsed:.1f}s")
            
            # Checkpointing
            if val_eer < self.best_eer:
                self.best_eer = val_eer
                self.save_checkpoint("best", val_eer)
            
            if (epoch + 1) % self.cfg["train"]["save_every"] == 0:
                self.save_checkpoint(f"epoch_{epoch+1}")
        
        print(f"[DONE] Best EER: {self.best_eer:.4f}")
        return self.history
