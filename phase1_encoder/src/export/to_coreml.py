# phase1_encoder/src/export/to_coreml.py
# REQUIRES: macOS + pip install coremltools
def convert_onnx_to_coreml(onnx_path: str, mlmodel_path: str, config: dict, precision: str = "float16"):
    import coremltools as ct
    import numpy as np
    
    # Load ONNX -> CoreML
    # Note: coremltools 7+ converts ONNX directly
    mlmodel = ct.convert(
        onnx_path,
        inputs=[ct.TensorType(name="input", shape=(1, 1, *config['preprocessing']['img_size']))],
        compute_precision=ct.precision.FLOAT16 if precision == "float16" else ct.precision.FLOAT32,
        minimum_deployment_target=ct.target.iOS15
    )
    
    # Metadata
    mlmodel.author = "Cancelable Biometric System"
    mlmodel.license = "Proprietary"
    mlmodel.short_description = "Fingerprint Encoder (ResNet18 -> 256-d L2 Embedding)"
    mlmodel.input_description["input"] = "Grayscale Fingerprint ROI [-1, 1]"
    mlmodel.output_description["embedding"] = "L2 Normalized 256-d Embedding"
    
    mlmodel.save(mlmodel_path)
    print(f"✅ CoreML ({precision}) exported to {mlmodel_path}")
