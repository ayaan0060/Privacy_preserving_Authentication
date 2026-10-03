# phase7_integration/tests/test_adversarial.py
"""
Consolidated Adversarial Test Runner.
Runs all adversarial test modules.
"""
import pytest
import sys, os

phase_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for p in ["phase1_encoder", "phase2_keymgmt", "phase3_fusion", "phase4_he", "phase5_backend", "phase6_tee", "phase7_integration"]:
    path = os.path.join(phase_root, p)
    if path not in sys.path:
        sys.path.insert(0, path)

from adversarial import (
    replay_tests,
    rotation_tests,
    inversion_tests,
    side_channel_tests,
    model_extraction,
)


class TestAdversarialSuite:
    """Meta-test to ensure all adversarial tests pass."""
    
    def test_replay_tests_exist(self):
        assert hasattr(replay_tests, 'TestNonceReplay')
        assert hasattr(replay_tests, 'TestTemplateReplay')
        assert hasattr(replay_tests, 'TestSignatureReplay')
    
    def test_rotation_tests_exist(self):
        assert hasattr(rotation_tests, 'TestKeyRotation')
    
    def test_inversion_tests_exist(self):
        assert hasattr(inversion_tests, 'TestTemplateInversion')
        assert hasattr(inversion_tests, 'TestEncoderInversion')
    
    def test_side_channel_tests_exist(self):
        assert hasattr(side_channel_tests, 'TestTimingSideChannels')
    
    def test_model_extraction_tests_exist(self):
        assert hasattr(model_extraction, 'TestModelExtraction')
