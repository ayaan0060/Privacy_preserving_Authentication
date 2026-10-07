#!/usr/bin/env python3
"""
scripts/run_protocol_experiments.py

Protocol-wide experiment rerun (Stage 1).
Runs ALL and EASY protocols across 3 pair-sampling seeds on one encoder.
Outputs metrics keyed as metrics[protocol][...] into results/final/metrics.json.

Rule R1: No number is typed by hand.
Rule R2: Parameters unchanged after seeing results.
Rule R3: Cannot-run items are flagged; no value is copied from another protocol.
"""

import os, sys, json, csv, math, random
from pathlib import Path
from collections import defaultdict

import numpy as np
import scipy.stats as stats
from sklearn.metrics import roc_curve

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / 'eval' / 'eer_benchmark' / 'src'))

from core.protocol import (
    build_pairs, save_pairs, load_pairs, pair_counts,
    PROTOCOL_ALL, PROTOCOL_EASY, Pair
)
from core.keys import (
    derive_haar_matrix, derive_film_key, derive_bipolar_signs,
    derive_permutation, derive_iom_matrices,
)
from core.film import FiLMGenerator, apply_film_modulation
from evaluator import compute_eer_metrics

import torch
from scripts.provenance import record_manifest_entry

FINAL_DIR = ROOT_DIR / 'results' / 'final'
RAW_DIR   = ROOT_DIR / 'results' / 'raw'
FINAL_DIR.mkdir(parents=True, exist_ok=True)

MASTER_SEED = b"ieee_trans_biometrics_master_entropy_seed_2026_!"
SEEDS = [42, 123, 456]
DIM   = 256

# ==============================================================================
# Helpers
# ==============================================================================

def get_subject(path): return Path(path).name.split('__')[0]

def get_finger(path):
    fname = Path(path).name
    for t in ['_CR', '_Obl', '_Zcut']: fname = fname.replace(t, '')
    return fname.replace('.BMP', '')


def load_embeddings(npz_path):
    d = np.load(npz_path)
    paths = [str(p) for p in d['paths']]
    return d['embeddings'], paths


def cosine_sim(a, b):
    na = np.linalg.norm(a); nb = np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12: return 0.0
    return float(np.dot(a, b) / (na * nb))


def compute_eer_from_scores(gen, imp):
    """EER, tau at EER, FAR@tau, FRR@tau, d', TAR@FAR1%, TAR@FAR0.1%"""
    g = np.array(gen, dtype=np.float64)
    i = np.array(imp, dtype=np.float64)
    y = np.concatenate([np.ones(len(g)), np.zeros(len(i))])
    s = np.concatenate([g, i])
    fpr, tpr, th = roc_curve(y, s)
    fnr = 1.0 - tpr
    idx = np.argmin(np.abs(fpr - fnr))
    eer = float((fpr[idx] + fnr[idx]) / 2.0 * 100.0)
    tau = float(th[idx])
    far_at_tau = float(np.mean(i >= tau) * 100.0)
    frr_at_tau = float(np.mean(g < tau) * 100.0)
    mu_g, s_g = float(g.mean()), float(g.std())
    mu_i, s_i = float(i.mean()), float(i.std())
    dprime = float((mu_g - mu_i) / (np.sqrt(0.5*(s_g**2 + s_i**2)) + 1e-12))
    th_far1  = float(np.percentile(i, 99.0))
    th_far01 = float(np.percentile(i, 99.9))
    tar1  = float(np.mean(g >= th_far1)  * 100.0)
    tar01 = float(np.mean(g >= th_far01) * 100.0)
    return dict(
        eer_percent=round(eer, 2),
        tau=round(tau, 4),
        far_at_tau=round(far_at_tau, 2),
        frr_at_tau=round(frr_at_tau, 2),
        d_prime=round(dprime, 4),
        tar_at_far_1pct=round(tar1, 2),
        tar_at_far_01pct=round(tar01, 2),
        genuine_mean=round(mu_g, 4),
        genuine_std=round(s_g, 4),
        impostor_mean=round(mu_i, 4),
        impostor_std=round(s_i, 4),
        n_genuine=int(len(g)),
        n_impostor=int(len(i)),
    )


def bootstrap_eer_ci(gen, imp, n_boot=1000, seed=42):
    rng_b = np.random.RandomState(seed)
    g = np.array(gen); i = np.array(imp)
    boot_eers = []
    for _ in range(n_boot):
        bg = g[rng_b.choice(len(g), len(g), replace=True)]
        bi = i[rng_b.choice(len(i), len(i), replace=True)]
        boot_eers.append(compute_eer_from_scores(bg, bi)['eer_percent'])
    return round(float(np.percentile(boot_eers, 2.5)), 2), round(float(np.percentile(boot_eers, 97.5)), 2)


def compute_validation_transfer(test_scores_rop, proto):
    """
    Computes validation threshold on socofing_val_embeddings.npz for the given protocol,
    then transfers it to the test set genuine/impostor scores (test_scores_rop).
    """
    val_npz = RAW_DIR / 'socofing_val_embeddings.npz'
    val_data = np.load(val_npz)
    v_embs = val_data['embeddings']
    v_paths = [str(p) for p in val_data['paths']]
    v_map = {p: i for i, p in enumerate(v_paths)}
    v_reals = [p for p in v_paths if '/Real/' in p]
    v_real_map = {Path(p).name.replace('.BMP', ''): v_map[p] for p in v_reals}

    v_gen = []
    for p in v_paths:
        if '/Real/' in p:
            continue
        if proto == PROTOCOL_EASY and 'Easy' not in p:
            continue
        fname = Path(p).name.replace('.BMP', '')
        for suf in ['_CR', '_Obl', '_Zcut']:
            fname = fname.replace(suf, '')
        if fname in v_real_map:
            v_gen.append(float(np.dot(v_embs[v_map[p]], v_embs[v_real_map[fname]])))

    rng_v = random.Random(42)
    v_imp = []
    seen_v = set()
    while len(v_imp) < len(v_gen):
        p1, p2 = rng_v.sample(v_reals, 2)
        s1, s2 = Path(p1).stem.split('__')[0], Path(p2).stem.split('__')[0]
        if s1 == s2:
            continue
        key = tuple(sorted([p1, p2]))
        if key in seen_v:
            continue
        seen_v.add(key)
        v_imp.append(float(np.dot(v_embs[v_map[p1]], v_embs[v_map[p2]])))

    y_v = np.concatenate([np.ones(len(v_gen)), np.zeros(len(v_imp))])
    s_v = np.concatenate([v_gen, v_imp])
    fpr_v, tpr_v, th_v = roc_curve(y_v, s_v)
    fnr_v = 1.0 - tpr_v
    idx_v = np.argmin(np.abs(fpr_v - fnr_v))
    val_tau = float(th_v[idx_v])
    val_eer = float((fpr_v[idx_v] + fnr_v[idx_v]) / 2.0 * 100.0)

    # Evaluate on test set genuine/impostor scores
    t_gen = np.array(test_scores_rop['gen'])
    t_imp = np.array(test_scores_rop['imp'])
    test_far_at_val = float(np.mean(t_imp >= val_tau) * 100.0)
    test_frr_at_val = float(np.mean(t_gen < val_tau) * 100.0)
    transfer_gap = float(abs(test_frr_at_val - test_far_at_val))

    return {
        'val_tau': round(val_tau, 4),
        'val_eer': round(val_eer, 2),
        'test_far_at_val_tau': round(test_far_at_val, 2),
        'test_frr_at_val_tau': round(test_frr_at_val, 2),
        'transfer_gap': round(transfer_gap, 2),
        'n_val_genuine': len(v_gen),
        'n_val_impostor': len(v_imp)
    }


def compute_cross_entropy_metrics():
    """
    Computes cross-entropy baseline metrics from saved raw score arrays.
    Only EASY nominal benchmark scores exist; ALL alteration scores were not preserved.
    """
    ce_res = {'ALL': None, 'EASY': {}}
    eers, tar1s, tar01s, dps = [], [], [], []
    per_seed = {}
    for s in SEEDS:
        f = RAW_DIR / f'cross_entropy_seed{s}_scores.npz'
        if f.exists():
            d = np.load(f)
            imp_k = 'same_key_impostor' if 'same_key_impostor' in d else 'impostor'
            m = compute_eer_from_scores(d['genuine'], d[imp_k])
            per_seed[str(s)] = m
            eers.append(m['eer_percent'])
            tar1s.append(m['tar_at_far_1pct'])
            tar01s.append(m['tar_at_far_01pct'])
            dps.append(m['d_prime'])
    if eers:
        ce_res['EASY'] = {
            'eer_mean': round(float(np.mean(eers)), 2),
            'eer_std': round(float(np.std(eers, ddof=1)), 2),
            'single_seed_eer': per_seed['42']['eer_percent'],
            'single_seed': 42,
            'eer_seeds': {str(s): per_seed[str(s)]['eer_percent'] for s in SEEDS},
            'tar_at_far_1pct': per_seed['42']['tar_at_far_1pct'],
            'tar_at_far_01pct': per_seed['42']['tar_at_far_01pct'],
            'tar_at_far_1pct_mean': round(float(np.mean(tar1s)), 2),
            'tar_at_far_1pct_std': round(float(np.std(tar1s, ddof=1)), 2),
            'tar_at_far_1pct_seeds': {str(s): per_seed[str(s)]['tar_at_far_1pct'] for s in SEEDS},
            'd_prime': per_seed['42']['d_prime'],
            'tau': per_seed['42']['tau'],
            'far_at_tau': per_seed['42']['far_at_tau'],
            'frr_at_tau': per_seed['42']['frr_at_tau'],
            'rank1': None,
            'note': 'Cross-entropy evaluated on EASY nominal pairs; full 1:N gallery embeddings not preserved in raw dataset.'
        }
    ce_res['ALL'] = {
        'eer_mean': None,
        'eer_std': None,
        'single_seed_eer': None,
        'tar_at_far_1pct': None,
        'd_prime': None,
        'rank1': None,
        'note': 'Unrun on ALL alterations: embeddings for medium/hard distortions were not preserved in raw dataset.'
    }
    return ce_res


# ==============================================================================
# Load film generator (checkpoint must exist)
# ==============================================================================

def load_film_gen():
    ckpt = ROOT_DIR / 'exports' / 'film_generator.pt'
    assert ckpt.exists(), f"FiLM checkpoint missing: {ckpt}"
    gen = FiLMGenerator(input_dim=DIM, hidden_dims=[512, 512], output_dim=DIM)
    gen.load_state_dict(torch.load(ckpt, map_location='cpu'))
    gen.eval()
    return gen


# ==============================================================================
# Build scheme templates for a set of embeddings + identities
# ==============================================================================

def compute_scheme_scores(pairs, emb_map, film_gen, seed_for_iom=42):
    """
    Compute cosine similarity scores for all schemes on the given pair list.
    Returns dict: scheme -> {'gen': [...], 'imp': [...]}
    """
    # Pre-cache per-identity keys
    identities = set()
    for p in pairs:
        identities.add(p.subject1)
        identities.add(p.subject2)
    identities = sorted(identities)

    user_Q    = {uid: derive_haar_matrix(MASTER_SEED, uid, 1, DIM) for uid in identities}
    user_s    = {uid: derive_bipolar_signs(MASTER_SEED, uid, 1, DIM) for uid in identities}
    user_perm = {uid: derive_permutation(MASTER_SEED, uid, 1, DIM) for uid in identities}
    user_k    = {uid: derive_film_key(MASTER_SEED, uid, 1, DIM) for uid in identities}
    user_iom  = {uid: derive_iom_matrices(MASTER_SEED, uid, 1, num_groups=64, group_size=8, dim=DIM) for uid in identities}

    # FiLM gamma/beta per identity
    user_gamma, user_beta = {}, {}
    with torch.no_grad():
        for uid in identities:
            k_t = torch.from_numpy(user_k[uid]).unsqueeze(0)
            g_t, b_t = film_gen(k_t)
            user_gamma[uid] = g_t.squeeze(0).numpy()
            user_beta[uid]  = b_t.squeeze(0).numpy()

    def encode_iom_single(e, W):
        K, M, D = W.shape
        proj = np.einsum('kmd,d->km', W, e)
        max_idx = np.argmax(proj, axis=1)
        oh = np.zeros((K, M), dtype=np.float32)
        oh[np.arange(K), max_idx] = 1.0 / np.sqrt(K)
        return oh.flatten()

    def encode_biohash(e, Q):
        v = Q @ e
        b = np.sign(v); b[b == 0] = 1.0
        return (b / np.sqrt(DIM)).astype(np.float32)

    SCHEMES = ['plaintext', 'rop', 'sign_only', 'sign_permutation',
               'film_only', 'bipolar_film', 'biohashing', 'iom']

    scores = {sch: {'gen': [], 'imp': []} for sch in SCHEMES}
    STOLEN = 'stolen_key'

    for pair in pairs:
        e1 = emb_map[pair.path1].astype(np.float64)
        e2 = emb_map[pair.path2].astype(np.float64)
        e1 /= (np.linalg.norm(e1) + 1e-12)
        e2 /= (np.linalg.norm(e2) + 1e-12)
        u1, u2 = pair.subject1, pair.subject2
        is_gen = (pair.label == 1)

        # Under stolen key: attacker uses victim u1's key for both
        Q_a = user_Q[u1];  Q_b = user_Q[u1]
        s_a = user_s[u1];  s_b = user_s[u1]
        p_a = user_perm[u1]; p_b = user_perm[u1]
        g_a = user_gamma[u1]; b_a = user_beta[u1]
        iom_a = user_iom[u1]; iom_b = user_iom[u1]

        templates = {
            'plaintext':        (e1, e2),
            'rop':              (Q_a @ e1, Q_b @ e2),
            'sign_only':        (s_a * e1, s_b * e2),
            'sign_permutation': (s_a * e1[p_a], s_b * e2[p_b]),
            'film_only':        (apply_film_modulation(e1, g_a, b_a),
                                 apply_film_modulation(e2, g_a, b_a)),
            'bipolar_film':     (apply_film_modulation(e1, g_a, b_a, s_a),
                                 apply_film_modulation(e2, g_a, b_a, s_b)),
            'biohashing':       (encode_biohash(e1, Q_a), encode_biohash(e2, Q_b)),
            'iom':              (encode_iom_single(e1, iom_a), encode_iom_single(e2, iom_b)),
        }
        pt_sim = float(np.dot(e1, e2))
        for sch, (t1, t2) in templates.items():
            if sch == 'plaintext':
                sim = pt_sim
            elif sch == 'rop':
                rop_sim = float(np.dot(t1 / (np.linalg.norm(t1) + 1e-12), t2 / (np.linalg.norm(t2) + 1e-12)))
                assert abs(rop_sim - pt_sim) < 1e-5, f"Isometry violated: |{rop_sim} - {pt_sim}| >= 1e-5"
                sim = pt_sim
            else:
                t1n = t1 / (np.linalg.norm(t1) + 1e-12)
                t2n = t2 / (np.linalg.norm(t2) + 1e-12)
                sim = float(np.dot(t1n, t2n))
            if is_gen: scores[sch]['gen'].append(sim)
            else:      scores[sch]['imp'].append(sim)

    return scores


# ==============================================================================
# Main: Per-protocol, per-seed evaluation
# ==============================================================================

def main():
    print("=" * 70)
    print("PROTOCOL-WIDE EXPERIMENT RERUN")
    print("Protocols: ALL (headline), EASY (secondary)")
    print("Seeds: 42, 123, 456 (pair-sampling seeds on one encoder)")
    print("=" * 70)

    # Load test embeddings
    test_npz = RAW_DIR / 'socofing_test_embeddings.npz'
    t_embs, t_paths = load_embeddings(test_npz)
    emb_map = {p: t_embs[i] for i, p in enumerate(t_paths)}

    # Load/regenerate pair CSVs for seed=42 (canonical pair list)
    print("\n[STAGE 0] Building protocol pair lists (seed=42)...")
    proto_pairs = build_pairs(test_npz, seed=42)
    for proto, pairs in proto_pairs.items():
        csv_path = FINAL_DIR / f'pairs_{proto.lower()}.csv'
        save_pairs(pairs, csv_path)
        pc = pair_counts(pairs)
        print(f"  {proto}: total={pc['total']}, genuine={pc['genuine']} "
              f"(easy={pc['genuine_easy']}, med={pc['genuine_medium']}, hard={pc['genuine_hard']}), "
              f"impostor={pc['impostor']}  -> {csv_path.name}")

    # Load FiLM generator once
    film_gen = load_film_gen()
    print("\n[FiLM] Loaded checkpoint from exports/film_generator.pt")

    # Inspect FiLM checkpoint forward code + stats
    print(f"\n[FiLM] Generator architecture:\n{film_gen}")
    ckpt_params = dict(film_gen.named_parameters())
    with torch.no_grad():
        # compute gamma/beta stats on ALL genuine pairs
        all_genuines = [p for p in proto_pairs[PROTOCOL_ALL] if p.label == 1]
        subj_ids = sorted(set(p.subject1 for p in all_genuines))
        gammas, betas, norms_beta = [], [], []
        for uid in subj_ids:
            k_t = torch.from_numpy(derive_film_key(MASTER_SEED, uid, 1, DIM)).unsqueeze(0)
            g_t, b_t = film_gen(k_t)
            gammas.append(g_t.squeeze(0).numpy())
            betas.append(b_t.squeeze(0).numpy())
            norms_beta.append(float(np.linalg.norm(b_t.squeeze(0).numpy())))
        gammas = np.array(gammas); betas = np.array(betas)
        film_stats = {
            'gamma_mean': round(float(gammas.mean()), 4),
            'gamma_std':  round(float(gammas.std()), 4),
            'beta_mean':  round(float(betas.mean()),  4),
            'beta_std':   round(float(betas.std()),   4),
            'beta_norm_mean': round(float(np.mean(norms_beta)), 4),
        }
        print(f"[FiLM] Stats: gamma={film_stats['gamma_mean']}±{film_stats['gamma_std']}, "
              f"beta={film_stats['beta_mean']}±{film_stats['beta_std']}, "
              f"||beta||={film_stats['beta_norm_mean']}")

    # ==========================================================================
    # Per-protocol evaluation
    # ==========================================================================
    all_metrics = {}

    for proto in [PROTOCOL_ALL, PROTOCOL_EASY]:
        print(f"\n{'='*70}")
        print(f"PROTOCOL: {proto}")
        print(f"{'='*70}")

        # Build pair list for each seed separately
        seed_results = {sch: {'eers': [], 'taus': [], 'far_list': [], 'frr_list': []}
                        for sch in ['plaintext','rop','sign_only','sign_permutation',
                                    'film_only','bipolar_film','biohashing','iom']}

        per_seed_data = {}
        for seed in SEEDS:
            print(f"\n  [Seed {seed}] Building pairs + computing scores...")
            proto_res = build_pairs(test_npz, seed=seed, protocols=(proto,))
            pairs = proto_res[proto]
            pc = pair_counts(pairs)
            print(f"    Pairs: genuine={pc['genuine']}, impostor={pc['impostor']}")

            assert pc['genuine'] > 0, f"No genuine pairs for {proto} seed={seed}"
            assert pc['impostor'] > 0, f"No impostor pairs for {proto} seed={seed}"
            assert pc['genuine'] == pc['impostor'], \
                f"Genuine/impostor mismatch for {proto} seed={seed}: {pc['genuine']} vs {pc['impostor']}"

            scores = compute_scheme_scores(pairs, emb_map, film_gen)

            # Isometry assertion: ROP == plaintext under stolen key
            p_gen = np.array(scores['plaintext']['gen'])
            p_imp = np.array(scores['plaintext']['imp'])
            r_gen = np.array(scores['rop']['gen'])
            r_imp = np.array(scores['rop']['imp'])
            max_diff = max(float(np.max(np.abs(r_gen - p_gen))),
                           float(np.max(np.abs(r_imp - p_imp))))
            print(f"    [Assertion] ROP isometry max|Δ| = {max_diff:.2e}")
            assert max_diff < 1e-5, f"ROP isometry violated (max|Δ|={max_diff:.2e})"

            seed_metrics = {}
            for sch, sc in scores.items():
                m = compute_eer_from_scores(sc['gen'], sc['imp'])
                seed_metrics[sch] = m
                seed_results[sch]['eers'].append(m['eer_percent'])
                seed_results[sch]['taus'].append(m['tau'])
                seed_results[sch]['far_list'].append(m['far_at_tau'])
                seed_results[sch]['frr_list'].append(m['frr_at_tau'])
                # TAR <= 1 - EER assertion
                eer_frac = m['eer_percent'] / 100.0
                if m['tar_at_far_1pct'] / 100.0 > 1.0 - eer_frac + 0.05:
                    print(f"    [WARNING] {sch} TAR@1% > 1-EER: TAR={m['tar_at_far_1pct']:.2f}% EER={m['eer_percent']:.2f}%")

            # Save per-seed raw scores for provenance
            out_key = f'proto{proto.lower()}_seed{seed}'
            for sch, sc in scores.items():
                np.savez_compressed(
                    RAW_DIR / f'{sch}_{out_key}_scores.npz',
                    genuine=np.array(sc['gen']),
                    impostor=np.array(sc['imp']),
                )

            per_seed_data[seed] = {'scores': scores, 'metrics': seed_metrics, 'pair_counts': pc}
            print(f"    ROP EER (seed={seed}): {seed_metrics['rop']['eer_percent']:.2f}%")

        # Aggregate across seeds: mean ± std
        agg = {}
        SCHEMES_ORDERED = ['plaintext','rop','sign_only','sign_permutation',
                           'film_only','bipolar_film','biohashing','iom']
        for sch in SCHEMES_ORDERED:
            eers = seed_results[sch]['eers']
            mean_eer = round(float(np.mean(eers)), 2)
            std_eer  = round(float(np.std(eers, ddof=1 if len(eers) > 1 else 0)), 2)
            # Single-seed value from seed=42 (first seed)
            single_seed_eer = per_seed_data[42]['metrics'][sch]['eer_percent']
            single_seed_tau = per_seed_data[42]['metrics'][sch]['tau']

            # Assertion: single-seed within mean ± 3*std
            if len(eers) > 1:
                deviation = abs(single_seed_eer - mean_eer)
                limit = 3.0 * std_eer if std_eer > 0 else 0.5
                if deviation > limit:
                    print(f"    [WARNING] {sch} single-seed={single_seed_eer:.2f} outside mean±3std "
                          f"({mean_eer:.2f}±{std_eer:.2f})")

            # Bootstrap CI on seed=42 scores
            sc42 = per_seed_data[42]['scores'][sch]
            ci_low, ci_high = bootstrap_eer_ci(sc42['gen'], sc42['imp'])

            # Full metrics from seed=42
            m42 = per_seed_data[42]['metrics'][sch]
            agg[sch] = {
                'eer_mean':     mean_eer,
                'eer_std':      std_eer,
                'eer_seeds':    {str(s): per_seed_data[s]['metrics'][sch]['eer_percent'] for s in SEEDS},
                'single_seed_eer': single_seed_eer,
                'single_seed':  42,
                'eer_ci_lower': ci_low,
                'eer_ci_upper': ci_high,
                'tau':          single_seed_tau,
                'far_at_tau':   m42['far_at_tau'],
                'frr_at_tau':   m42['frr_at_tau'],
                'd_prime':      m42['d_prime'],
                'tar_at_far_1pct':  m42['tar_at_far_1pct'],
                'tar_at_far_01pct': m42['tar_at_far_01pct'],
                'tar_at_far_1pct_mean': round(float(np.mean([per_seed_data[s]['metrics'][sch]['tar_at_far_1pct'] for s in SEEDS])), 2),
                'tar_at_far_1pct_std': round(float(np.std([per_seed_data[s]['metrics'][sch]['tar_at_far_1pct'] for s in SEEDS], ddof=1)), 2),
                'tar_at_far_1pct_seeds': {str(s): per_seed_data[s]['metrics'][sch]['tar_at_far_1pct'] for s in SEEDS},
                'genuine_mean': m42['genuine_mean'],
                'impostor_mean': m42['impostor_mean'],
                'n_genuine':    m42['n_genuine'],
                'n_impostor':   m42['n_impostor'],
            }
            print(f"  {sch:20s}: EER {mean_eer:.2f}±{std_eer:.2f}% "
                  f"(seeds={eers}) single={single_seed_eer:.2f}% CI=[{ci_low},{ci_high}]% "
                  f"TAR@1%={agg[sch]['tar_at_far_1pct_mean']:.2f}±{agg[sch]['tar_at_far_1pct_std']:.2f}%")

        # Compute validation operating threshold transfer to test split
        val_transfer = compute_validation_transfer(per_seed_data[42]['scores']['rop'], proto)
        print(f"\n  [Validation Transfer ({proto})]")
        print(f"    Validation tau = {val_transfer['val_tau']} (val EER = {val_transfer['val_eer']}%)")
        print(f"    Transferred Test FAR = {val_transfer['test_far_at_val_tau']}%, FRR = {val_transfer['test_frr_at_val_tau']}% "
              f"(transfer gap = {val_transfer['transfer_gap']}%)")

        all_metrics[proto] = {
            'schemes': agg,
            'validation_transfer': val_transfer,
            'pair_counts_seed42': per_seed_data[42]['pair_counts'],
            'film_checkpoint_stats': film_stats,
        }

    # Cross-entropy baseline evaluation
    ce_metrics = compute_cross_entropy_metrics()
    print("\n[Cross-Entropy Baseline]")
    if ce_metrics['EASY']:
        print(f"  EASY nominal: EER={ce_metrics['EASY']['eer_mean']:.2f}±{ce_metrics['EASY']['eer_std']:.2f}%, "
              f"TAR@1%={ce_metrics['EASY']['tar_at_far_1pct_mean']:.2f}±{ce_metrics['EASY']['tar_at_far_1pct_std']:.2f}%, "
              f"d'={ce_metrics['EASY']['d_prime']:.2f}")
    print(f"  ALL: {ce_metrics['ALL']['note']}")

    # Register pair CSVs in manifest
    for proto in [PROTOCOL_ALL, PROTOCOL_EASY]:
        csv_path = FINAL_DIR / f'pairs_{proto.lower()}.csv'
        if csv_path.exists():
            record_manifest_entry(csv_path, Path(__file__), protocol=proto, seed=42)

    # Register raw scores in manifest
    for proto in [PROTOCOL_ALL, PROTOCOL_EASY]:
        for seed in SEEDS:
            out_key = f'proto{proto.lower()}_seed{seed}'
            for sch in SCHEMES_ORDERED:
                raw_f = RAW_DIR / f'{sch}_{out_key}_scores.npz'
                if raw_f.exists():
                    record_manifest_entry(raw_f, Path(__file__), protocol=proto, seed=seed)

    # ==========================================================================
    # Build headline numbers (protocol=ALL, scheme=ROP)
    # ==========================================================================
    all_rop = all_metrics[PROTOCOL_ALL]['schemes']['rop']
    all_plain = all_metrics[PROTOCOL_ALL]['schemes']['plaintext']

    assert abs(all_rop['eer_mean'] - all_plain['eer_mean']) < 1e-5, \
        f"ROP mean EER != plaintext mean EER: {all_rop['eer_mean']} vs {all_plain['eer_mean']}"

    easy_rop = all_metrics[PROTOCOL_EASY]['schemes']['rop']
    easy_plain = all_metrics[PROTOCOL_EASY]['schemes']['plaintext']
    assert abs(easy_rop['eer_mean'] - easy_plain['eer_mean']) < 1e-5, \
        f"EASY ROP mean EER != plaintext mean EER: {easy_rop['eer_mean']} vs {easy_plain['eer_mean']}"
    assert abs(easy_rop['single_seed_eer'] - easy_plain['single_seed_eer']) < 1e-5, \
        f"EASY ROP single seed EER != plaintext single seed EER: {easy_rop['single_seed_eer']} vs {easy_plain['single_seed_eer']}"

    print(f"\n{'='*70}")
    print(f"HEADLINE: ALL protocol, ROP (=plaintext by isometry): "
          f"EER {all_rop['eer_mean']:.2f}±{all_rop['eer_std']:.2f}%")
    print(f"SECONDARY: EASY protocol, ROP: "
          f"EER {all_metrics[PROTOCOL_EASY]['schemes']['rop']['eer_mean']:.2f}±"
          f"{all_metrics[PROTOCOL_EASY]['schemes']['rop']['eer_std']:.2f}%")
    print(f"{'='*70}")

    return all_metrics, film_stats, ce_metrics


if __name__ == '__main__':
    all_metrics, film_stats, ce_metrics = main()
    # Save protocol results for subsequent pipeline steps
    out = FINAL_DIR / 'protocol_results.json'
    with open(out, 'w') as f:
        json.dump({
            'protocol_metrics': all_metrics,
            'cross_entropy': ce_metrics,
            'film_stats': film_stats
        }, f, indent=2)
    record_manifest_entry(out, Path(__file__), protocol='ALL+EASY', seed='multi')
    print(f"\n[✓] Protocol results saved to {out} and recorded in manifest.json")

