# phase1_encoder/data/preprocessing.py
"""
Fingerprint preprocessing pipeline:
1. Load grayscale
2. CLAHE contrast enhancement
3. ROI segmentation (simple threshold + morphology)
4. Center crop with margin
5. Resize to target size
6. Normalize to [-1, 1] (matches ArcFace convention)
"""
import cv2
import numpy as np
from typing import Tuple

def clahe_enhance(img: np.ndarray, clip_limit: float = 2.0, tile_grid: Tuple[int, int] = (8, 8)) -> np.ndarray:
    """Apply CLAHE to fingerprint image."""
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
    return clahe.apply(img)

def segment_roi(img: np.ndarray, margin_frac: float = 0.1) -> Tuple[int, int, int, int]:
    """
    Simple ROI segmentation: threshold -> largest component -> bounding box -> margin.
    Returns (x, y, w, h) of ROI.
    """
    # Threshold (fingerprint ridges are darker)
    _, thresh = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    
    # Find largest connected component
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(thresh, connectivity=8)
    if num_labels <= 1:
        # Fallback: whole image
        h, w = img.shape
        return 0, 0, w, h
    
    # Ignore background (label 0)
    largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    x, y, w, h, _ = stats[largest_label]
    
    # Add margin
    margin_x = int(w * margin_frac)
    margin_y = int(h * margin_frac)
    x = max(0, x - margin_x)
    y = max(0, y - margin_y)
    w = min(img.shape[1] - x, w + 2 * margin_x)
    h = min(img.shape[0] - y, h + 2 * margin_y)
    
    return x, y, w, h

def preprocess_image(
    img_path: str,
    target_size: Tuple[int, int] = (96, 96),
    clahe_clip: float = 2.0,
    clahe_grid: Tuple[int, int] = (8, 8),
    roi_margin: float = 0.1
) -> np.ndarray:
    """
    Full preprocessing pipeline. Returns float32 array in [-1, 1], shape (H, W).
    """
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Failed to load image: {img_path}")
    
    # CLAHE
    img = clahe_enhance(img, clahe_clip, clahe_grid)
    
    # ROI crop
    x, y, w, h = segment_roi(img, roi_margin)
    roi = img[y:y+h, x:x+w]
    
    # Resize
    roi = cv2.resize(roi, target_size[::-1], interpolation=cv2.INTER_AREA)  # cv2 uses (W, H)
    
    # Normalize to [-1, 1]
    roi = roi.astype(np.float32) / 127.5 - 1.0
    
    return roi  # (H, W)

# --- Test hook ---
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        out = preprocess_image(sys.argv[1])
        print(f"Shape: {out.shape}, Range: [{out.min():.3f}, {out.max():.3f}], Mean: {out.mean():.3f}")
