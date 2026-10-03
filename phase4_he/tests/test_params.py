# phase4_he/tests/test_params.py
import pytest
import tenseal as ts
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from he.params import (
    DEFAULT_PARAMS, HIGH_SECURITY_PARAMS, TEST_PARAMS,
    validate_params, estimate_security, create_tenseal_context
)

def test_default_params_valid():
    valid, msg = validate_params(DEFAULT_PARAMS)
    assert valid, f"Default params invalid: {msg}"

def test_default_security_128bit():
    sec = estimate_security(DEFAULT_PARAMS)
    assert sec["classical_bits"] >= 128, f"Security only {sec['classical_bits']:.1f}-bit"

def test_default_slots_sufficient():
    assert DEFAULT_PARAMS.max_slots >= 256, f"Slots {DEFAULT_PARAMS.max_slots} < 256"

def test_high_security_params():
    valid, msg = validate_params(HIGH_SECURITY_PARAMS)
    assert valid
    sec = estimate_security(HIGH_SECURITY_PARAMS)
    assert sec["classical_bits"] >= 192

def test_test_params_insecure():
    valid, msg = validate_params(TEST_PARAMS)
    assert not valid
    assert "Security" in msg

def test_context_creation():
    ctx = create_tenseal_context(DEFAULT_PARAMS)
    assert isinstance(ctx, ts.Context)
    assert ctx.global_scale == 2**40
    assert ctx.auto_relin
    assert ctx.auto_rescale
    assert ctx.auto_mod_switch

def test_context_serialization_roundtrip():
    ctx = create_tenseal_context(DEFAULT_PARAMS)
    secret = ctx.serialize(save_secret_key=True, save_public_key=True, 
                           save_galois_keys=True, save_relin_keys=True)
    ctx2 = ts.context_from(secret)
    assert isinstance(ctx2, ts.Context)
    
    public = ctx.serialize(save_secret_key=False, save_public_key=True,
                           save_galois_keys=True, save_relin_keys=True)
    ctx3 = ts.context_from(public)
    assert not ctx3.has_secret_key()
    assert isinstance(ctx3, ts.Context)
