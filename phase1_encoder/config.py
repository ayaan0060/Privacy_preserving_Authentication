# phase1_encoder/config.py
import yaml
from pathlib import Path
from typing import Dict, Any

def load_config(path: Path | str) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        path = Path(__file__).parent / path
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {path}")
    with open(path, "r") as f:
        return yaml.safe_load(f)
