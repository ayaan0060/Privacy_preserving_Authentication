# phase1_encoder/data/dataset.py
"""
PyTorch Dataset for fingerprint pairs/triplets.
Supports:
- Identification split (disjoint subjects train/val/test)
- Verification pairs (genuine + impostor)
"""
import os
import random
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
try:
    import albumentations as A
    from albumentations.pytorch import ToTensorV2
    HAS_ALBUMENTATIONS = True
except ImportError:
    HAS_ALBUMENTATIONS = False
    A = None
    ToTensorV2 = None

from .preprocessing import preprocess_image

class FingerprintDataset(Dataset):
    """
    Directory structure expected:
    root/
      subject_001/
        1_1.png
        1_2.png
        ...
      subject_002/
        ...
    """
    def __init__(
        self,
        root: str | Path,
        target_size: Tuple[int, int] = (96, 96),
        transform: A.Compose | None = None,
        preprocess_kwargs: dict | None = None,
    ):
        self.root = Path(root)
        self.target_size = target_size
        self.transform = transform
        self.preprocess_kwargs = preprocess_kwargs or {}
        
        # Build subject -> image list mapping
        self.subjects: List[str] = sorted([d.name for d in self.root.iterdir() if d.is_dir()])
        self.subject_to_idx: Dict[str, int] = {s: i for i, s in enumerate(self.subjects)}
        self.samples: List[Tuple[Path, int]] = []  # (img_path, subject_idx)
        
        for subj in self.subjects:
            subj_dir = self.root / subj
            imgs = sorted(list(subj_dir.glob("*.png")) + list(subj_dir.glob("*.bmp")) + list(subj_dir.glob("*.jpg")))
            for img_path in imgs:
                self.samples.append((img_path, self.subject_to_idx[subj]))
        
        print(f"[Dataset] {len(self.subjects)} subjects, {len(self.samples)} images")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        img_path, label = self.samples[idx]
        
        # Preprocess (numpy)
        img = preprocess_image(str(img_path), self.target_size, **self.preprocess_kwargs)  # (H, W) in [-1, 1]
        img = np.expand_dims(img, axis=0)  # (1, H, W) for albumentations
        
        # Augmentations (expects H, W, C or C, H, W)
        if self.transform:
            # Albumentations expects H, W, C
            img = img.transpose(1, 2, 0)  # (H, W, 1)
            augmented = self.transform(image=img)
            img = augmented["image"]  # (H, W, 1) or (C, H, W) if ToTensorV2
            if img.ndim == 3 and img.shape[-1] == 1:
                img = img.transpose(2, 0, 1)  # (1, H, W)
        
        # Ensure tensor
        if not isinstance(img, torch.Tensor):
            img = torch.from_numpy(img).float()
        
        return img, label

    def get_subject_indices(self) -> Dict[int, List[int]]:
        """Return mapping subject_idx -> list of sample indices."""
        mapping: Dict[int, List[int]] = {}
        for idx, (_, label) in enumerate(self.samples):
            mapping.setdefault(label, []).append(idx)
        return mapping


class VerificationPairDataset(Dataset):
    """
    Generates genuine and impostor pairs on-the-fly for verification evaluation.
    """
    def __init__(
        self,
        base_dataset: FingerprintDataset,
        num_pairs: int,
        genuine_ratio: float = 0.5,
        seed: int = 42,
    ):
        self.base = base_dataset
        self.num_pairs = num_pairs
        self.genuine_ratio = genuine_ratio
        self.rng = random.Random(seed)
        self.subject_indices = base_dataset.get_subject_indices()
        self.subjects = list(self.subject_indices.keys())
        self.pairs = self._generate_pairs()

    def _generate_pairs(self) -> List[Tuple[int, int, int]]:
        """Returns list of (idx1, idx2, label) where label=1 for genuine."""
        pairs = []
        n_genuine = int(self.num_pairs * self.genuine_ratio)
        n_impostor = self.num_pairs - n_genuine
        
        # Genuine pairs
        for _ in range(n_genuine):
            subj = self.rng.choice(self.subjects)
            idxs = self.subject_indices[subj]
            if len(idxs) < 2:
                continue
            i1, i2 = self.rng.sample(idxs, 2)
            pairs.append((i1, i2, 1))
        
        # Impostor pairs
        for _ in range(n_impostor):
            subj1, subj2 = self.rng.sample(self.subjects, 2)
            i1 = self.rng.choice(self.subject_indices[subj1])
            i2 = self.rng.choice(self.subject_indices[subj2])
            pairs.append((i1, i2, 0))
        
        self.rng.shuffle(pairs)
        return pairs

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, int]:
        i1, i2, label = self.pairs[idx]
        img1, _ = self.base[i1]
        img2, _ = self.base[i2]
        return img1, img2, label


def get_train_augmentations(cfg: dict) -> A.Compose:
    """Build albumentations pipeline from config."""
    augs = []
    
    # Geometric
    if cfg.get("rotation_degrees", 0) > 0:
        augs.append(A.Rotate(limit=cfg["rotation_degrees"], p=0.5, border_mode=cv2.BORDER_REFLECT_101))
    
    # Elastic distortion (simulates finger pressure)
    if cfg.get("elastic_alpha", 0) > 0:
        augs.append(A.ElasticTransform(
            alpha=cfg["elastic_alpha"],
            sigma=cfg["elastic_sigma"],
            alpha_affine=cfg["elastic_alpha"] * 0.03,
            p=0.3,
            border_mode=cv2.BORDER_REFLECT_101,
        ))
    
    # Cutout (simulates occlusion/dirt)
    if cfg.get("cutout_prob", 0) > 0:
        augs.append(A.CoarseDropout(
            max_holes=1,
            max_height=cfg["cutout_size"],
            max_width=cfg["cutout_size"],
            min_holes=1,
            min_height=cfg["cutout_size"] // 2,
            min_width=cfg["cutout_size"] // 2,
            fill_value=-1.0,  # Matches normalized range
            p=cfg["cutout_prob"],
        ))
    
    # Photometric
    if cfg.get("brightness_contrast_prob", 0) > 0:
        augs.append(A.RandomBrightnessContrast(
            brightness_limit=0.2,
            contrast_limit=0.2,
            p=cfg["brightness_contrast_prob"],
        ))
    
    # Always apply: ToTensor (converts to CxHxW float32)
    augs.append(ToTensorV2())
    
    return A.Compose(augs)


def build_dataloaders(cfg: dict) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """Build train/val/test loaders with subject-disjoint splits."""
    from sklearn.model_selection import train_test_split
    
    # Full dataset (no augment yet)
    full_dataset = FingerprintDataset(
        root=cfg["data"]["processed_dir"],
        target_size=tuple(cfg["data"]["img_size"]),
        preprocess_kwargs={
            "clahe_clip": cfg["preprocess"]["clahe_clip_limit"],
            "clahe_grid": tuple(cfg["preprocess"]["clahe_tile_grid"]),
            "roi_margin": cfg["preprocess"]["roi_margin"],
        },
    )
    
    # Subject-disjoint split
    subjects = full_dataset.subjects
    train_subjs, test_subjs = train_test_split(
        subjects, test_size=cfg["data"]["test_split"], random_state=cfg["seed"], shuffle=True
    )
    train_subjs, val_subjs = train_test_split(
        train_subjs, test_size=cfg["data"]["val_split"] / (1 - cfg["data"]["test_split"]),
        random_state=cfg["seed"], shuffle=True
    )
    
    def filter_by_subjects(subj_list: List[str]) -> List[int]:
        return [i for i, (_, label) in enumerate(full_dataset.samples) if full_dataset.subjects[label] in subj_list]
    
    train_idx = filter_by_subjects(train_subjs)
    val_idx = filter_by_subjects(val_subjs)
    test_idx = filter_by_subjects(test_subjs)
    
    # Subsets
    train_subset = torch.utils.data.Subset(full_dataset, train_idx)
    val_subset = torch.utils.data.Subset(full_dataset, val_idx)
    test_subset = torch.utils.data.Subset(full_dataset, test_idx)
    
    # Augmentations for training only
    train_augs = get_train_augmentations(cfg["augment"])
    # Wrap subsets to apply augmentations
    class AugmentedSubset(Dataset):
        def __init__(self, subset, transform):
            self.subset = subset
            self.transform = transform
        def __len__(self): return len(self.subset)
        def __getitem__(self, idx):
            img, label = self.subset[idx]
            # img is already tensor (1, H, W) from base dataset
            # Convert to numpy for albumentations
            img_np = img.numpy().transpose(1, 2, 0)  # (H, W, 1)
            aug = self.transform(image=img_np)
            img_aug = aug["image"]
            if not isinstance(img_aug, torch.Tensor):
                img_aug = torch.from_numpy(img_aug).float()
            return img_aug, label
    
    train_dataset = AugmentedSubset(train_subset, train_augs)
    val_dataset = AugmentedSubset(val_subset, A.Compose([ToTensorV2()]))  # No augment
    test_dataset = AugmentedSubset(test_subset, A.Compose([ToTensorV2()]))
    
    # DataLoaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=cfg["train"]["batch_size"],
        shuffle=True,
        num_workers=cfg["data"]["num_workers"],
        pin_memory=cfg["data"]["pin_memory"],
        drop_last=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=cfg["eval"]["batch_size"],
        shuffle=False,
        num_workers=cfg["data"]["num_workers"],
        pin_memory=cfg["data"]["pin_memory"],
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=cfg["eval"]["batch_size"],
        shuffle=False,
        num_workers=cfg["data"]["num_workers"],
        pin_memory=cfg["data"]["pin_memory"],
    )
    
    return train_loader, val_loader, test_loader
