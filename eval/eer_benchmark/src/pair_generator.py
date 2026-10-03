import os
import sys
import argparse
import csv
import re
import random
from pathlib import Path

DEFAULT_SOCOFING_DIR = Path('/Users/ayaanwani/.cache/kagglehub/datasets/ruizgara/socofing/versions/2/SOCOFing/SOCOFing')

def build_socofing_pairs(
    dataset_dir: Path,
    output_csv: Path,
    num_genuine: int = 3000,
    num_impostor: int = 3000,
    seed: int = 42
):
    print(f'[DATASET] Generating pairs from SOCOFing at {dataset_dir}...')
    real_dir = dataset_dir / 'Real'
    alt_dir = dataset_dir / 'Altered' / 'Altered-Easy'

    if not real_dir.exists() or not alt_dir.exists():
        raise FileNotFoundError(f'SOCOFing dataset missing Real or Altered-Easy in {dataset_dir}')

    real_files = sorted(list(real_dir.glob('*.BMP')))
    alt_files = sorted(list(alt_dir.glob('*.BMP')))

    print(f'  Found {len(real_files)} Real images and {len(alt_files)} Altered-Easy impressions.')

    alt_map = {}
    for p in alt_files:
        m = re.match(r'^(.*)_(CR|Obl|Zcut)$', p.stem)
        if m:
            alt_map.setdefault(m.group(1), []).append(p)

    matching_real = [p for p in real_files if p.stem in alt_map]
    print(f'  Total fingers with verified impressions: {len(matching_real)}')

    rng = random.Random(seed)
    rng.shuffle(matching_real)

    # 1. Genuine pairs (same finger identity, different impressions)
    genuine_pairs = []
    for p_real in matching_real[:num_genuine]:
        finger_id = p_real.stem
        p_alt = rng.choice(alt_map[finger_id])
        genuine_pairs.append({
            'img_path_1': str(p_real),
            'img_path_2': str(p_alt),
            'pair_type': 'genuine',
            'label': 1,
            'identity_1': finger_id,
            'identity_2': finger_id
        })

    # 2. Impostor pairs (different subject identities)
    impostor_pairs = []
    attempts = 0
    max_attempts = num_impostor * 20
    seen_pairs = set()

    while len(impostor_pairs) < num_impostor and attempts < max_attempts:
        attempts += 1
        p1, p2 = rng.sample(real_files, 2)
        subj1 = p1.stem.split('__')[0]
        subj2 = p2.stem.split('__')[0]
        if subj1 == subj2:
            continue
        
        pair_key = tuple(sorted([p1.stem, p2.stem]))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        impostor_pairs.append({
            'img_path_1': str(p1),
            'img_path_2': str(p2),
            'pair_type': 'impostor',
            'label': 0,
            'identity_1': p1.stem,
            'identity_2': p2.stem
        })

    all_pairs = genuine_pairs + impostor_pairs
    rng.shuffle(all_pairs)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, 'w', newline='') as f:
        fieldnames = ['img_path_1', 'img_path_2', 'pair_type', 'label', 'identity_1', 'identity_2']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_pairs:
            writer.writerow(row)

    print(f'[✓] SOCOFing Pair CSV generated: {output_csv}')
    print(f'    - Total pairs: {len(all_pairs)}')
    print(f'    - Genuine pairs: {len(genuine_pairs)}')
    print(f'    - Impostor pairs: {len(impostor_pairs)}')
    return len(genuine_pairs), len(impostor_pairs)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset-dir', type=Path, default=DEFAULT_SOCOFING_DIR)
    parser.add_argument('--output-csv', type=Path, default=Path('/Users/ayaanwani/Documents/ biometric-auth-system/eval/eer_benchmark/pairs/socofing_benchmark_pairs.csv'))
    parser.add_argument('--num-genuine', type=int, default=3000)
    parser.add_argument('--num-impostor', type=int, default=3000)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    build_socofing_pairs(args.dataset_dir, args.output_csv, args.num_genuine, args.num_impostor, args.seed)
