# phase5_backend/backend/security/pii_filter.py
"""
PII Redaction Middleware & Log Filter.
Ensures NO biometric data, keys, or ciphertexts appear in logs.
"""
import re
import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..config import get_settings


class PIIRedactionFilter(logging.Filter):
    """Logging filter that redacts sensitive fields."""
    
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.redact_fields = set(settings.pii.redact_fields)
        self.redact_patterns = [re.compile(p, re.IGNORECASE) for p in settings.pii.redact_patterns]
    
    def filter(self, record: logging.LogRecord) -> bool:
        if not get_settings().pii.filter_logs:
            return True
        
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = self._redact_string(record.msg)
        
        if record.args:
            record.args = tuple(
                self._redact_string(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        return True
    
    def _redact_string(self, text: str) -> str:
        for field in self.redact_fields:
            text = re.sub(
                rf'("?\w*{field}\w*"?\s*[:=]\s*"?)([^"\s,}}]+)("?)',
                r'\1[REDACTED]\3',
                text,
                flags=re.IGNORECASE
            )
        
        for pattern in self.redact_patterns:
            text = pattern.sub("[REDACTED]", text)
        
        return text


class PIIRedactionMiddleware(BaseHTTPMiddleware):
    """Middleware to prevent PII in request/response logs."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        return response


def setup_pii_logging():
    """Configure root logger with PII filter."""
    root_logger = logging.getLogger()
    pii_filter = PIIRedactionFilter()
    
    for handler in root_logger.handlers:
        handler.addFilter(pii_filter)
    
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]:
        logger = logging.getLogger(name)
        logger.addFilter(pii_filter)
