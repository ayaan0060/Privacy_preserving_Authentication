# phase1_encoder/src/export/to_onnx.py
import torch
import torch.onnx
from src.models.backbone import FingerprintEncoder

def export_onnx(ckpt_path: str, output_path: str, config: dict, opset: int = 17):
    encoder = FingerprintEncoder(
        embedding_dim=config['model']['embedding_dim'],
        pretrained=False, dropout=0.0
    )
    
    ckpt = torch.load(ckpt_path, map_location='cpu')
    encoder_state = {k.replace('encoder.', ''): v for k, v in ckpt['state_dict'].items() if k.startswith('encoder.')}
    encoder.load_state_dict(encoder_state)
    encoder.eval()
    
    # Dummy Input
    h, w = config['preprocessing']['img_size']
    dummy = torch.randn(1, 1, h, w)
    
    # Dynamic Axes for Batch Size
    dynamic_axes = {'input': {0: 'batch'}, 'embedding': {0: 'batch'}}
    
    torch.onnx.export(
        encoder, dummy, output_path,
        export_params=True, opset_version=opset,
        do_constant_folding=True,
        input_names=['input'], output_names=['embedding'],
        dynamic_axes=dynamic_axes,
        verbose=False
    )
    print(f"✅ ONNX exported to {output_path}")
    
    # Verify
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(output_path)
        out = sess.run(None, {'input': dummy.numpy()})
        print(f"ONNX Runtime Output Shape: {out[0].shape}")
        assert out[0].shape == (1, config['model']['embedding_dim'])
        print("✅ ONNX Verification Passed.")
    except ImportError:
        print("⚠️ onnxruntime not installed. Skipping runtime verification.")
