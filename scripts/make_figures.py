#!/usr/bin/env python3
"""
scripts/make_figures.py

Generates publication-quality vector PDF figures into figures/ from results/final/:
1. figures/roc_curve.pdf: ROC curves (TAR vs log10 FAR)
2. figures/det_curve.pdf: DET curves (log10 FRR vs log10 FAR, independently computed)
3. figures/score_distributions.pdf: Score histograms of genuine, stolen-key, and legit-key impostor with tau
4. figures/film_param_distributions.pdf: FiLM gamma and beta parameter distributions
"""

from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json

ROOT_DIR = Path(__file__).resolve().parent.parent
FINAL_DIR = ROOT_DIR / 'results' / 'final'
RAW_DIR = ROOT_DIR / 'results' / 'raw'
FIG_DIR = ROOT_DIR / 'figures'
FIG_DIR.mkdir(parents=True, exist_ok=True)
METRICS_PATH = FINAL_DIR / 'metrics.json'

# Styling for IEEE Transactions / Conference format (single column width ~3.45 inches)
plt.rcParams.update({
    'font.size': 8,
    'axes.labelsize': 8.5,
    'axes.titlesize': 9,
    'xtick.labelsize': 7.5,
    'ytick.labelsize': 7.5,
    'legend.fontsize': 7,
    'figure.titlesize': 9,
    'font.family': 'sans-serif',
    'lines.linewidth': 1.4,
    'grid.linewidth': 0.5,
    'grid.alpha': 0.4,
    'pdf.fonttype': 42,
    'ps.fonttype': 42
})


def plot_roc_and_det(m):
    print("Generating ROC and DET curves from results/final/...")
    schemes_to_plot = [
        ('plaintext', 'stolen_key', 'ResNet-18 ArcFace (Plaintext)', '#0275d8', '-'),
        ('rop', 'stolen_key', 'ROP Stolen-Key (Adopted Primary)', '#d9534f', '--'),
        ('bipolar_film', 'stolen_key', 'Bipolar FiLM Stolen-Key', '#f0ad4e', '-.'),
        ('biohashing', 'stolen_key', 'BioHashing ($M=256$)', '#6f42c1', ':'),
        ('rop', 'legitimate_key', 'ROP Legitimate-Key Mode', '#5cb85c', '-')
    ]

    fig_roc, ax_roc = plt.subplots(figsize=(3.45, 2.7))
    fig_det, ax_det = plt.subplots(figsize=(3.45, 2.7))

    for sch, mode, label, color, ls in schemes_to_plot:
        data = np.load(FINAL_DIR / f"{sch}_{mode}_scores.npz")
        gen = data['genuine']
        imp = data['impostor']

        all_scores = np.concatenate([gen, imp])
        thresholds = np.linspace(np.min(all_scores) - 1e-4, np.max(all_scores) + 1e-4, 3000)

        far_list, frr_list = [], []
        n_gen, n_imp = len(gen), len(imp)

        for th in thresholds:
            far = np.sum(imp >= th) / n_imp
            frr = np.sum(gen < th) / n_gen
            far_list.append(far)
            frr_list.append(frr)

        far_arr = np.array(far_list)
        frr_arr = np.array(frr_list)
        tpr_arr = 1.0 - frr_arr

        valid_roc = far_arr > 1e-5
        ax_roc.plot(far_arr[valid_roc], tpr_arr[valid_roc], label=label, color=color, linestyle=ls)

        valid_det = (far_arr > 1e-5) & (frr_arr > 1e-5)
        ax_det.plot(far_arr[valid_det], frr_arr[valid_det], label=label, color=color, linestyle=ls)

    ax_roc.set_xscale('log')
    ax_roc.set_xlim(1e-4, 1.0)
    ax_roc.set_ylim(0.85, 1.005)
    ax_roc.set_xlabel('False Accept Rate (FAR, log scale)')
    ax_roc.set_ylabel('True Accept Rate (TAR)')
    ax_roc.set_title('ROC Curves (SOCOFing Benchmark)')
    ax_roc.grid(True, which='both', linestyle=':')
    ax_roc.legend(loc='lower right', framealpha=0.9)
    fig_roc.tight_layout()
    fig_roc.savefig(FIG_DIR / 'roc_curve.pdf', dpi=300)
    plt.close(fig_roc)

    ax_det.set_xscale('log')
    ax_det.set_yscale('log')
    ax_det.set_xlim(1e-4, 1.0)
    ax_det.set_ylim(1e-4, 1.0)
    ax_det.set_xlabel('False Accept Rate (FAR, log scale)')
    ax_det.set_ylabel('False Reject Rate (FRR, log scale)')
    ax_det.set_title('DET Curves (SOCOFing Benchmark)')
    ax_det.grid(True, which='both', linestyle=':')
    ax_det.legend(loc='upper right', framealpha=0.9)
    fig_det.tight_layout()
    fig_det.savefig(FIG_DIR / 'det_curve.pdf', dpi=300)
    plt.close(fig_det)

    print("  [✓] Generated roc_curve.pdf and det_curve.pdf")


def plot_score_distributions(m):
    print("Generating score_distributions.pdf from results/final/...")
    rop_s = np.load(FINAL_DIR / "rop_stolen_key_scores.npz")
    rop_l = np.load(FINAL_DIR / "rop_legitimate_key_scores.npz")

    gen = rop_s['genuine']
    imp_stolen = rop_s['impostor']
    imp_legit = rop_l['impostor']
    tau = m['verification']['tau_threshold']

    fig, ax = plt.subplots(figsize=(3.45, 2.7))
    bins = np.linspace(-0.3, 1.02, 120)

    ax.hist(imp_legit, bins=bins, density=True, alpha=0.5, color='#6f42c1', label=f'Legit-Key Impostor ($\\mu={imp_legit.mean():.2f}$)')
    ax.hist(imp_stolen, bins=bins, density=True, alpha=0.5, color='#f0ad4e', label=f'Stolen-Key Impostor ($\\mu={imp_stolen.mean():.2f}$)')
    ax.hist(gen, bins=bins, density=True, alpha=0.6, color='#5cb85c', label=f'Genuine Pairs ($\\mu={gen.mean():.2f}$)')

    ax.axvline(tau, color='#d9534f', linestyle='--', linewidth=1.5, label=f'Threshold $\\tau = {tau:.4f}$')

    ax.set_yscale('log')
    ax.set_ylim(1e-2, 50.0)
    ax.set_xlim(-0.35, 1.05)
    ax.set_xlabel('Cosine Similarity Score')
    ax.set_ylabel('Probability Density (log scale)')
    ax.set_title('Verification Score Distributions')
    ax.grid(True, which='both', linestyle=':')
    ax.legend(loc='upper left', framealpha=0.9, fontsize=6.5)

    fig.tight_layout()
    fig.savefig(FIG_DIR / 'score_distributions.pdf', dpi=300)
    plt.close(fig)
    print("  [✓] Generated score_distributions.pdf")


def plot_film_params():
    print("Generating film_param_distributions.pdf...")
    film_file = RAW_DIR / "film_params_seed42.npz"
    if not film_file.exists():
        print("  Warning: film_params_seed42.npz not found, skipping film params plot.")
        return

    data = np.load(film_file)
    gamma = data['gamma']
    beta = data['beta']

    fig, ax = plt.subplots(figsize=(3.45, 2.7))
    bins_g = np.linspace(0.4, 1.8, 80)
    bins_b = np.linspace(-0.15, 0.15, 80)

    ax.hist(gamma, bins=bins_g, density=True, alpha=0.6, color='#e83e8c', label=f'Scale $\\gamma_i$ ($\\mu={gamma.mean():.3f}, \\sigma={gamma.std():.3f}$)')
    ax.hist(beta, bins=bins_b, density=True, alpha=0.6, color='#17a2b8', label=f'Shift $\\beta_i$ ($\\mu={beta.mean():.4f}, \\sigma={beta.std():.3f}$)')

    ax.set_xlabel('Parameter Value')
    ax.set_ylabel('Probability Density')
    ax.set_title('FiLM Conditioning Generator Output Distributions')
    ax.grid(True, linestyle=':')
    ax.legend(loc='upper right', framealpha=0.9)

    fig.tight_layout()
    fig.savefig(FIG_DIR / 'film_param_distributions.pdf', dpi=300)
    plt.close(fig)
    print("  [✓] Generated film_param_distributions.pdf")


def main():
    with open(METRICS_PATH, 'r') as f:
        m = json.load(f)
    plot_roc_and_det(m)
    plot_score_distributions(m)
    plot_film_params()
    print("[✓] All PDF figures generated in figures/!")


if __name__ == '__main__':
    main()
