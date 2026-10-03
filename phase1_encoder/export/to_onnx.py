# phase1_encoder/export/to_onnx.py
"""
Export PyTorch encoder to ONNX with dynamic batch size.
Validates numerical parity.
"""
import argparse
import yaml
import torch
import onnx
import onnxruntime as ort
import numpy as np
from pathlib import Path

from ..model.encoder import build_encoder
from ..config import load_config


def export_onnx(cfg: dict, checkpoint_path: Path, output_path: Path, opset: int = 17):
    device = torch.device("cpu")  # Export on CPU
    model = build_encoder(cfg).to(device)
    
    ckpt = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    
    # Dummy input
    h, w = cfg["data"]["img_size"]
    dummy = torch.randn(1, 1, h, w, device=device)
    
    # Export
    dynamic_axes = {
        "input": {0: "batch"},
        "output": {0: "batch"},
    } if cfg["export"]["dynamic_batch"] else None
    
    torch.onnx.export(
        model,
        dummy,
        output_path,
        export_params=True,
        opset_version=opset,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=dynamic_axes,
        verbose=False,
    )
    
    # Validate ONNX model
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    print(f"[ONNX] Model validated: {output_path}")
    
    # Numerical parity test
    print("[ONNX] Running numerical parity test...")
    ort_session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    
    # Test multiple batch sizes
    for batch in [1, 4, 8, 16]:
        x = torch.randn(batch, 1, h, w)
        with torch.no_grad():
            torch_out = model(x).numpy()
        ort_out = ort_session.run(None, {"input": x.numpy()})[0]
        
        diff = np.abs(torch_out - ort_out).max()
        rel_diff = (np.abs(torch_out - ort_out) / (np.abs(torch_out) + 1e-6)).max()
        print(f"  Batch {batch:2d}: max_abs_diff={diff:.2e}, max_rel_diff={rel_diff:.2e}")
        assert diff < 1e-4, f"ONNX parity failed for batch {batch}: {diff}"
    
    print("[ONNX] Numerical parity PASSED (max diff < 1e-4)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--opset", type=int, default=17)
    args = parser.parse_args()
    
    cfg = load_config(args.config)
    export_onnx(cfg, args.checkpoint, args.output, args.opset)


if __name__ == "__main__":
    main()
