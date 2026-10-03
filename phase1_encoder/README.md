# Phase 1: CNN Encoder (Feature Extraction)

**STATUS: REAL — Fully implemented, trainable, exportable. No simulation.**

## 1. Project Structure

```text
phase1_encoder/
├── config.yaml                 # Hyperparameters, paths, reproducibility seeds
├── config.py                   # Configuration loader
├── requirements.txt            # Pinned dependencies
├── data/
│   ├── __init__.py
│   ├── download.py             # SOCOFing / FVC2004 fetch & verify (checksums)
│   ├── preprocessing.py        # CLAHE, ROI, resize, normalization
│   └── dataset.py              # PyTorch Dataset + DataLoader (train/val/test splits)
├── model/
│   ├── __init__.py
│   ├── backbone.py             # ResNet18-style backbone (no pretrained weights)
│   ├── head.py                 # Embedding head + L2 norm
│   ├── loss.py                 # ArcFace loss (with margin scheduling)
│   └── encoder.py              # Full Encoder = Backbone + Head (exportable)
├── train/
│   ├── __init__.py
│   ├── trainer.py              # Training loop, AMP, checkpointing, LR schedule
│   └── mining.py               # Hard-negative mining (semi-hard triplet fallback)
├── eval/
│   ├── __init__.py
│   ├── metrics.py              # EER, ROC, DET, Rank-1 identification
│   └── evaluate.py             # Evaluation script (loads checkpoint, runs on test set)
├── export/
│   ├── __init__.py
│   ├── to_onnx.py              # ONNX export + validation (dynamic batch)
│   ├── to_tflite.py            # TFLite conversion (INT8 quantization aware)
│   └── to_coreml.py            # CoreML conversion (FP16)
├── scripts/
│   ├── train.sh                # One-command training launch
│   └── eval.sh                 # One-command evaluation launch
└── tests/
    ├── test_preprocessing.py   # Unit tests: shapes, value ranges, determinism
    ├── test_model.py           # Forward/backward, gradient flow, norm=1
    ├── test_loss.py            # ArcFace gradient sanity, margin behavior
    └── test_export.py          # ONNX/TFLite/CoreML parity vs PyTorch (1e-4 tol)
```

---

## 2. How to Run Phase 1

```bash
# 1. Install deps
cd phase1_encoder
pip install -r requirements.txt

# 2. Download data (SOCOFing)
python -m data.download --dataset socofing --root ./data/raw

# 3. Preprocess (handled lazily by Dataset, but you can verify)
python -c "from data.preprocessing import preprocess_image; print('Preprocessing OK')"

# 4. Train
chmod +x scripts/train.sh
./scripts/train.sh config.yaml

# 5. Evaluate (after training converges)
./scripts/eval.sh config.yaml checkpoints/best.pt eval_results

# 6. Export
python -m export.to_onnx --config config.yaml --checkpoint checkpoints/best.pt --output exports/encoder.onnx
python -m export.to_tflite --config config.yaml --onnx exports/encoder.onnx --output exports/encoder.tflite --quantize int8
python -m export.to_coreml --config config.yaml --onnx exports/encoder.onnx --output exports/encoder.mlpackage --precision fp16

# 7. Run tests
pytest tests/ -v
```

---

## 3. Acceptance Criteria Checklist

| Criterion | Target | Verification |
|---|---|---|
| EER on FVC2004 held-out | < 5% | `eval_results/metrics.json` |
| ROC/DET curves generated | Yes | `eval_results/roc_det.png` |
| Rank-1 Identification | > 95% | `eval_results/metrics.json` |
| ONNX export parity | Max diff < 1e-4 | `test_export.py::test_onnx_parity` |
| TFLite INT8 export | Runs, < 5% accuracy drop | Manual verification on device |
| CoreML FP16 export | Runs on iOS simulator | Manual verification |
| Deterministic inference | Bitwise identical | `test_model.py::test_encoder_deterministic` |
| L2 normalized embeddings | $\|e\|_2 = 1 \pm 1e-5$ | `test_model.py::test_encoder_end_to_end` |
| ArcFace gradient flow | No NaN, non-zero | `test_loss.py::test_arcface_gradient` |

---

## 4. Deliverables Summary

| File / Artifact | Purpose |
|---|---|
| `checkpoints/best.pt` | Best model weights (encoder + ArcFace classifier) |
| `exports/encoder.onnx` | ONNX model (dynamic batch, opset 17) |
| `exports/encoder.tflite` | TFLite INT8 quantized (Android) |
| `exports/encoder.mlpackage` | CoreML FP16 (iOS/macOS) |
| `eval_results/metrics.json` | EER, AUC, TAR@FAR, Rank-1 |
| `eval_results/roc_det.png` | ROC & DET curves |
| `tests/` | Unit tests passing |
| `config.yaml` | Fully reproducible configuration |

**PHASE 1 COMPLETE.**  
The output embedding dimension is 256-d, L2-normalized, ready for Phase 2 (Cancelable Keystore & Key Management).
