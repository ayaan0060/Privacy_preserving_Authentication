import os
import sys
import csv
import cv2
import numpy as np
import torch
from pathlib import Path
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from collections import defaultdict

# Ensure MJR2 and project root are importable
sys.path.insert(0, '/Users/ayaanwani/Documents/MJR2')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.fingerprint_model import FingerprintEncoder
from app.dataset import FingerprintDataset

class ImageListDataset(Dataset):
    def __init__(self, paths):
        self.paths = paths

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        p = self.paths[idx]
        img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(f"Cannot read: {p}")
        img = FingerprintDataset._preprocess(img)
        t = torch.from_numpy(img).unsqueeze(0).repeat(3, 1, 1) # (3, 96, 96)
        return t, idx

def extract_and_save(paths, encoder, device, out_path, batch_size=256):
    dataset = ImageListDataset(paths)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    embeddings = np.zeros((len(paths), 256), dtype=np.float32)

    with torch.no_grad():
        for batch_idx, (batch_t, indices) in enumerate(loader):
            batch_t = batch_t.to(device)
            out = encoder(batch_t).cpu().numpy()
            for i, idx in enumerate(indices.numpy()):
                embeddings[idx] = out[i]
            if (batch_idx + 1) % 10 == 0 or (batch_idx + 1) == len(loader):
                print(f"  Processed {min((batch_idx + 1) * batch_size, len(paths))}/{len(paths)}...")

    np.savez_compressed(out_path, embeddings=embeddings, paths=np.array(paths))
    print(f"[✓] Saved {len(paths)} embeddings to {out_path}")

def main():
    device = torch.device('mps' if torch.backends.mps.is_available() else 'cpu')
    print(f"Using compute device: {device}")

    encoder = FingerprintEncoder().to(device)
    ckpt_path = Path('exports/fingerprint_encoder.pt')
    state = torch.load(ckpt_path, map_location=device)
    if 'state_dict' in state:
        state = state['state_dict']
    encoder.load_state_dict(state)
    encoder.eval()

    out_dir = Path('results/raw')
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 10k Benchmark pairs embeddings
    pairs_csv = Path('eval/eer_benchmark/pairs/socofing_benchmark_10k_pairs.csv')
    with open(pairs_csv, 'r') as f:
        reader = list(csv.DictReader(f))
    unique_10k = sorted(list({r['img_path_1'] for r in reader} | {r['img_path_2'] for r in reader}))
    
    file_10k = out_dir / 'socofing_10k_embeddings.npz'
    if not file_10k.exists():
        print(f"Extracting 10k benchmark embeddings ({len(unique_10k)} images)...")
        extract_and_save(unique_10k, encoder, device, file_10k)
    else:
        print(f"10k benchmark embeddings already exist at {file_10k}")

    # 2. Test partition embeddings (for alteration breakdown & test-set stats)
    base = Path('/Users/ayaanwani/.cache/kagglehub/datasets/ruizgara/socofing/versions/2/SOCOFing/SOCOFing')
    real_files = list((base / 'Real').glob('*.BMP'))
    altered_easy = list((base / 'Altered' / 'Altered-Easy').glob('*.BMP'))
    altered_med  = list((base / 'Altered' / 'Altered-Medium').glob('*.BMP'))
    altered_hard = list((base / 'Altered' / 'Altered-Hard').glob('*.BMP'))

    all_files = real_files + altered_easy + altered_med + altered_hard
    def get_subj(f): return f.name.split('__')[0]
    subj_files = defaultdict(list)
    for f in all_files: subj_files[get_subj(f)].append(f)
    subjects = sorted(list(subj_files.keys()), key=lambda x: int(x))

    train_subjs, test_subjs = train_test_split(subjects, test_size=0.15, random_state=42, shuffle=True)
    train_subjs, val_subjs = train_test_split(train_subjs, test_size=0.15 / 0.85, random_state=42, shuffle=True)

    test_paths = sorted([str(f) for s in test_subjs for f in subj_files[s]])
    val_paths = sorted([str(f) for s in val_subjs for f in subj_files[s]])

    file_test = out_dir / 'socofing_test_embeddings.npz'
    print(f"Extracting test partition embeddings ({len(test_paths)} images)...")
    extract_and_save(test_paths, encoder, device, file_test)

    file_val = out_dir / 'socofing_val_embeddings.npz'
    print(f"Extracting val partition embeddings ({len(val_paths)} images)...")
    extract_and_save(val_paths, encoder, device, file_val)

if __name__ == '__main__':
    main()
