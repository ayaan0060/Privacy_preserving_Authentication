# phase1_encoder/export/to_tflite.py
"""
Convert ONNX -> TensorFlow SavedModel -> TFLite.
Supports FP32, FP16, INT8 (quantization-aware via representative dataset).
"""
import argparse
import numpy as np
import tensorflow as tf
import tf2onnx
import onnx
from pathlib import Path

from ..data.dataset import build_dataloaders
from ..config import load_config


def convert_onnx_to_tflite(
    onnx_path: Path,
    tflite_path: Path,
    quantize: str = "int8",  # "fp32", "fp16", "int8"
    representative_data: np.ndarray | None = None,
):
    # Load ONNX
    onnx_model = onnx.load(str(onnx_path))
    
    # Convert to TF SavedModel
    tf_saved_model_dir = tflite_path.parent / f"{tflite_path.stem}_tf"
    tf_saved_model_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[TFLITE] Converting ONNX -> TF SavedModel at {tf_saved_model_dir}")
    tf2onnx.convert.from_onnx(
        onnx_model,
        output_path=str(tf_saved_model_dir),
        opset=17,
    )
    
    # TFLite converter
    converter = tf.lite.TFLiteConverter.from_saved_model(str(tf_saved_model_dir))
    
    if quantize == "fp16":
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.target_spec.supported_types = [tf.float16]
        print("[TFLITE] FP16 quantization enabled")
    
    elif quantize == "int8":
        if representative_data is None:
            raise ValueError("INT8 quantization requires representative dataset")
        
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        
        def representative_dataset_gen():
            for i in range(min(100, len(representative_data))):
                yield [representative_data[i:i+1].astype(np.float32)]
        
        converter.representative_dataset = representative_dataset_gen
        converter.target_spec.supported_ops = [
            tf.lite.OpsSet.TFLITE_BUILTINS_INT8,
            tf.lite.OpsSet.SELECT_TF_OPS,  # Allow flex ops if needed
        ]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8
        print("[TFLITE] INT8 full integer quantization enabled")
    
    else:  # fp32
        print("[TFLITE] FP32 (no quantization)")
    
    tflite_model = converter.convert()
    
    tflite_path.write_bytes(tflite_model)
    print(f"[TFLITE] Saved {tflite_path} ({len(tflite_model)/1024:.1f} KB)")
    
    # Validate
    interpreter = tf.lite.Interpreter(model_content=tflite_model)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print(f"  Input: {input_details[0]['shape']} {input_details[0]['dtype']}")
    print(f"  Output: {output_details[0]['shape']} {output_details[0]['dtype']}")
    
    return tflite_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quantize", choices=["fp32", "fp16", "int8"], default="int8")
    args = parser.parse_args()
    
    cfg = load_config(args.config)
    
    # Get representative data for INT8 calibration
    rep_data = None
    if args.quantize == "int8":
        print("[TFLITE] Collecting representative data for INT8 calibration...")
        _, _, test_loader = build_dataloaders(cfg)
        rep_samples = []
        for images, _ in test_loader:
            rep_samples.append(images.numpy())
            if len(rep_samples) * cfg["eval"]["batch_size"] >= 500:
                break
        rep_data = np.concatenate(rep_samples, axis=0)[:500]
        print(f"  Collected {len(rep_data)} samples")
    
    convert_onnx_to_tflite(args.onnx, args.output, args.quantize, rep_data)


if __name__ == "__main__":
    main()
