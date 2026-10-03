# Phase 3 — FiLM Fusion Network

## Overview
Phase 3 implements feature-wise linear modulation (FiLM) for cancelable biometrics:
$$t = \text{Norm}(\gamma(k) \odot x + \beta(k))$$
where $x$ is the L2-normalized 256-d fingerprint feature vector from Phase 1, and $k$ is the 256-d key vector derived via HKDF in Phase 2.

## Project Structure
```
phase3_fusion/
├── config.yaml
├── requirements.txt
├── README.md
├── src/
│   ├── models/
│   │   ├── film.py
│   │   └── combined.py
│   ├── data/
│   │   └── fusion_dataset.py
│   ├── engine/
│   │   ├── trainer.py
│   │   └── evaluator.py
│   └── export/
│       └── to_onnx.py
├── scripts/
│   ├── train_film.py
│   ├── eval_fusion.py
│   └── export_fusion.py
└── tests/
    ├── test_film_layer.py
    ├── test_unlinkability.py
    └── test_integration.py
```

## How to Run Phase 3

### 1. Install Dependencies
```bash
cd phase3_fusion
pip install -r requirements.txt
export CANCELABLE_BIO_MASTER_KEY="super-secret-dev-key-change-in-prod-32chars!!"
```

### 2. Verify Artifacts
Ensure Phase 1 and Phase 2 configs and checkpoints exist:
- `../phase1_encoder/outputs/phase1/checkpoints/best.ckpt`
- `../phase1_encoder/config.yaml`
- `../phase2_keymgmt/config.yaml`

### 3. Run Unit & Integration Tests
```bash
pytest tests/ -v
```

### 4. Train FiLM Generator
```bash
python scripts/train_film.py
```

### 5. Evaluate Unlinkability & Verification
```bash
python scripts/eval_fusion.py --ckpt outputs/phase3/checkpoints/best.ckpt
```

### 6. Export Combined ONNX Models
```bash
python scripts/export_fusion.py --ckpt outputs/phase3/checkpoints/best.ckpt --out_dir exports/phase3
```

## Completion Checklist
- [x] FiLM Generator predicts $\gamma > 0$ (Softplus) and $\beta \in [-1, 1]$ (Tanh).
- [x] Identity initialization ($\gamma \approx 1, \beta \approx 0$) ensures stable early training.
- [x] Unlinkability test passes: Mean similarity between templates $t_1, t_2$ for different $k_1, k_2$ is $\approx 0$ with std $\approx 1/\sqrt{256} = 0.0625$.
- [x] Combined model export (`fusion_combined.onnx`) verified.
