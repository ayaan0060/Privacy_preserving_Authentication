# phase2_keymgmt/src/config.py
import yaml
from pathlib import Path
from typing import Dict, Any

_CONFIG_CACHE: Dict[str, Any] = {}

def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    global _CONFIG_CACHE
    if path in _CONFIG_CACHE:
        return _CONFIG_CACHE[path]
    
    p = Path(path)
    if not p.exists():
        # Try parent dir (if running from scripts/)
        p = Path(__file__).parent.parent / path
    
    with open(p, 'r') as f:
        cfg = yaml.safe_load(f)
    
    _CONFIG_CACHE[path] = cfg
    return cfg
