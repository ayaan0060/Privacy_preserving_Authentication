import pytest
import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import get_settings

@pytest.fixture(autouse=True)
def set_test_config():
    get_settings().database.url = "sqlite+aiosqlite:///:memory:"
