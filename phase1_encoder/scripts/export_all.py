# phase1_encoder/scripts/export_all.py
import os
import sys
import argparse
import yaml

# Add project root to sys.path to ensure module resolution when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.export.to_onnx import export_onnx

# Conditional imports for platform specific tools
try:
    from src.export.to_tflite import convert_onnx_to_tflite
    HAS_TF = True
except ImportError:
    HAS_TF = False
    
try:
    from src.export.to_coreml import convert_onnx_to_coreml
    HAS_COREML = True
except ImportError:
    HAS_COREML = False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ckpt', required=True)
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--out_dir', default='exports/phase1')
    args = parser.parse_args()
    
    config = yaml.safe_load(open(args.config))
    os.makedirs(args.out_dir, exist_ok=True)
    
    onnx_path = os.path.join(args.out_dir, "encoder.onnx")
    export_onnx(args.ckpt, onnx_path, config, config['export']['onnx_opset'])
    
    if HAS_TF:
        tflite_path = os.path.join(args.out_dir, "encoder.tflite")
        convert_onnx_to_tflite(onnx_path, tflite_path, config['export']['tflite_quantize'])
    else:
        print("⚠️ TensorFlow/onnx-tf not installed. Skipping TFLite export.")
        
    if HAS_COREML:
        coreml_path = os.path.join(args.out_dir, "encoder.mlpackage")
        convert_onnx_to_coreml(onnx_path, coreml_path, config, config['export']['coreml_compute_precision'])
    else:
        print("⚠️ coremltools not installed (or not on macOS). Skipping CoreML export.")

if __name__ == "__main__":
    main()
