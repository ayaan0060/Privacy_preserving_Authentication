# tests/test_unlinkability_metric.py
import unittest
import numpy as np
from core.unlinkability import compute_gomez_barrero, compute_null_calibration, compute_bootstrap_cis

class TestUnlinkabilityMetric(unittest.TestCase):
    def test_old_bug_vs_fixed_degenerate_arrays(self):
        """
        Proof of fix for finding F4 / BioHashing bug:
        When mated and non-mated score arrays are constant (e.g. all 1.0),
        the naive algorithm divided by zero (bin width = 0), producing NaN -> clipped to 1.0.
        The robust implementation recognizes identical point masses -> D_sys = 0.0, Omega = 1.0.
        """
        n = 1500
        mated = np.ones(n, dtype=np.float64)
        non_mated = np.ones(n, dtype=np.float64)
        
        # 1. Simulate the OLD buggy logic:
        all_s = np.concatenate([mated, non_mated])
        s_min, s_max = np.min(all_s), np.max(all_s)
        bins = np.linspace(s_min, s_max, 101) # all 1.0
        bin_widths = np.diff(bins) # all 0.0
        # In numpy, histogram with density=True on zero bin widths issues warnings and produces NaNs
        with np.errstate(divide='ignore', invalid='ignore'):
            p_m, _ = np.histogram(mated, bins=bins, density=True)
            p_nm, _ = np.histogram(non_mated, bins=bins, density=True)
            denom = p_m + p_nm + 1e-12
            d_loc = np.maximum(0.0, 2.0 * (p_m / denom) - 1.0)
            old_bug_dsys = float(np.sum(d_loc * p_m * bin_widths))
            # Fallback in old code:
            if np.isnan(old_bug_dsys):
                old_bug_dsys = 1.0
        
        self.assertEqual(old_bug_dsys, 1.0, "Old bug should evaluate to 1.0 due to NaN fallback")
        
        # 2. Test the NEW fixed logic:
        d_sys, omega, details = compute_gomez_barrero(mated, non_mated)
        self.assertEqual(d_sys, 0.0, "Fixed logic must return D_sys = 0.0 for identical point masses")
        self.assertEqual(omega, 1.0, "Fixed logic must return Omega = 1.0 for identical point masses")
        self.assertTrue(details['is_degenerate'])

    def test_completely_separated_distributions(self):
        """Disjoint distributions must yield D_sys = 1.0, Omega = 0.0."""
        rng = np.random.RandomState(42)
        mated = rng.normal(loc=1.0, scale=0.01, size=2000)
        non_mated = rng.normal(loc=-1.0, scale=0.01, size=2000)
        
        d_sys, omega, _ = compute_gomez_barrero(mated, non_mated)
        self.assertAlmostEqual(d_sys, 1.0, places=3)
        self.assertAlmostEqual(omega, 0.0, places=3)

    def test_bin_count_sensitivity(self):
        """D_sys on identical distributions should stay within the finite-sample noise floor across bin counts."""
        rng = np.random.RandomState(42)
        # Identical N(0, 1) distributions
        mated = rng.normal(0.0, 1.0, size=5000)
        non_mated = rng.normal(0.0, 1.0, size=5000)
        
        for k in [50, 100, 200]:
            d_sys, omega, _ = compute_gomez_barrero(mated, non_mated, num_bins=k)
            # On 5000 samples, finite-sample noise floor is < 0.08
            self.assertLess(d_sys, 0.08, f"D_sys with {k} bins exceeded noise floor: {d_sys}")

    def test_null_calibration_noise_floor(self):
        """Null calibration must correctly characterize the finite-sample noise floor."""
        rng = np.random.RandomState(42)
        mated = rng.normal(0.0, 1.0, size=1500)
        non_mated = rng.normal(0.0, 1.0, size=1500)
        
        calib = compute_null_calibration(mated, non_mated, num_permutations=200, num_bins=100)
        self.assertIn('null_mean', calib)
        self.assertIn('null_p95', calib)
        self.assertGreater(calib['null_p95'], calib['null_mean'])
        # Noise floor on 1500 samples with 100 bins is typically ~0.05-0.08
        self.assertLess(calib['null_mean'], 0.10)

if __name__ == '__main__':
    unittest.main()
