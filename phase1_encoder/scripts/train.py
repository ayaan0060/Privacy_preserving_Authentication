# phase1_encoder/scripts/train.py
"""
Training script for Phase 1 Encoder.
Delegates to train.trainer.Trainer.
"""
import os
import sys
import argparse
import torch
from pathlib import Path

# Add phase1_encoder root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import load_config
from data.dataset import build_dataloaders
from model.encoder import build_encoder
from train.trainer import Trainer

def main():
    parser = argparse.ArgumentParser(description="Train Phase 1 Fingerprint Encoder")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="Path to config.yaml")
    parser.add_argument("--resume", type=Path, default=None, help="Path to checkpoint to resume from")
    args = parser.parse_args()

    cfg = load_config(args.config)
    device = torch.device(cfg.get("device", "cuda") if torch.cuda.is_available() else "cpu")

    train_loader, val_loader, _ = build_dataloaders(cfg)
    model = build_encoder(cfg)

    trainer = Trainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        cfg=cfg,
        device=device,
    )

    trainer.fit(resume_from=args.resume)

if __name__ == "__main__":
    main()
