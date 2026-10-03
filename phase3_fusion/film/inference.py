# phase3_fusion/film/inference.py
"""
ONNX runtime inference helper for FiLM fusion.
Used in BiometricPipeline to run the exported ONNX film model.
"""
import numpy as np
import onnxruntime as ort


def film_fuse(film_session, x: np.ndarray, k: np.ndarray) -> np.ndarray:
    """
    Run FiLM fusion via ONNX runtime or PyTorch model.
    """
    if x.ndim == 1:
        x = x[np.newaxis, :]
    if k.ndim == 1:
        k = k[np.newaxis, :]

    if hasattr(film_session, 'get_inputs'):
        input_names = [inp.name for inp in film_session.get_inputs()]
        inputs = dict(zip(input_names, [x.astype(np.float32), k.astype(np.float32)]))
        output = film_session.run(None, inputs)[0]
        return output[0]
    else:
        import torch
        with torch.no_grad():
            tx = torch.from_numpy(x).float()
            tk = torch.from_numpy(k).float()
            res = film_session(tx, tk)
            t = res[0] if isinstance(res, tuple) else res
            return t.numpy()[0]
