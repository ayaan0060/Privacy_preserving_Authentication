# phase1_encoder/export/to_coreml.py
"""
Convert ONNX -> CoreML (mlpackage).
Supports FP16 precision for Neural Engine.
"""
import argparse
import coremltools as ct
import onnx
import numpy as np
from pathlib import Path

from ..config import load_config


def convert_onnx_to_coreml(
    onnx_path: Path,
    coreml_path: Path,
    precision: str = "fp16",  # "fp32" | "fp16"
    img_size: tuple = (96, 96),
):
    print(f"[COREML] Loading ONNX from {onnx_path}")
    onnx_model = onnx.load(str(onnx_path))
    
    # Convert
    print(f"[COREML] Converting to CoreML (precision={precision})...")
    mlmodel = ct.convert(
        onnx_model,
        source="onnx",
        inputs=[
            ct.TensorType(
                name="input",
                shape=(1, 1, img_size[0], img_size[1]),  # NCHW
                dtype=np.float32,
            )
        ],
        compute_precision=ct.precision.FLOAT16 if precision == "fp16" else ct.precision.FLOAT32,
        minimum_deployment_target=ct.target.iOS15,  # Neural Engine support
    )
    
    # Metadata
    mlmodel.short_description = "Fingerprint Encoder (ResNet18 + ArcFace)"
    mlmodel.version = "1.0"
    mlmodel.author = "Cancelable Biometric Auth System"
    mlmodel.license = "Research/Prototype Use Only"
    
    # Save
    mlmodel.save(str(coreml_path))
    print(f"[COREML] Saved {coreml_path}")
    
    # Validate
    test_input = np.random.randn(1, 1, img_size[0], img_size[1]).astype(np.float32)
    coreml_out = mlmodel.predict({"input": test_input})["output"]
    print(f"  Output shape: {coreml_out.shape}")
    
    return mlmodel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--precision", choices=["fp32", "fp16"], default="fp16")
    args = parser.parse_args()
    
    cfg = load_config(args.config)
    convert_onnx_to_coreml(args.onnx, args.output, args.precision, tuple(cfg["data"]["img_size"]))


if __name__ == "__main__":
    main()
