# tests/test_keys_core.py
import unittest
import numpy as np
from core.keys import (
    derive_haar_matrix,
    derive_film_key,
    derive_bipolar_signs,
    derive_permutation,
    derive_iom_matrices,
)

class TestKeysCore(unittest.TestCase):
    def test_haar_matrix_properties(self):
        seed = b'test_master_seed_256_bits_entropy_!'
        user_a = "user_alice"
        
        Q1 = derive_haar_matrix(seed, user_a, version=1, dim=256)
        Q2 = derive_haar_matrix(seed, user_a, version=1, dim=256)
        Q_v2 = derive_haar_matrix(seed, user_a, version=2, dim=256)
        Q_bob = derive_haar_matrix(seed, "user_bob", version=1, dim=256)
        
        # 1. Determinism
        np.testing.assert_array_equal(Q1, Q2)
        
        # 2. Domain separation
        self.assertFalse(np.allclose(Q1, Q_v2))
        self.assertFalse(np.allclose(Q1, Q_bob))
        
        # 3. Strict orthogonality
        diff = np.max(np.abs(Q1.T @ Q1 - np.eye(256, dtype=np.float32)))
        self.assertLess(diff, 1e-5, f"Max deviation from identity: {diff}")
        
        # 4. Isometry test on vector
        x = np.random.randn(256).astype(np.float32)
        x = x / np.linalg.norm(x)
        y = Q1 @ x
        np.testing.assert_allclose(np.linalg.norm(y), 1.0, atol=1e-5)

    def test_permutation_properties(self):
        seed = b'test_master_seed_256_bits_entropy_!'
        perm1 = derive_permutation(seed, "alice", 1, 256)
        perm2 = derive_permutation(seed, "alice", 1, 256)
        np.testing.assert_array_equal(perm1, perm2)
        self.assertEqual(len(set(perm1)), 256)
        self.assertEqual(np.min(perm1), 0)
        self.assertEqual(np.max(perm1), 255)

    def test_iom_matrices_properties(self):
        seed = b'test_master_seed_256_bits_entropy_!'
        W = derive_iom_matrices(seed, "alice", 1, num_groups=64, group_size=8, dim=256)
        self.assertEqual(W.shape, (64, 8, 256))
        self.assertLess(abs(W.mean()), 0.05)
        self.assertLess(abs(W.std() - 1.0), 0.05)

if __name__ == '__main__':
    unittest.main()
