import os
import sys
import csv
import json
import argparse
from pathlib import Path
import cv2
import numpy as np
import torch

script_dir = Path(__file__).resolve().parent
eer_benchmark_dir = script_dir.parent
eval_dir = eer_benchmark_dir.parent
phase_root = eval_dir.parent

mjr2_path = Path('/Users/ayaanwani/Documents/MJR2')
if str(mjr2_path) not in sys.path:
    sys.path.insert(0, str(mjr2_path))
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from app.fingerprint_model import FingerprintEncoder
from app.dataset import FingerprintDataset
from evaluator import compute_eer_metrics, plot_eer_curves

def preprocess_socofing(image_path: str) -> torch.Tensor:
    """Exact training preprocessing from MJR2/app/dataset.py"""
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    img = cv2.equalizeHist(img)
    img = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(img)
    img = FingerprintDataset._crop_roi(img)
    img = cv2.resize(img, (96, 96), interpolation=cv2.INTER_AREA)
    img = img.astype(np.float32) / 255.0
    tensor = torch.from_numpy(img).unsqueeze(0).unsqueeze(0).repeat(1, 3, 1, 1)
    return tensor

def run_encoder_benchmark(pairs_csv: Path, ckpt_path: Path, results_dir: Path):
    print("=" * 85, flush=True)
    print("🔒 EVALUATION A: ENCODER-LEVEL BIOMETRIC EER (REAL SOCOFING DATASET)", flush=True)
    print("=" * 85, flush=True)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    encoder = FingerprintEncoder().to(device)
    state = torch.load(ckpt_path, map_location=device)
    if 'state_dict' in state:
        state = state['state_dict']
    encoder.load_state_dict(state)
    encoder.eval()
    print(f"[✓] Loaded model weights from {ckpt_path} on {device}", flush=True)

    with open(pairs_csv, 'r') as f:
        reader = list(csv.DictReader(f))

    print(f"[✓] Loaded {len(reader)} pairs from {pairs_csv}", flush=True)

    genuine_scores = []
    impostor_scores = []

    # Cache embeddings by image path to avoid redundant forward passes
    emb_cache = {}

    def get_embedding(img_path: str) -> np.ndarray:
        if img_path not in emb_cache:
            t = preprocess_socofing(img_path).to(device)
            with torch.no_grad():
                emb = encoder(t).cpu().numpy()[0]
            emb_cache[img_path] = emb
        return emb_cache[img_path]

    total = len(reader)
    for idx, row in enumerate(reader, 1):
        if idx % 1000 == 0 or idx == total:
            print(f"  [PROGRESS] Evaluated {idx}/{total} pairs ({len(emb_cache)} unique images cached)...", flush=True)

        e1 = get_embedding(row['img_path_1'])
        e2 = get_embedding(row['img_path_2'])
        sim = float(np.dot(e1, e2))

        if int(row['label']) == 1:
            genuine_scores.append(sim)
        else:
            impostor_scores.append(sim)

    gen_arr = np.array(genuine_scores)
    imp_arr = np.array(impostor_scores)

    metrics = compute_eer_metrics(gen_arr, imp_arr)
    print("\n[RESULTS - EVALUATION A: ENCODER-LEVEL]", flush=True)
    print(f"  ✓ {metrics['EER_formatted_string']}", flush=True)
    print(f"  ✓ EER Threshold: {metrics['EER_threshold']:.4f}", flush=True)
    print(f"  ✓ ROC-AUC: {metrics['ROC_AUC']:.6f}", flush=True)
    print(f"  ✓ TAR @ 1% FAR: {metrics['TAR_at_FAR_1pct']:.2f}%", flush=True)
    print(f"  ✓ TAR @ 0.1% FAR: {metrics['TAR_at_FAR_01pct']:.2f}%", flush=True)
    print(f"  ✓ Genuine Stats:  Min={metrics['genuine_stats']['min']:.4f}, Max={metrics['genuine_stats']['max']:.4f}, Mean={metrics['genuine_stats']['mean']:.4f}, Std={metrics['genuine_stats']['std']:.4f}", flush=True)
    print(f"  ✓ Impostor Stats: Min={metrics['impostor_stats']['min']:.4f}, Max={metrics['impostor_stats']['max']:.4f}, Mean={metrics['impostor_stats']['mean']:.4f}, Std={metrics['impostor_stats']['std']:.4f}", flush=True)

    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = results_dir / 'socofing_encoder_level_eer.json'
    with open(json_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"[✓] Saved JSON results to: {json_path}", flush=True)

    plot_path = results_dir / 'socofing_encoder_level_det.png'
    plot_eer_curves(metrics, plot_path, "Evaluation A: Encoder-Level EER (Real SOCOFing Dataset)")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pairs-csv', type=Path, default=Path('/Users/ayaanwani/Documents/ biometric-auth-system/eval/eer_benchmark/pairs/socofing_benchmark_pairs.csv'))
    parser.add_argument('--ckpt', type=Path, default=Path('/Users/ayaanwani/Documents/MJR2/artifacts/fingerprint_encoder.pt'))
    parser.add_argument('--results-dir', type=Path, default=Path('/Users/ayaanwani/Documents/ biometric-auth-system/eval/eer_benchmark/results'))
    args = parser.parse_args()

    run_encoder_benchmark(args.pairs_csv, args.ckpt, args.results_dir)
