# phase3_fusion/film/model.py
"""
Shim module: re-exports FiLMFusion and FiLMGenerator from src.models.film.

Also provides:
- FiLMFusionExport: a wrapper that accepts embedding_dim kwarg for easy test
  instantiation and exports a single-tensor output (just t, no gamma/beta).
  Used in phase7 tests for ONNX export.
"""
import sys
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F

_phase3_root = Path(__file__).parent.parent
if str(_phase3_root) not in sys.path:
    sys.path.insert(0, str(_phase3_root))

try:
    from src.models.film import FiLMFusion as _FiLMFusion, FiLMGenerator
except ModuleNotFoundError:
    import importlib.util
    film_path = _phase3_root / "src" / "models" / "film.py"
    spec = importlib.util.spec_from_file_location("phase3_src_models_film", film_path)
    film_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(film_mod)
    _FiLMFusion = film_mod.FiLMFusion
    FiLMGenerator = film_mod.FiLMGenerator


class FiLMFusionExport(nn.Module):
    """
    ONNX-exportable FiLM wrapper.
    
    - Accepts embedding_dim for easy construction (creates its own FiLMGenerator).
    - forward(x, k) -> t  (single L2-normalized tensor, no gamma/beta).
    - Compatible with torch.onnx.export and onnxruntime inference.
    
    Usage in tests:
        model = FiLMFusionExport(embedding_dim=256)
        torch.onnx.export(model, (dummy_x, dummy_k), "film.onnx", opset_version=17)
    """

    def __init__(self, embedding_dim: int = 256):
        super().__init__()
        generator = FiLMGenerator(
            input_dim=embedding_dim,
            hidden_dims=[512, 512],
            output_dim=embedding_dim,
        )
        self._film = _FiLMFusion(film_generator=generator)

    def forward(self, x: torch.Tensor, k: torch.Tensor) -> torch.Tensor:
        """Returns only t (L2-normalized template). Drops gamma and beta."""
        t, _, _ = self._film(x, k)
        return t


# Backward-compatible alias: FiLMFusion in phase7 tests means the export wrapper
FiLMFusion = FiLMFusionExport

__all__ = ["FiLMFusion", "FiLMFusionExport", "FiLMGenerator"]
