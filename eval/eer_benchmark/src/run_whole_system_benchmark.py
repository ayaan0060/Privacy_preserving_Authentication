import os
import sys
import csv
import json
import asyncio
import tempfile
import shutil
import argparse
from pathlib import Path
import numpy as np
import torch
import cv2

script_dir = Path(__file__).resolve().parent
eer_benchmark_dir = script_dir.parent
eval_dir = eer_benchmark_dir.parent
phase_root = eval_dir.parent

mjr2_path = Path('/Users/ayaanwani/Documents/MJR2')
if str(mjr2_path) not in sys.path:
    sys.path.insert(0, str(mjr2_path))

for p in ['phase1_encoder', 'phase2_keymgmt', 'phase3_fusion', 'phase4_he', 'phase5_backend', 'phase6_tee', 'phase7_integration']:
    path = str(phase_root / p)
    if path not in sys.path:
        sys.path.insert(0, path)

if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))
if str(phase_root) not in sys.path:
    sys.path.insert(0, str(phase_root))

from app.fingerprint_model import FingerprintEncoder
from evaluator import compute_eer_metrics, plot_eer_curves
from integration.pipeline import BiometricPipeline, PipelineConfig, _ENROLLMENT_CACHE
from he.crypto import generate_he_keys
from he.params import DEFAULT_PARAMS
from film.model import FiLMFusionExport

class CorrectEncoderAdapter:
    def __init__(self, encoder: FingerprintEncoder):
        self.encoder = encoder
        self.cache = {}

    def run(self, output_names, input_feed):
        img_arr = list(input_feed.values())[0] # (1, 96, 96) in [-1, 1]
        h = hash(img_arr.tobytes())
        if h in self.cache:
            return [self.cache[h]]
        # Mathematical identity: ([-1, 1] + 1.0) / 2.0 == [0, 1]
        img_0_1 = (img_arr + 1.0) / 2.0
        t = torch.from_numpy(img_0_1).float()
        if t.ndim == 3:
            t = t.unsqueeze(0) # (1, 1, 96, 96)
        if t.shape[1] == 1:
            t = t.repeat(1, 3, 1, 1) # (1, 3, 96, 96)
        with torch.no_grad():
            emb = self.encoder(t).numpy()
        self.cache[h] = emb
        return [emb]

async def run_whole_system_benchmark(pairs_csv: Path, ckpt_path: Path, results_dir: Path, num_pairs: int = 500):
    print('=' * 85, flush=True)
    print(f'🔒 EVALUATION B: WHOLE-SYSTEM HOMOMORPHIC PIPELINE EER (N={num_pairs})', flush=True)
    print('=' * 85, flush=True)

    encoder = FingerprintEncoder()
    state = torch.load(ckpt_path, map_location='cpu')
    if 'state_dict' in state:
        state = state['state_dict']
    encoder.load_state_dict(state)
    encoder.eval()
    print(f'[✓] Loaded encoder model from {ckpt_path}', flush=True)

    with open(pairs_csv, 'r') as f:
        all_rows = list(csv.DictReader(f))

    gen_rows = [r for r in all_rows if int(r['label']) == 1]
    imp_rows = [r for r in all_rows if int(r['label']) == 0]

    half = num_pairs // 2
    eval_rows = gen_rows[:half] + imp_rows[:half]
    print(f'[✓] Selected {len(eval_rows)} balanced pairs ({half} genuine + {half} impostor)', flush=True)

    device_dir = tempfile.mkdtemp()
    he_dir = tempfile.mkdtemp()
    keystore_dir = tempfile.mkdtemp()
    film_dir = tempfile.mkdtemp()

    try:
        print('[HE] Generating CKKS encryption keys...', flush=True)
        generate_he_keys(Path(he_dir), DEFAULT_PARAMS)
        film_model = FiLMFusionExport(embedding_dim=256)
        film_model.eval()

        config = PipelineConfig(
            encoder_path=Path(film_dir) / 'encoder.onnx',
            film_path=Path(film_dir) / 'film.onnx',
            he_key_dir=Path(he_dir),
            keystore_dir=Path(keystore_dir),
            device_key_dir=Path(device_dir),
        )

        pipeline = BiometricPipeline(config)
        pipeline.film_session = film_model
        pipeline.encoder_session = CorrectEncoderAdapter(encoder)

        sys_genuine_scores = []
        sys_impostor_scores = []

        total = len(eval_rows)
        for idx, row in enumerate(eval_rows, 1):
            if idx % 50 == 0 or idx == total:
                print(f'  [EVALUATION B PROGRESS] Processed {idx}/{total} pairs...', flush=True)

            img1 = cv2.imread(row['img_path_1'], cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(row['img_path_2'], cv2.IMREAD_GRAYSCALE)
            if img1 is None or img2 is None:
                continue

            user_target = f'target_user_{idx}'
            user_probe  = f'target_user_{idx}' if int(row['label']) == 1 else f'impostor_user_{idx}'

            await pipeline.enroll(user_target, img1)
            if int(row['label']) == 0:
                await pipeline.enroll(user_probe, img2)

            verify_res = await pipeline.verify(user_target, img2)
            score = float(verify_res.similarity_score)

            if int(row['label']) == 1:
                sys_genuine_scores.append(score)
            else:
                sys_impostor_scores.append(score)

            _ENROLLMENT_CACHE.clear()

            # Clean per-pair keystore files
            for u in [user_target, user_probe]:
                fpath = Path(keystore_dir) / f'{u}.enc'
                if fpath.exists():
                    try: fpath.unlink()
                    except Exception: pass
                dpath = Path(keystore_dir) / u
                if dpath.exists():
                    try: shutil.rmtree(dpath)
                    except Exception: pass

        gen_arr = np.array(sys_genuine_scores)
        imp_arr = np.array(sys_impostor_scores)

        metrics = compute_eer_metrics(gen_arr, imp_arr)
        print("\n[RESULTS - EVALUATION B: WHOLE-SYSTEM]", flush=True)
        print(f"  ✓ {metrics['EER_formatted_string']}", flush=True)
        print(f"  ✓ EER Threshold: {metrics['EER_threshold']:.4f}", flush=True)
        print(f"  ✓ ROC-AUC: {metrics['ROC_AUC']:.6f}", flush=True)
        print(f"  ✓ TAR @ 1% FAR: {metrics['TAR_at_FAR_1pct']:.2f}%", flush=True)
        print(f"  ✓ TAR @ 0.1% FAR: {metrics['TAR_at_FAR_01pct']:.2f}%", flush=True)
        print(f"  ✓ Genuine Stats:  Min={metrics['genuine_stats']['min']:.4f}, Max={metrics['genuine_stats']['max']:.4f}, Mean={metrics['genuine_stats']['mean']:.4f}, Std={metrics['genuine_stats']['std']:.4f}", flush=True)
        print(f"  ✓ Impostor Stats: Min={metrics['impostor_stats']['min']:.4f}, Max={metrics['impostor_stats']['max']:.4f}, Mean={metrics['impostor_stats']['mean']:.4f}, Std={metrics['impostor_stats']['std']:.4f}", flush=True)

        results_dir.mkdir(parents=True, exist_ok=True)
        json_path = results_dir / 'socofing_whole_system_eer.json'
        with open(json_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"[✓] Saved JSON results to: {json_path}", flush=True)

        plot_path = results_dir / 'socofing_whole_system_det.png'
        plot_eer_curves(metrics, plot_path, f"Evaluation B: Whole-System EER (Full CKKS Pipeline, N={len(eval_rows)})")

    finally:
        for d in [device_dir, he_dir, keystore_dir, film_dir]:
            try: shutil.rmtree(d)
            except Exception: pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pairs-csv', type=Path, default=Path('/Users/ayaanwani/Documents/ biometric-auth-system/eval/eer_benchmark/pairs/socofing_benchmark_pairs.csv'))
    parser.add_argument('--ckpt', type=Path, default=Path('/Users/ayaanwani/Documents/MJR2/artifacts/fingerprint_encoder.pt'))
    parser.add_argument('--results-dir', type=Path, default=Path('/Users/ayaanwani/Documents/ biometric-auth-system/eval/eer_benchmark/results'))
    parser.add_argument('--num-pairs', type=int, default=500)
    args = parser.parse_args()

    asyncio.run(run_whole_system_benchmark(args.pairs_csv, args.ckpt, args.results_dir, args.num_pairs))
