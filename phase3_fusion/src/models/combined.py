# phase3_fusion/src/models/combined.py
"""
Combined Model for ONNX Export.
1. Encoder (Phase 1) - Frozen
2. FiLM Generator (Phase 3) - Trained
3. Fusion Layer
Inputs: Image (1, 96, 96), Key Vector k (256)
Output: Template t (256)
"""
import torch
import torch.nn as nn
import os, sys
from typing import Tuple

class EncoderWrapper(nn.Module):
    def __init__(self, encoder_ckpt_path: str, config: dict):
        super().__init__()
        # Ensure Phase 1 path is on sys.path
        phase1_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../phase1_encoder"))
        if phase1_dir not in sys.path:
            sys.path.insert(0, phase1_dir)
            
        from model.encoder import FingerprintEncoder
        self.encoder = FingerprintEncoder(
            embedding_dim=config['model']['embedding_dim'],
            pretrained=False, dropout=0.0
        )
        ckpt = torch.load(encoder_ckpt_path, map_location='cpu')
        encoder_state = {k.replace('encoder.', ''): v for k, v in ckpt['state_dict'].items() if k.startswith('encoder.')}
        self.encoder.load_state_dict(encoder_state, strict=True)
        self.encoder.eval()
        for p in self.encoder.parameters():
            p.requires_grad = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return self.encoder(x)


class CombinedFusionModel(nn.Module):
    """
    Exportable Module: (img, k) -> t
    """
    def __init__(self, encoder: EncoderWrapper, film_fusion):
        super().__init__()
        self.encoder = encoder
        self.film_fusion = film_fusion
        
    def forward(self, img: torch.Tensor, k: torch.Tensor) -> torch.Tensor:
        """
        img: (B, 1, H, W)
        k:   (B, 256)
        Returns:
            t: (B, 256) L2 Normalized Template
        """
        x = self.encoder(img)          # (B, 256)
        t, _, _ = self.film_fusion(x, k)
        return t

    def export_onnx_separate(self, onnx_encoder_path: str, onnx_film_path: str, onnx_combined_path: str, config: dict):
        """Exports 3 ONNX models for flexible deployment."""
        import torch.onnx
        
        h, w = config['preprocessing']['img_size']
        dummy_img = torch.randn(1, 1, h, w)
        dummy_k = torch.randn(1, 256)
        dynamic_axes = {'input': {0: 'batch'}, 'k': {0: 'batch'}, 'embedding': {0: 'batch'}, 'gamma': {0: 'batch'}, 'beta': {0: 'batch'}, 'template': {0: 'batch'}}
        
        # 1. Encoder Only
        torch.onnx.export(self.encoder, dummy_img, onnx_encoder_path,
                          input_names=['input'], output_names=['embedding'],
                          dynamic_axes={'input': {0: 'batch'}, 'embedding': {0: 'batch'}},
                          opset_version=config['export']['onnx_opset'])
        print(f"Exported Encoder -> {onnx_encoder_path}")
        
        # 2. FiLM Generator Only
        class FilmGenWrapper(nn.Module):
            def __init__(self, gen): super().__init__(); self.gen = gen
            def forward(self, k): return self.gen(k)
        
        gen_wrapper = FilmGenWrapper(self.film_fusion.generator)
        torch.onnx.export(gen_wrapper, dummy_k, onnx_film_path,
                          input_names=['k'], output_names=['gamma', 'beta'],
                          dynamic_axes=dynamic_axes, opset_version=config['export']['onnx_opset'])
        print(f"Exported FiLM Generator -> {onnx_film_path}")
        
        # 3. Combined
        torch.onnx.export(self, (dummy_img, dummy_k), onnx_combined_path,
                          input_names=['input', 'k'], output_names=['template'],
                          dynamic_axes=dynamic_axes, opset_version=config['export']['onnx_opset'])
        print(f"Exported Combined Fusion -> {onnx_combined_path}")
