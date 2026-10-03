# phase1_encoder/tests/test_export.py
import pytest
import torch
import numpy as np
import onnxruntime as ort
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model.encoder import build_encoder
from config import load_config

@pytest.fixture(scope="module")
def encoder_and_input():
    cfg = load_config("config.yaml")
    model = build_encoder(cfg)
    model.eval()
    x = torch.randn(1, 1, 96, 96)
    with torch.no_grad():
        ref_out = model(x).numpy()
    return model, x, ref_out

def test_onnx_parity(encoder_and_input, tmp_path):
    model, x, ref_out = encoder_and_input
    onnx_path = tmp_path / "test_encoder.onnx"
    
    # Export
    try:
        torch.onnx.export(
            model, x, onnx_path,
            opset_version=17,
            input_names=["input"], output_names=["output"],
            dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
            dynamo=False,
        )
    except TypeError:
        torch.onnx.export(
            model, x, onnx_path,
            opset_version=17,
            input_names=["input"], output_names=["output"],
            dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        )
    
    # Run ONNX
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    ort_out = sess.run(None, {"input": x.numpy()})[0]
    
    # Compare
    max_abs = np.abs(ref_out - ort_out).max()
    max_rel = (np.abs(ref_out - ort_out) / (np.abs(ref_out) + 1e-6)).max()
    assert max_abs < 1e-4, f"ONNX parity failed: max_abs_diff={max_abs}"
    assert max_rel < 1e-3, f"ONNX parity failed: max_rel_diff={max_rel}"

# TFLite/CoreML parity tests would run in CI with those runtimes available
# They are integration tests, not unit tests — skip here unless explicitly enabled
