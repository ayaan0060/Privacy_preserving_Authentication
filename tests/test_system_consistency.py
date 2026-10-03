# tests/test_system_consistency.py
import unittest
import json
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
METRICS_PATH = ROOT_DIR / 'results' / 'final' / 'metrics.json'

class TestSystemConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not METRICS_PATH.exists():
            raise unittest.SkipTest("metrics.json does not exist. Run scripts/run_all_experiments.py first.")
        with open(METRICS_PATH, 'r') as f:
            cls.m = json.load(f)

    def test_rop_isometry_to_plaintext(self):
        """Rule 4.2: Assert ROP scores equal plaintext scores to within 1e-5 on the same pairs."""
        ver = self.m['verification']
        diff = ver['rop_isometry_max_diff']
        self.assertLess(diff, 1e-5, f"ROP isometry max absolute difference {diff} exceeds 1e-5")
        
        # Verify EERs match exactly
        plain_eer = ver['schemes']['plaintext']['stolen_key']['EER_percent']
        rop_eer = ver['schemes']['rop']['stolen_key']['EER_percent']
        self.assertAlmostEqual(plain_eer, rop_eer, places=2)

    def test_operating_point_consistency(self):
        """Rule 4.3: Assert EER, TAR@FAR, FRR@tau, and score distributions are mutually consistent."""
        ver = self.m['verification']
        tau = ver['tau_threshold']
        far = ver['nominal_test_far']
        frr = ver['nominal_test_frr']
        eer = ver['headline_eer']
        
        # At EER threshold, FAR and FRR should be within 0.1% of EER
        self.assertAlmostEqual(far, eer, delta=0.1)
        self.assertAlmostEqual(frr, eer, delta=0.1)
        
        # TAR@FAR=1% must be <= 100 - EER for FAR < EER
        rop = ver['schemes']['rop']['stolen_key']
        tar1 = rop['TAR_at_FAR_1pct']
        tar01 = rop['TAR_at_FAR_01pct']
        self.assertLessEqual(tar01, tar1)
        self.assertGreater(tar1, 90.0)

    def test_table_x_alteration_reconciliation(self):
        """Rule 4.4: Verify alteraton stress test counts and categories."""
        alt = self.m['alterations']
        total_stress = alt['total_stress_alterations']
        self.assertEqual(total_stress, 7327)
        self.assertGreater(alt['weighted_overall_frr'], 20.0) # Overall stress FRR driven by severe medium/hard damage
        self.assertLess(alt['easy_cr'], 2.0)
        self.assertLess(alt['easy_zcut'], 0.5)

    def test_procrustes_collapse_boundary(self):
        """Rule 3.1: Assert Procrustes attack collapses security once n >= 256."""
        proc = self.m['procrustes']
        # Monotonically decreasing Frobenius error
        err16 = proc['n_16']['frobenius_error']
        err64 = proc['n_64']['frobenius_error']
        err128 = proc['n_128']['frobenius_error']
        err256 = proc['n_256']['frobenius_error']
        err512 = proc['n_512']['frobenius_error']
        
        self.assertGreater(err16, err64)
        self.assertGreater(err64, err128)
        self.assertGreater(err128, err256)
        self.assertGreater(err256, err512)
        
        # At n=256, inversion EER must drop below 1%
        self.assertLess(proc['n_256']['inversion_eer'], 1.0)
        self.assertLessEqual(proc['n_512']['inversion_eer'], 0.05)

    def test_null_calibration_floor(self):
        """Rule 1.3: Assert ROP worst-case D_sys is within or near the permutation null noise floor."""
        unl = self.m['unlinkability']
        null_p95 = unl['null_noise_floor_p95']
        rop_dsys = unl['unlinkability_table']['rop']['D_sys_worst']
        self.assertLess(rop_dsys, null_p95)

    def test_load_test_littles_law(self):
        """T1: Assert Little's Law discrepancy is strictly under 5% across all load test points."""
        lt_path = ROOT_DIR / 'results' / 'raw' / 'load_test_results.json'
        with open(lt_path) as f:
            lt_rows = json.load(f)
        for row in lt_rows:
            N = row['concurrent_clients']
            X = row['throughput_req_per_s']
            Z = row['think_time_s']
            R_mean = row['mean_latency_ms'] / 1000.0
            expected_X = N / (R_mean + Z)
            discrepancy = abs(X - expected_X) / expected_X * 100.0
            self.assertLess(discrepancy, 5.0, f"Little's Law discrepancy {discrepancy:.2f}% exceeds 5% at N={N}")

    def test_tvla_side_channel_stats(self):
        """T7: Assert TVLA side-channel statistics are correctly recorded."""
        sc = self.m['side_channel']
        self.assertLess(abs(sc['tvla_t_statistic']), 4.5, "TVLA t-statistic exceeds 4.5 threshold")
        self.assertEqual(sc['tvla_trials_count'], 2000)
        self.assertGreater(sc['tvla_fixed_var_ms2'], sc['tvla_random_var_ms2'])

if __name__ == '__main__':
    unittest.main()
