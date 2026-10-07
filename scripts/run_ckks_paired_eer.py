#!/usr/bin/env python3
"""
scripts/run_ckks_paired_eer.py

Computes paired verification EER (Plaintext vs CKKS Homomorphic Encryption)
on 1,000 pairs drawn from the ALL protocol.
Rule R1: Reads raw data and outputs results/raw/ckks_paired_eer.json.
"""

import sys
import json
import csv
from pathlib import Path
import numpy as np
import tenseal as ts
from sklearn.metrics import roc_curve

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / 'eval' / 'eer_benchmark' / 'src'))

from core.keys import derive_haar_matrix
from evaluator import compute_eer_metrics

def main():
    print("Running Paired CKKS vs Plaintext EER on 1,000 ALL-protocol pairs...")
    raw_emb = np.load(ROOT_DIR / 'results' / 'raw' / 'socofing_test_embeddings.npz')
    embs = raw_emb['embeddings']
    paths = list(raw_emb['paths'])
    path_map = {p: i for i, p in enumerate(paths)}

    pairs_csv = ROOT_DIR / 'results' / 'final' / 'pairs_all.csv'
    with open(pairs_csv) as f:
        pairs = list(csv.DictReader(f))

    gen_pairs = [r for r in pairs if r['label'] == '1'][:500]
    imp_pairs = [r for r in pairs if r['label'] == '0'][:500]
    eval_pairs = gen_pairs + imp_pairs

    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=8192,
        coeff_mod_bit_sizes=[60, 40, 40, 60]
    )
    context.generate_galois_keys()
    context.global_scale = 2**40

    MASTER_SEED = b"ieee_trans_biometrics_master_entropy_seed_2026_!"
    Q = derive_haar_matrix(MASTER_SEED, "paired_ckks_eval_key", 1, 256)

    plain_scores = []
    ckks_scores = []
    labels = []
    max_err = 0.0

    print(f"Evaluating {len(eval_pairs)} pairs with TenSEAL CKKS...")
    for idx, r in enumerate(eval_pairs):
        e1 = embs[path_map[r['path1']]]
        e2 = embs[path_map[r['path2']]]
        t1 = Q @ e1
        t2 = Q @ e2

        s_plain = float(np.dot(t1, t2))
        enc1 = ts.ckks_vector(context, t1)
        enc2 = ts.ckks_vector(context, t2)
        res_enc = enc1.dot(enc2)
        s_ckks = float(res_enc.decrypt()[0])

        err = abs(s_ckks - s_plain)
        if err > max_err:
            max_err = err

        plain_scores.append(s_plain)
        ckks_scores.append(s_ckks)
        labels.append(int(r['label']))

        if (idx + 1) % 200 == 0:
            print(f"  Processed {idx + 1}/{len(eval_pairs)} pairs... (current max error = {max_err:.2e})")

    y = np.array(labels)
    sp = np.array(plain_scores)
    sc = np.array(ckks_scores)

    m_plain = compute_eer_metrics(sp[y == 1], sp[y == 0])
    m_ckks = compute_eer_metrics(sc[y == 1], sc[y == 0])

    plain_eer = m_plain['EER_percent']
    ckks_eer = m_ckks['EER_percent']
    delta_eer = ckks_eer - plain_eer

    # Bootstrap 95% CI of paired difference
    rng = np.random.RandomState(42)
    n_pairs = len(y)
    diffs = []
    for _ in range(1000):
        b_idx = rng.randint(0, n_pairs, size=n_pairs)
        yb = y[b_idx]
        if len(np.unique(yb)) < 2:
            continue
        bp = compute_eer_metrics(sp[b_idx][yb == 1], sp[b_idx][yb == 0])['EER_percent']
        bc = compute_eer_metrics(sc[b_idx][yb == 1], sc[b_idx][yb == 0])['EER_percent']
        diffs.append(bc - bp)

    ci_low = float(np.percentile(diffs, 2.5))
    ci_high = float(np.percentile(diffs, 97.5))

    print(f"\nPaired Results (N={len(eval_pairs)}):")
    print(f"  Plaintext EER: {plain_eer:.2f}%")
    print(f"  CKKS EER     : {ckks_eer:.2f}%")
    print(f"  Delta EER    : {delta_eer:.4f}% (95% Bootstrap CI: [{ci_low:.4f}%, {ci_high:.4f}%])")
    print(f"  Max Absolute CKKS Dot Error: {max_err:.2e}")

    out = {
        'protocol': 'ALL',
        'n_trials': len(eval_pairs),
        'n_genuine': len(gen_pairs),
        'n_impostor': len(imp_pairs),
        'plaintext_eer': round(float(plain_eer), 2),
        'ckks_eer': round(float(ckks_eer), 2),
        'delta_eer': round(float(delta_eer), 4),
        'ci_95': [round(ci_low, 4), round(ci_high, 4)],
        'max_ckks_error': max_err
    }

    out_path = ROOT_DIR / 'results' / 'raw' / 'ckks_paired_eer.json'
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f"[✓] Saved to {out_path}")

if __name__ == '__main__':
    main()
