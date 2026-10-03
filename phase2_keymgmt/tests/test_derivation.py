# phase2_keymgmt/tests/test_derivation.py
"""
HKDF-SHA256 derivation: known-answer tests, domain separation, rescaling.
"""
import pytest
import numpy as np
import hmac
import hashlib
import secrets
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from keystore.derivation import (
    hkdf_sha256, 
    derive_key_vector, 
    verify_key_vector_consistency,
    KAT_SEED,
)

class TestHKDF:
    """RFC 5869 test vectors."""
    
    def test_rfc5869_example_1(self):
        # RFC 5869 Section A.1
        ikm = bytes.fromhex("0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b")
        salt = bytes.fromhex("000102030405060708090a0b0c")
        info = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
        okm = hkdf_sha256(ikm, salt, info, 42)
        expected = bytes.fromhex(
            "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"
        )
        assert okm == expected
    
    def test_rfc5869_example_2(self):
        ikm = bytes.fromhex("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f")
        salt = bytes.fromhex("606162636465666768696a6b6c6d6e6f707172737475767778797a7b7c7d7e7f808182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9f")
        info = bytes.fromhex("a0a1a2a3a4a5a6a7a8a9aaaabaacadaeafb0b1b2b3b4b5b6b7b8b9babbbcbdbebfc0c1c2c3c4c5c6c7c8c9cacbcccdcecfd0d1d2d3d4d5d6d7d8d9dadbdcdddedfe0e1e2e3e4e5e6e7e8e9eaebecedeeeff0f1f2f3f4f5f6f7f8f9fafbfcfdfeff")
        okm = hkdf_sha256(ikm, salt, info, 82)
        assert len(okm) == 82

class TestDeriveKeyVector:
    
    def test_output_shape_and_range(self):
        kv = derive_key_vector(KAT_SEED, length=256, range_min=-1.0, range_max=1.0)
        assert kv.shape == (256,)
        assert kv.dtype == np.float32
        assert kv.min() >= -1.0
        assert kv.max() <= 1.0
    
    def test_deterministic(self):
        kv1 = derive_key_vector(KAT_SEED, length=256)
        kv2 = derive_key_vector(KAT_SEED, length=256)
        assert np.allclose(kv1, kv2)
    
    def test_different_seed_different_output(self):
        seed1 = secrets.token_bytes(32)
        seed2 = secrets.token_bytes(32)
        kv1 = derive_key_vector(seed1)
        kv2 = derive_key_vector(seed2)
        assert not np.allclose(kv1, kv2)
    
    def test_domain_separation(self):
        """Different info prefix → different output."""
        kv1 = derive_key_vector(KAT_SEED, info_prefix="app/v1")
        kv2 = derive_key_vector(KAT_SEED, info_prefix="app/v2")
        assert not np.allclose(kv1, kv2)
    
    def test_length_parameter(self):
        kv128 = derive_key_vector(KAT_SEED, length=128)
        kv256 = derive_key_vector(KAT_SEED, length=256)
        assert kv128.shape == (128,)
        assert kv256.shape == (256,)
    
    def test_range_rescaling(self):
        kv_pos = derive_key_vector(KAT_SEED, range_min=0.0, range_max=1.0)
        kv_neg = derive_key_vector(KAT_SEED, range_min=-1.0, range_max=1.0)
        assert kv_pos.min() >= 0.0
        assert kv_pos.max() <= 1.0
        assert kv_neg.min() >= -1.0
        assert kv_neg.max() <= 1.0
    
    def test_verify_consistency(self):
        kv = derive_key_vector(KAT_SEED)
        assert verify_key_vector_consistency(KAT_SEED, kv) is True
        
        # Tampered
        kv_tampered = kv.copy()
        kv_tampered[0] += 0.1
        assert verify_key_vector_consistency(KAT_SEED, kv_tampered) is False
