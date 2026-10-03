# phase1_encoder/src/data/dataset.py
import os
import cv2
import numpy as np
from pathlib import Path
from torch.utils.data import Dataset
from typing import List, Tuple, Dict, Optional
import logging

log = logging.getLogger(__name__)

class FingerprintDataset(Dataset):
    """
    Expects directory structure:
    root/
      subject_001/
        1_1.png
        1_2.png
      subject_002/
        2_1.png
    Or flat files with labels in CSV (FVC style).
    """
    def __init__(
        self, 
        root: str, 
        transform=None, 
        roi_extractor=None,
        label_map: Optional[Dict[str, int]] = None,
        is_fvc: bool = False
    ):
        self.root = Path(root)
        self.transform = transform
        self.roi_extractor = roi_extractor
        self.is_fvc = is_fvc
        
        self.samples: List[Tuple[str, int]] = [] # (path, label_idx)
        self.label_to_idx: Dict[str, int] = label_map or {}
        self.idx_to_label: Dict[int, str] = {}
        
        self._scan_directory()
        self._finalize_labels()
        log.info(f"Loaded {len(self.samples)} samples, {len(self.label_to_idx)} identities from {root}")

    def _scan_directory(self):
        if self.is_fvc:
            # FVC: files like 101_1.tif, 101_2.tif ... label is prefix before '_'
            for f in sorted(self.root.glob("*.tif")) + sorted(self.root.glob("*.bmp")) + sorted(self.root.glob("*.png")):
                label_str = f.stem.split('_')[0]
                if label_str not in self.label_to_idx:
                    self.label_to_idx[label_str] = len(self.label_to_idx)
                self.samples.append((str(f), self.label_to_idx[label_str]))
        else:
            # SOCOFing: subdirs per subject
            for subj_dir in sorted(self.root.iterdir()):
                if not subj_dir.is_dir(): continue
                label_str = subj_dir.name
                if label_str not in self.label_to_idx:
                    self.label_to_idx[label_str] = len(self.label_to_idx)
                for img_path in sorted(subj_dir.glob("*.bmp")) + sorted(subj_dir.glob("*.png")):
                    self.samples.append((str(img_path), self.label_to_idx[label_str]))

    def _finalize_labels(self):
        self.idx_to_label = {v: k for k, v in self.label_to_idx.items()}
        # Convert to numpy for faster sampler access
        self.labels = np.array([s[1] for s in self.samples], dtype=np.int64)

    def __len__(self): return len(self.samples)

    def __getitem__(self, idx: int):
        path, label = self.samples[idx]
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise IOError(f"Failed to read {path}")
        
        if self.roi_extractor:
            img = self.roi_extractor(img)
        
        # Albumentations expects HWC
        img = img.astype(np.float32) / 255.0 # Normalize to [0,1] for CLAHE input
        img = np.expand_dims(img, axis=-1)   # (H, W, 1)
        
        if self.transform:
            augmented = self.transform(image=img)
            img = augmented['image'] # Returns Tensor (C, H, W) normalized [-1,1]
            
        return img, label

    def get_labels(self) -> np.ndarray:
        return self.labels
