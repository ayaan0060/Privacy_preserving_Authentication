# phase5_backend/tests/test_pii_logging.py
import pytest
import logging
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.security.pii_filter import PIIRedactionFilter

class TestPIIRedaction:
    def setup_method(self):
        self.filter = PIIRedactionFilter()
    
    def test_redacts_template_field(self):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Enrolling user with template=[1.0, 2.0, 3.0]", args=(), exc_info=None
        )
        self.filter.filter(record)
        assert "template=[REDACTED]" in record.msg
        assert "1.0" not in record.msg
    
    def test_redacts_ciphertext_field(self):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg='ciphertext="abc123secret"', args=(), exc_info=None
        )
        self.filter.filter(record)
        assert 'ciphertext="[REDACTED]"' in record.msg
        assert "abc123secret" not in record.msg
    
    def test_redacts_key_vector(self):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg='key_vector: [0.5, -0.3, 0.1]', args=(), exc_info=None
        )
        self.filter.filter(record)
        assert "key_vector: [REDACTED]" in record.msg
    
    def test_redacts_seed(self):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Generated seed: a1b2c3d4e5f6", args=(), exc_info=None
        )
        self.filter.filter(record)
        assert "seed: [REDACTED]" in record.msg
    
    def test_redacts_begin_key_pattern(self):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="-----BEGIN PRIVATE KEY-----\nMIIE...", args=(), exc_info=None
        )
        self.filter.filter(record)
        assert "BEGIN PRIVATE KEY" not in record.msg
        assert "[REDACTED]" in record.msg
    
    def test_json_log_redaction(self):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg='{"user_id": "alice", "encrypted_template": "deadbeef"}', args=(), exc_info=None
        )
        self.filter.filter(record)
        assert '"encrypted_template": "[REDACTED]"' in record.msg
        assert "deadbeef" not in record.msg
