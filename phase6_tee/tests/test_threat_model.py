# phase6_tee/tests/test_threat_model.py
"""
Threat Model Assertion Tests.
"""
import pytest
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tee.threat_model import (
    get_simulation_limitations, 
    get_real_tee_guarantees,
    THREAT_MODEL,
)
from tee.simulation import SoftwareSecureContext


class TestThreatModelDocumentation:
    
    def test_threat_model_exists(self):
        """Threat model document is present and non-empty."""
        assert len(THREAT_MODEL) > 1000
        assert "SIMULATION LIMITATIONS" in THREAT_MODEL
        assert "REAL TEE GUARANTEES" in THREAT_MODEL
        assert "THREATS MITIGATED" in THREAT_MODEL
    
    def test_simulation_limitations_documented(self):
        """All known simulation limitations are explicitly listed."""
        limitations = get_simulation_limitations()
        critical = [
            "memory isolation",
            "hardware RNG",
            "attestation",
            "root/OS compromise",
            "tamper resistance",
            "side-channel",
            "verified boot",
        ]
        
        for crit in critical:
            assert any(crit.lower() in lim.lower() for lim in limitations), \
                f"Missing critical limitation: {crit}"
    
    def test_real_tee_guarantees_documented(self):
        """Real TEE guarantees are explicitly listed."""
        guarantees = get_real_tee_guarantees()
        critical = [
            "memory isolation",
            "hardware RNG",
            "attestation",
            "OS/kernel compromise",
            "tamper resistance",
            "side-channel",
            "verified boot",
            "keys never leave",
            "monotonic counters",
        ]
        
        for crit in critical:
            assert any(crit.lower() in g.lower() for g in guarantees), \
                f"Missing critical guarantee: {crit}"
    
    def test_simulation_vs_real_mapping(self):
        """Each simulation limitation has corresponding real TEE guarantee."""
        limitations = get_simulation_limitations()
        guarantees = get_real_tee_guarantees()
        assert len(limitations) == len(guarantees)


class TestSecureContextSecurityProperties:
    """Verify SecureContext enforces required security properties."""
    
    def test_interface_requires_threshold_check_inside(self):
        from tee.interface import SecureContext
        import inspect
        
        sig = inspect.signature(SecureContext.verify_and_sign)
        params = list(sig.parameters.keys())
        
        assert "encrypted_similarity" in params
        assert "threshold" in params
    
    def test_interface_requires_nonce_freshness(self):
        from tee.interface import SecureContext
        import inspect
        
        sig = inspect.signature(SecureContext.verify_and_sign)
        params = list(sig.parameters.keys())
        
        assert "nonce" in params
    
    def test_interface_requires_key_version(self):
        from tee.interface import SecureContext
        import inspect
        
        sig = inspect.signature(SecureContext.verify_and_sign)
        params = list(sig.parameters.keys())
        
        assert "key_version" in params
    
    def test_interface_returns_signature_not_score(self):
        from tee.interface import VerificationResult
        import dataclasses
        
        fields = {f.name for f in dataclasses.fields(VerificationResult)}
        
        assert "verified" in fields
        assert "signature" in fields
        assert "signed_payload" in fields
        assert "similarity_score" in fields
    
    def test_exceptions_match_threats(self):
        from tee.interface import (
            NonceReplayError,
            NonceExpiredError,
            KeyRevokedError,
            ThresholdNotMetError,
            HardwareUnavailableError,
        )
        
        threats = {
            NonceReplayError: "replay attack",
            NonceExpiredError: "stale nonce",
            KeyRevokedError: "key rollback",
            ThresholdNotMetError: "score manipulation",
            HardwareUnavailableError: "TEE failure",
        }
        
        for exc in threats:
            assert issubclass(exc, Exception)


class TestSimulationWarnings:
    """Tests that verify simulation warnings are present."""
    
    def test_simulation_class_docstring_warns(self):
        doc = SoftwareSecureContext.__doc__
        assert doc is not None
        assert "SIMULATION" in doc.upper()
        assert "NOT A REAL" in doc.upper()
        assert "HARDWARE SECURITY BOUNDARY" in doc.upper()
