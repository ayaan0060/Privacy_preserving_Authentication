# phase1_encoder/tests/test_preprocessing.py
import pytest
import numpy as np
import cv2
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.preprocessing import preprocess_image, clahe_enhance, segment_roi

def test_clahe_enhance():
    img = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
    out = clahe_enhance(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8
    assert out.min() >= 0 and out.max() <= 255

def test_segment_roi():
    # Synthetic fingerprint-like image
    img = np.zeros((200, 200), dtype=np.uint8)
    cv2.rectangle(img, (50, 50), (150, 150), 255, -1)
    cv2.rectangle(img, (60, 60), (140, 140), 0, -1)  # Ridge pattern
    x, y, w, h = segment_roi(img, margin_frac=0.1)
    assert w > 0 and h > 0
    assert x >= 0 and y >= 0

def test_preprocess_image_output_range(tmp_path):
    # Create dummy image
    img = np.random.randint(0, 256, (200, 200), dtype=np.uint8)
    img_path = tmp_path / "test.png"
    cv2.imwrite(str(img_path), img)
    
    out = preprocess_image(str(img_path), target_size=(96, 96))
    assert out.shape == (96, 96)
    assert out.dtype == np.float32
    assert out.min() >= -1.0 - 1e-5
    assert out.max() <= 1.0 + 1e-5

def test_preprocess_deterministic(tmp_path):
    img = np.random.randint(0, 256, (200, 200), dtype=np.uint8)
    img_path = tmp_path / "test.png"
    cv2.imwrite(str(img_path), img)
    
    out1 = preprocess_image(str(img_path))
    out2 = preprocess_image(str(img_path))
    assert np.allclose(out1, out2)
