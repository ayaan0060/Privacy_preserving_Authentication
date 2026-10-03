# phase1_encoder/src/data/transforms.py
import albumentations as A
from albumentations.pytorch import ToTensorV2
import cv2
import numpy as np

def get_train_transforms(img_size: tuple, clahe_clip: float, clahe_tile: tuple) -> A.Compose:
    """
    Training augmentations for fingerprint domain.
    Justification:
    - ElasticTransform: Simulates skin distortion/pressure variation (critical for fingerprints).
    - Rotate: Small in-plane rotation (fingers rarely placed perfectly upright).
    - GaussianBlur/Noise: Sensor noise simulation.
    - CLAHE: Applied *before* geometric transforms to enhance ridges consistently.
    """
    return A.Compose([
        # 1. Contrast Enhancement (Deterministic per image, but helps ridge visibility)
        A.CLAHE(clip_limit=clahe_clip, tile_grid_size=clahe_tile, p=1.0),
        
        # 2. Geometric Augmentations (Domain Specific)
        A.ElasticTransform(
            alpha=1.0, sigma=20.0, alpha_affine=10.0, 
            interpolation=cv2.INTER_LINEAR, border_mode=cv2.BORDER_REFLECT_101, p=0.5
        ),
        A.Rotate(limit=15, interpolation=cv2.INTER_LINEAR, border_mode=cv2.BORDER_REFLECT_101, p=0.7),
        A.ShiftScaleRotate(shift_limit=0.05, scale_limit=0.1, rotate_limit=0, p=0.5),
        
        # 3. Photometric / Noise
        A.GaussNoise(var_limit=(10.0, 50.0), p=0.3),
        A.GaussianBlur(blur_limit=(3, 5), p=0.2),
        A.RandomBrightnessContrast(brightness_limit=0.1, contrast_limit=0.1, p=0.3),
        
        # 4. Final Prep
        A.Resize(img_size[0], img_size[1], interpolation=cv2.INTER_AREA),
        A.Normalize(mean=(0.5,), std=(0.5,)), # [-1, 1]
        ToTensorV2(),
    ])

def get_val_transforms(img_size: tuple, clahe_clip: float, clahe_tile: tuple) -> A.Compose:
    """Validation/Test: Deterministic CLAHE + Resize + Normalize only."""
    return A.Compose([
        A.CLAHE(clip_limit=clahe_clip, tile_grid_size=clahe_tile, p=1.0),
        A.Resize(img_size[0], img_size[1], interpolation=cv2.INTER_AREA),
        A.Normalize(mean=(0.5,), std=(0.5,)),
        ToTensorV2(),
    ])

# --- ROI Extraction (Run once during dataset init or on-the-fly) ---
def extract_roi_fixed_center(img: np.ndarray, target_size: tuple = (96, 96)) -> np.ndarray:
    """
    SIMULATION NOTE: Production systems use segmentation (U-Net) or orientation-field 
    based core-point detection (e.g., Poincare index) to find fingerprint core.
    Fixed center crop is a STRONG ASSUMPTION valid only for centered datasets (SOCOFing/FVC).
    Real deployment REQUIRES a robust segmentation/core-detection model here.
    """
    h, w = img.shape[:2]
    # Assume fingerprint centered in image (true for SOCOFing Real, approx for FVC)
    crop_size = min(h, w)
    y1 = (h - crop_size) // 2
    x1 = (w - crop_size) // 2
    roi = img[y1:y1+crop_size, x1:x1+crop_size]
    return cv2.resize(roi, target_size, interpolation=cv2.INTER_AREA)
