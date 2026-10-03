# phase1_encoder/src/export/to_tflite.py
# REQUIRES: pip install tensorflow onnx onnx-tf
# Run on Linux/Windows (not macOS usually for TF)
def convert_onnx_to_tflite(onnx_path: str, tflite_path: str, quantize: str = "dynamic"):
    import onnx
    from onnx_tf.backend import prepare
    import tensorflow as tf
    
    onnx_model = onnx.load(onnx_path)
    tf_rep = prepare(onnx_model)
    
    # Save as SavedModel first
    import tempfile, shutil
    tmp_dir = tempfile.mkdtemp()
    tf_rep.export_graph(tmp_dir)
    
    converter = tf.lite.TFLiteConverter.from_saved_model(tmp_dir)
    
    if quantize == "dynamic":
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        # Dynamic range quantization (weights int8, activations float)
    elif quantize == "int8":
        # Requires representative dataset for full integer quantization
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        # converter.representative_dataset = representative_data_gen
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type = tf.uint8
        converter.inference_output_type = tf.uint8
        print("⚠️ INT8 Quantization requires representative_dataset generator (not implemented here). Falling back to Dynamic.")
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS, tf.lite.OpsSet.SELECT_TF_OPS]
    
    tflite_model = converter.convert()
    
    with open(tflite_path, 'wb') as f:
        f.write(tflite_model)
    
    shutil.rmtree(tmp_dir)
    print(f"✅ TFLite ({quantize}) exported to {tflite_path}")
