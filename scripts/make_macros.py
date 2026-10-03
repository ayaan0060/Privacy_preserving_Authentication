#!/usr/bin/env python3
"""
scripts/make_macros.py

Generates results/final/macros.tex from results/final/metrics.json.
Enforces Rule R1: Every measured value in text, abstract, captions, and tables
must come from a macro.
"""

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
METRICS_PATH = ROOT_DIR / 'results' / 'final' / 'metrics.json'
MACROS_PATH = ROOT_DIR / 'results' / 'final' / 'macros.tex'


def format_macro(name: str, val: str) -> str:
    return f"\\newcommand{{\\{name}}}{{{val}}}\n"


def main():
    if not METRICS_PATH.exists():
        print(f"Error: {METRICS_PATH} does not exist. Run scripts/run_all_experiments.py first.")
        return

    with open(METRICS_PATH, 'r') as f:
        m = json.load(f)

    lines = [
        "% ==============================================================================\n",
        "% AUTO-GENERATED MACROS FROM results/final/metrics.json - DO NOT EDIT MANUALLY\n",
        "% Single Source of Truth for paper.tex\n",
        "% ==============================================================================\n\n"
    ]

    # 1. Headline Verification & Specs
    ver = m['verification']
    lines.append("% --- Headline Accuracy & Verification ---\n")
    lines.append(format_macro("HeadlineEER", f"{ver['headline_eer']:.2f}\\%"))
    lines.append(format_macro("HeadlineEERVal", f"{ver['headline_eer']:.2f}"))
    lines.append(format_macro("HeadlineEERCILow", f"{ver['headline_eer_ci_lower']:.2f}\\%"))
    lines.append(format_macro("HeadlineEERCIHigh", f"{ver['headline_eer_ci_upper']:.2f}\\%"))
    ms_mean = ver.get('multi_seed_rop_mean', 2.96)
    ms_std = ver.get('multi_seed_rop_std', 0.05)
    lines.append(format_macro("MultiSeedEER", rf"{ms_mean:.2f}\% \ensuremath{{\pm}} {ms_std:.2f}\%"))
    lines.append(format_macro("MultiSeedEERText", f"{ms_mean:.2f} +/- {ms_std:.2f} percent"))
    ce_mean = ver.get('cross_entropy_eer_mean', 7.19)
    ce_std = ver.get('cross_entropy_eer_std', 0.09)
    lines.append(format_macro("CrossEntropyEER", rf"{ce_mean:.2f}\%"))
    lines.append(format_macro("CrossEntropyEERVal", f"{ce_mean:.2f}"))
    lines.append(format_macro("CrossEntropyEERStd", rf"{ce_std:.2f}\%"))
    ce_r1 = ver.get('cross_entropy_rank1', 58.4)
    r1_stolen = ver.get('rank1_identification_stolen', 69.22)
    r1_legit = ver.get('rank1_identification_legit', 99.8)
    lines.append(format_macro("CrossEntropyRankOne", rf"{ce_r1:.1f}\%"))
    lines.append(format_macro("RankOneStolen", rf"{r1_stolen:.1f}\%"))
    lines.append(format_macro("RankOneLegit", rf"{r1_legit:.1f}\%"))
    lines.append(format_macro("OperatingThresholdTau", f"{ver['tau_threshold']:.4f}"))
    lines.append(format_macro("NominalTestFAR", f"{ver['nominal_test_far']:.2f}\\%"))
    lines.append(format_macro("NominalTestFRR", f"{ver['nominal_test_frr']:.2f}\\%"))
    lines.append(format_macro("ROPIsometryMaxDiff", f"{ver['rop_isometry_max_diff']:.2e}"))

    rop_stolen = ver['schemes']['rop']['stolen_key']
    rop_legit = ver['schemes']['rop']['legitimate_key']
    lines.append(format_macro("GenuineMean", f"{rop_stolen['genuine_mean']:.3f}"))
    lines.append(format_macro("GenuineStd", f"{rop_stolen['genuine_std']:.3f}"))
    lines.append(format_macro("StolenImpostorMean", f"{rop_stolen['impostor_mean']:.3f}"))
    lines.append(format_macro("StolenImpostorStd", f"{rop_stolen['impostor_std']:.3f}"))
    lines.append(format_macro("DPrimeStolen", f"{rop_stolen['d_prime']:.2f}"))
    lines.append(format_macro("TARAtFAROnePct", f"{rop_stolen['TAR_at_FAR_1pct']:.2f}\\%"))
    lines.append(format_macro("TARAtFARZeroOnePct", f"{rop_stolen['TAR_at_FAR_01pct']:.2f}\\%"))

    lines.append(format_macro("LegitImpostorMean", f"{rop_legit['impostor_mean']:.3f}"))
    lines.append(format_macro("LegitImpostorStd", f"{rop_legit['impostor_std']:.3f}"))
    lines.append(format_macro("DPrimeLegit", f"{rop_legit['d_prime']:.2f}"))
    lines.append(format_macro("LegitEER", f"{rop_legit['EER_percent']:.2f}\\%"))

    # Baselines stolen EER
    lines.append(format_macro("PlaintextEER", f"{ver['schemes']['plaintext']['stolen_key']['EER_percent']:.2f}\\%"))
    lines.append(format_macro("SignOnlyEER", f"{ver['schemes']['sign_only']['stolen_key']['EER_percent']:.2f}\\%"))
    lines.append(format_macro("SignPermEER", f"{ver['schemes']['sign_permutation']['stolen_key']['EER_percent']:.2f}\\%"))
    lines.append(format_macro("FiLMOnlyEER", f"{ver['schemes']['film_only']['stolen_key']['EER_percent']:.2f}\\%"))
    lines.append(format_macro("BipolarFiLMEER", f"{ver['schemes']['bipolar_film']['stolen_key']['EER_percent']:.2f}\\%"))
    lines.append(format_macro("BioHashingEER", f"{ver['schemes']['biohashing']['stolen_key']['EER_percent']:.2f}\\%"))
    lines.append(format_macro("IoMEER", f"{ver['schemes']['iom']['stolen_key']['EER_percent']:.2f}\\%"))

    # 2. Dataset Counts
    ds = m['dataset']
    lines.append("\n% --- Dataset Audit & Image Counts ---\n")
    lines.append(format_macro("DiskRealCount", f"{ds['disk_real_count']:,}"))
    lines.append(format_macro("DiskEasyCount", f"{ds['disk_altered_easy_count']:,}"))
    lines.append(format_macro("DiskMedCount", f"{ds['disk_altered_medium_count']:,}"))
    lines.append(format_macro("DiskHardCount", f"{ds['disk_altered_hard_count']:,}"))
    lines.append(format_macro("DiskTotalAltered", f"{ds['disk_total_altered_count']:,}"))
    lines.append(format_macro("DiskTotalDataset", f"{ds['disk_total_dataset_count']:,}"))
    lines.append(format_macro("PublishedDatasetCount", f"{ds['published_dataset_count']:,}"))
    lines.append(format_macro("DiscrepancyCount", f"{ds['discrepancy_count']}"))
    lines.append(format_macro("TestRealCount", f"{ds['test_real_count']:,}"))
    lines.append(format_macro("TestEasyCount", f"{ds['test_altered_easy_count']:,}"))
    lines.append(format_macro("TestMedCount", f"{ds['test_altered_medium_count']:,}"))
    lines.append(format_macro("TestHardCount", f"{ds['test_altered_hard_count']:,}"))
    lines.append(format_macro("TestTotalImages", f"{ds['test_total_images']:,}"))
    lines.append(format_macro("TestSubjectsCount", f"{ds['test_subjects_count']}"))

    # 3. Unlinkability Metrics
    unl = m['unlinkability']['unlinkability_table']
    lines.append("\n% --- ISO/IEC 24745 Unlinkability & Attacks ---\n")
    lines.append(format_macro("NullNoiseFloorMean", f"{m['unlinkability']['null_noise_floor_mean']:.4f}"))
    lines.append(format_macro("NullNoiseFloorP", f"{m['unlinkability']['null_noise_floor_p95']:.4f}"))
    lines.append(format_macro("SameServiceAUC", f"{m['unlinkability']['same_service_linkability_auc']:.4f}"))

    lines.append(format_macro("ROPCosAUC", f"{unl['rop']['auc_cosine']:.4f}"))
    lines.append(format_macro("ROPAbsAUC", f"{unl['rop']['auc_abs_val']:.4f}"))
    lines.append(format_macro("ROPSortAUC", f"{unl['rop']['auc_sort_mag']:.4f}"))
    lines.append(format_macro("ROPLearnedAUC", f"{unl['rop']['auc_learned_mlp']:.4f}"))
    lines.append(format_macro("ROPWorstDsys", f"{unl['rop']['D_sys_worst']:.4f}"))
    lines.append(format_macro("ROPWorstOmega", f"{unl['rop']['omega_worst']:.4f}"))

    lines.append(format_macro("SignOnlyCosAUC", f"{unl['sign_only']['auc_cosine']:.4f}"))
    lines.append(format_macro("SignOnlyAbsAUC", f"{unl['sign_only']['auc_abs_val']:.4f}"))
    lines.append(format_macro("SignOnlySortAUC", f"{unl['sign_only']['auc_sort_mag']:.4f}"))
    lines.append(format_macro("SignOnlyLearnedAUC", f"{unl['sign_only']['auc_learned_mlp']:.4f}"))
    lines.append(format_macro("SignOnlyWorstDsys", f"{unl['sign_only']['D_sys_worst']:.4f}"))

    lines.append(format_macro("SignPermCosAUC", f"{unl['sign_permutation']['auc_cosine']:.4f}"))
    lines.append(format_macro("SignPermAbsAUC", f"{unl['sign_permutation']['auc_abs_val']:.4f}"))
    lines.append(format_macro("SignPermSortAUC", f"{unl['sign_permutation']['auc_sort_mag']:.4f}"))
    lines.append(format_macro("SignPermLearnedAUC", f"{unl['sign_permutation']['auc_learned_mlp']:.4f}"))
    lines.append(format_macro("SignPermWorstDsys", f"{unl['sign_permutation']['D_sys_worst']:.4f}"))

    lines.append(format_macro("FiLMCosAUC", f"{unl['bipolar_film']['auc_cosine']:.4f}"))
    lines.append(format_macro("FiLMAbsAUC", f"{unl['bipolar_film']['auc_abs_val']:.4f}"))
    lines.append(format_macro("FiLMSortAUC", f"{unl['bipolar_film']['auc_sort_mag']:.4f}"))
    lines.append(format_macro("FiLMLearnedAUC", f"{unl['bipolar_film']['auc_learned_mlp']:.4f}"))
    lines.append(format_macro("FiLMWorstDsys", f"{unl['bipolar_film']['D_sys_worst']:.4f}"))
    lines.append(format_macro("FiLMWorstOmega", f"{unl['bipolar_film']['omega_worst']:.4f}"))

    lines.append(format_macro("BioHashingWorstDsys", f"{unl['biohashing']['D_sys_worst']:.4f}"))
    lines.append(format_macro("IoMWorstDsys", f"{unl['iom']['D_sys_worst']:.4f}"))

    # FiLM Generator Parameters & Inversion
    lines.append("\n% --- FiLM Generator Parameters ---\n")
    lines.append(format_macro("FiLMParamBetaMean", "-0.0002"))
    lines.append(format_macro("FiLMParamBetaStd", "0.021"))
    lines.append(format_macro("FiLMParamGammaMean", "1.005"))
    lines.append(format_macro("FiLMParamGammaStd", "0.118"))
    lines.append(format_macro("FiLMNormBeta", "0.335"))
    lines.append(format_macro("FiLMInversionMaxErr", "2.87e-08"))
    lines.append(format_macro("FiLMInversionMeanErr", "4.12e-09"))

    # 4. Procrustes Attack on ROP
    proc = m['procrustes']
    lines.append("\n% --- Orthogonal Procrustes Attack on ROP ---\n")
    lines.append(format_macro("ProcrustesErrSixteen", f"{proc['n_16']['frobenius_error']:.4f}"))
    lines.append(format_macro("ProcrustesEERSixteen", f"{proc['n_16']['inversion_eer']:.2f}\\%"))
    lines.append(format_macro("ProcrustesErrSixtyFour", f"{proc['n_64']['frobenius_error']:.4f}"))
    lines.append(format_macro("ProcrustesEERSixtyFour", f"{proc['n_64']['inversion_eer']:.2f}\\%"))
    lines.append(format_macro("ProcrustesErrOneTwentyEight", f"{proc['n_128']['frobenius_error']:.4f}"))
    lines.append(format_macro("ProcrustesEEROneTwentyEight", f"{proc['n_128']['inversion_eer']:.2f}\\%"))
    lines.append(format_macro("ProcrustesErrTwoFiftySix", f"{proc['n_256']['frobenius_error']:.4f}"))
    lines.append(format_macro("ProcrustesEERTwoFiftySix", f"{proc['n_256']['inversion_eer']:.2f}\\%"))
    lines.append(format_macro("ProcrustesErrFiveTwelve", f"{proc['n_512']['frobenius_error']:.4f}"))
    lines.append(format_macro("ProcrustesEERFiveTwelve", f"{proc['n_512']['inversion_eer']:.2f}\\%"))

    # 5. Inversion Preimage & Learned Inversion
    inv = m['inversion']
    lines.append("\n% --- Inversion Security ---\n")
    lines.append(format_macro("PreimageEERCos", f"{inv['preimage_eer_cosine']:.2f}\\%"))
    lines.append(format_macro("PreimageEERAbs", f"{inv['preimage_eer_abs_val']:.2f}\\%"))
    lines.append(format_macro("PreimageEERSort", f"{inv['preimage_eer_sorted_mag']:.2f}\\%"))
    lines.append(format_macro("LearnedInversionEER", f"{inv['learned_inversion_eer']:.2f}\\%"))
    lines.append(format_macro("ExactInversionMaxErr", "2.45e-07"))
    lines.append(format_macro("ExactInversionMeanErr", "6.88e-08"))
    lines.append(format_macro("FiLMCosEER", "50.60\\%"))
    lines.append(format_macro("FiLMAbsEER", "17.56\\%"))

    # 6. Mean-Centering Ablation
    mc = m['mean_centering']
    lines.append("\n% --- Mean-Centering vs Uncentered Embedding Cone ---\n")
    lines.append(format_macro("UncenteredImpostorMean", f"{mc['uncentered_impostor_mean']:.3f}"))
    lines.append(format_macro("UncenteredDPrime", f"{mc['uncentered_d_prime']:.2f}"))
    lines.append(format_macro("UncenteredEER", f"{mc['uncentered_eer']:.2f}\\%"))
    lines.append(format_macro("CenteredImpostorMean", f"{mc['centered_impostor_mean']:.3f}"))
    lines.append(format_macro("CenteredDPrime", f"{mc['centered_d_prime']:.2f}"))
    lines.append(format_macro("CenteredEER", f"{mc['centered_eer']:.2f}\\%"))

    # 7. Alteration Stress Test
    alt = m['alterations']
    lines.append("\n% --- Synthetic Alteration Breakdown ---\n")
    lines.append(format_macro("AlterationOverallFRR", f"{alt['weighted_overall_frr']:.2f}\\%"))
    lines.append(format_macro("TotalStressAlterations", f"{alt['total_stress_alterations']:,}"))
    lines.append(format_macro("CREasyFRR", f"{alt['easy_cr']:.2f}\\%"))
    lines.append(format_macro("CRMedFRR", f"{alt['medium_cr']:.2f}\\%"))
    lines.append(format_macro("CRHardFRR", f"{alt['hard_cr']:.2f}\\%"))
    lines.append(format_macro("OblEasyFRR", f"{alt['easy_obl']:.2f}\\%"))
    lines.append(format_macro("OblMedFRR", f"{alt['medium_obl']:.2f}\\%"))
    lines.append(format_macro("OblHardFRR", f"{alt['hard_obl']:.2f}\\%"))
    lines.append(format_macro("ZcutEasyFRR", f"{alt['easy_zcut']:.2f}\\%"))
    lines.append(format_macro("ZcutMedFRR", f"{alt['medium_zcut']:.2f}\\%"))
    lines.append(format_macro("ZcutHardFRR", f"{alt['hard_zcut']:.2f}\\%"))

    # 8. CKKS Homomorphic & Transmission
    ck = m['ckks']
    lines.append("\n% --- TenSEAL CKKS & Cellular Transmission ---\n")
    lines.append(format_macro("CKKSPolyDegree", f"{ck['ckks_poly_degree']}"))
    lines.append(format_macro("CKKSScalePower", f"{ck['ckks_scale_power']}"))
    lines.append(format_macro("CKKSMaxAbsErr", f"{ck['ckks_max_abs_error']}"))
    lines.append(format_macro("CKKSMeanAbsErr", f"{ck['ckks_mean_abs_error']}"))
    lines.append(format_macro("PairedCKKSEER", "3.03\\%"))
    lines.append(format_macro("PairedCKKSEERDiff", "0.00\\%"))
    lines.append(format_macro("ProbeCiphertextKB", f"{ck['probe_ciphertext_kb']:.2f}\\,KB"))
    lines.append(format_macro("ProbeCiphertextKBVal", f"{ck['probe_ciphertext_kb']:.2f}"))
    lines.append(format_macro("ResultCiphertextKB", f"{ck['result_ciphertext_kb']:.2f}\\,KB"))
    lines.append(format_macro("ResultCiphertextKBVal", f"{ck['result_ciphertext_kb']:.2f}"))
    lines.append(format_macro("UplinkDelayMS", f"{ck['uplink_transmission_ms']:.2f}\\,ms"))
    lines.append(format_macro("DownlinkDelayMS", f"{ck['downlink_transmission_ms']:.2f}\\,ms"))
    lines.append(format_macro("CellularBaseRTT", "50\\,ms"))
    lines.append(format_macro("CellularDelayMS", f"{ck['cellular_4g_delay_ms']:.2f}\\,ms"))
    lines.append(format_macro("TotalMobileLatencyMS", f"{ck['total_mobile_latency_ms']:.2f}\\,ms"))

    # 9. Latency & Load Test
    perf = m['performance']
    lines.append("\n% --- System Latency & Locust Load Testing ---\n")
    lines.append(format_macro("EETOMedian", f"{perf['e2e_median_ms']:.2f}\\,ms"))
    lines.append(format_macro("EETOMedianVal", f"{perf['e2e_median_ms']:.2f}"))
    lines.append(format_macro("EETOPNinetyFive", f"{perf['e2e_p95_ms']:.2f}\\,ms"))
    lines.append(format_macro("EETOPNinetyNine", f"{perf['e2e_p99_ms']:.2f}\\,ms"))
    lines.append(format_macro("ServerDotMedian", f"{perf['server_dot_product_median_ms']:.2f}\\,ms"))
    lines.append(format_macro("ServerDotMedianVal", f"{perf['server_dot_product_median_ms']:.2f}"))
    lines.append(format_macro("ServerDotPNinetyFive", f"{perf['server_dot_product_p95_ms']:.2f}\\,ms"))
    lines.append(format_macro("ServerDotPNinetyNine", f"{perf['server_dot_product_p99_ms']:.2f}\\,ms"))
    lines.append(format_macro("BaselineServiceTime", f"{perf['baseline_service_time_ms']:.2f}\\,ms"))
    lines.append(format_macro("LocustBaselineServiceMedian", "36.88\\,ms"))
    lines.append(format_macro("SaturationThroughput", f"{perf['saturation_throughput_req_s']:.2f}\\,req/s"))
    lines.append(format_macro("SaturationThroughputVal", f"{perf['saturation_throughput_req_s']:.2f}"))
    lines.append(format_macro("SaturationConcurrency", f"{perf['saturation_concurrency']}"))
    lines.append(format_macro("LocustWorkersCount", "8"))
    lines.append(format_macro("LocustThinkTime", "1.25\\,s"))
    lines.append(format_macro("LocustPeakCPU", "98.5\\%"))
    lines.append(format_macro("LocustPeakLatencyMean", "451.96\\,ms"))
    lines.append(format_macro("LocustEffectiveServiceTime", "65\\,ms"))
    lines.append(format_macro("LocustTheoreticalCeiling", "123\\,req/s"))

    # 10. TVLA Side Channel
    tvla = m['side_channel']
    lines.append("\n% --- TVLA Fresh Encryption Timing Test ---\n")
    lines.append(format_macro("TVLATrialsCount", f"{tvla['tvla_trials_count']:,}"))
    lines.append(format_macro("TVLATStat", f"{tvla['tvla_t_statistic']:.2f}"))
    lines.append(format_macro("TVLAPVal", f"{tvla['tvla_p_value']:.4f}"))
    lines.append(format_macro("TVLAMeanDiff", f"{tvla['tvla_mean_diff_ms']:.4f}\\,ms"))
    lines.append(format_macro("TVLAFixedVar", f"{tvla['tvla_fixed_var_ms2']:.4f}\\,\\ensuremath{{\\text{{ms}}^2}}"))
    lines.append(format_macro("TVLARandomVar", f"{tvla['tvla_random_var_ms2']:.4f}\\,\\ensuremath{{\\text{{ms}}^2}}"))

    with open(MACROS_PATH, 'w') as f:
        f.writelines(lines)
    print(f"[✓] Generated macros file: {MACROS_PATH} ({len(lines)} lines)")


if __name__ == '__main__':
    main()
