# phase3_fusion/film/__init__.py
"""
Shim package: exposes phase3 film models under the 'film' namespace
as expected by phase7_integration imports.
"""
from .model import FiLMFusion, FiLMGenerator, FiLMFusionExport
from .inference import film_fuse

__all__ = ["FiLMFusion", "FiLMGenerator", "FiLMFusionExport", "film_fuse"]
