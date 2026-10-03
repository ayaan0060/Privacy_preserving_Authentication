# phase1_encoder/eval/evaluate.py
"""
Standalone evaluation script.
Loads checkpoint, runs on test set, prints metrics, saves plots.
"""
import argparse
import yaml
import torch
from pathlib import Path

from ..config import load_config
from ..data.dataset import build_dataloaders
from ..model.encoder import build_encoder
from ..eval.metrics import (
    compute_verification_metrics,
    compute_identification_rank1,
    get_genuine_impostor_scores,
    plot_roc_det,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("./eval_results"))
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--max-pairs", type=int, default=100000)
    args = parser.parse_args()
    
    cfg = load_config(args.config)
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    
    # Data
    _, _, test_loader = build_dataloaders(cfg)
    
    # Model
    model = build_encoder(cfg).to(device)
    ckpt = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    
    print(f"[EVAL] Loaded checkpoint from epoch {ckpt.get('epoch', '?')}")
    print(f"[EVAL] Test set: {len(test_loader.dataset)} samples")
    
    # Extract embeddings
    all_embeddings = []
    all_labels = []
    with torch.no_grad():
        for images, labels in test_loader:
            images = images.to(device)
            embeddings = model(images)
            all_embeddings.append(embeddings.cpu())
            all_labels.append(labels)
    
    embeddings = torch.cat(all_embeddings, dim=0)
    labels = torch.cat(all_labels, dim=0)
    
    print(f"[EVAL] Embeddings shape: {embeddings.shape}")
    
    # Metrics
    ver_metrics = compute_verification_metrics(embeddings, labels, max_pairs=args.max_pairs)
    rank1 = compute_identification_rank1(embeddings, labels)
    
    print("\n" + "="*50)
    print("VERIFICATION METRICS")
    print("="*50)
    for k, v in ver_metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.6f}")
        else:
            print(f"  {k}: {v}")
    
    print(f"\n  Rank-1 Identification: {rank1:.4f}")
    print("="*50)
    
    # Plots
    args.output_dir.mkdir(parents=True, exist_ok=True)
    genuine, impostor = get_genuine_impostor_scores(embeddings, labels, max_pairs=args.max_pairs)
    plot_roc_det(genuine, impostor, str(args.output_dir / "roc_det.png"), 
                 title=f"Test Set ROC/DET (Epoch {ckpt.get('epoch', '?')})")
    
    # Save metrics
    import json
    with open(args.output_dir / "metrics.json", "w") as f:
        json.dump({**ver_metrics, "rank1": rank1}, f, indent=2)
    
    print(f"[EVAL] Results saved to {args.output_dir}")


if __name__ == "__main__":
    main()
