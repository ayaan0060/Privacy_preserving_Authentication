# phase3_fusion/src/data/fusion_dataset.py
"""
Dataset for FiLM Training.
Generates (embedding x, key k) pairs on-the-fly.
- x: Comes from Phase 1 Encoder (Frozen) applied to Fingerprint Images.
- k: Comes from Phase 2 HKDF Derivation (Seed -> k).
We pre-compute embeddings 'x' for speed (Encoder is frozen), 
then pair with dynamically derived 'k' per epoch (simulating key rotation).
"""
import os
import cv2
import torch
import numpy as np
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
from typing import List, Tuple, Dict
import logging
import sys
import hashlib, hmac, struct, math
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

log = logging.getLogger(__name__)

# --- VENDORED HKDF (Minimal) ---
def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    hash_len = 32
    n = math.ceil(length / hash_len)
    okm = bytearray()
    t = b''
    for i in range(1, n + 1):
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm.extend(t)
    return bytes(okm[:length])

def derive_key_vector_vendored(seed: bytes, domain_tag: str, user_id: str, key_version: int, dim: int = 256) -> np.ndarray:
    if len(seed) != 32: raise ValueError("Seed 32 bytes")
    info = f"{domain_tag}|{user_id}|{key_version}|FiLM_KeyVector".encode('utf-8')
    prk = hmac.new(b'\x00'*32, seed, hashlib.sha256).digest() # Extract(salt=0, IKM=seed)
    okm = _hkdf_expand(prk, info, dim * 4)
    fmt = f"<{dim}I"
    uint_vals = struct.unpack(fmt, okm)
    float_vals = [(v / 4294967296.0) * 2.0 - 1.0 for v in uint_vals] # [0,1) -> [-1,1]
    return np.array(float_vals, dtype=np.float32)

class FusionDataset(Dataset):
    """
    Pre-computes Encoder Embeddings (x) for all images.
    At __getitem__, samples a Key Version and Derives k.
    Returns: (x, k, label, user_id, key_version)
    """
    def __init__(
        self, 
        encoder,                  # Phase 1 Encoder (Frozen, Eval mode)
        data_root: str,           # SOCOFing Root
        phase2_config: dict,      # For domain_tag, key_vector_dim
        transform,                # Val Transform (CLAHE, Resize, Norm)
        roi_extractor,
        split: str = "train",     # "train" or "val"
        val_split_ratio: float = 0.1,
        seed: int = 42
    ):
        self.encoder = encoder
        self.encoder.eval()
        self.phase2_cfg = phase2_config
        self.domain_tag = phase2_config['project']['domain_separation_tag']
        self.key_dim = phase2_config['crypto']['key_vector_dim']
        
        # 1. Scan Files
        self.samples: List[Tuple[str, str]] = [] # (path, user_id_str)
        self.user_to_idx: Dict[str, int] = {}
        self._scan_directory(data_root)
        
        # 2. Train/Val Split by Identity (Disjoint Users)
        np.random.seed(seed)
        unique_users = list(self.user_to_idx.keys())
        np.random.shuffle(unique_users)
        n_val = max(1, int(len(unique_users) * val_split_ratio))
        val_users = set(unique_users[:n_val])
        train_users = set(unique_users[n_val:])
        
        target_users = val_users if split == "val" else train_users
        self.indices = [i for i, (_, uid) in enumerate(self.samples) if uid in target_users]
        
        # 3. Pre-compute Embeddings 'x'
        log.info(f"Pre-computing embeddings for {split} set ({len(self.indices)} samples)...")
        self.embeddings = self._precompute_embeddings(transform, roi_extractor)
        log.info("Embedding pre-computation done.")
        
        # 4. Key Version State
        self.user_versions: Dict[str, int] = {uid: 1 for uid in target_users}
        
        self.transform = transform
        self.roi_extractor = roi_extractor

    def _scan_directory(self, root: str):
        root_path = Path(root)
        if not root_path.exists():
            log.warning(f"Data root path {root} does not exist. Operating in dummy mode.")
            return
        for subj_dir in sorted(root_path.iterdir()):
            if not subj_dir.is_dir(): continue
            uid = subj_dir.name
            if uid not in self.user_to_idx:
                self.user_to_idx[uid] = len(self.user_to_idx)
            for img_path in sorted(subj_dir.glob("*.bmp")) + sorted(subj_dir.glob("*.png")):
                self.samples.append((str(img_path), uid))

    def _precompute_embeddings(self, transform, roi_extractor) -> Dict[int, np.ndarray]:
        embeddings = {}
        batch_paths = []
        batch_indices = []
        
        for idx in self.indices:
            path, _ = self.samples[idx]
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is None: continue
            img = roi_extractor(img)
            img = img.astype(np.float32) / 255.0
            img = np.expand_dims(img, -1)
            aug = transform(image=img)
            batch_paths.append(aug['image'])
            batch_indices.append(idx)
            
            if len(batch_paths) >= 64:
                self._encode_batch(batch_paths, batch_indices, embeddings)
                batch_paths, batch_indices = [], []
        
        if batch_paths:
            self._encode_batch(batch_paths, batch_indices, embeddings)
            
        return embeddings

    def _encode_batch(self, batch_tensors, batch_indices, embeddings_dict):
        batch = torch.stack(batch_tensors).to(next(self.encoder.parameters()).device)
        with torch.no_grad():
            embs = self.encoder(batch).cpu().numpy()
        for i, idx in enumerate(batch_indices):
            embeddings_dict[idx] = embs[i]

    def increment_key_versions(self):
        """Call at start of each epoch to simulate Key Rotation."""
        for uid in self.user_versions:
            self.user_versions[uid] += 1

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        real_idx = self.indices[idx]
        x = self.embeddings[real_idx] # (256,) np.float32
        _, uid = self.samples[real_idx]
        label = self.user_to_idx[uid]
        version = self.user_versions[uid]
        
        seed = hashlib.sha256(uid.encode()).digest()
        k = derive_key_vector_vendored(seed, self.domain_tag, uid, version, self.key_dim)
        
        return torch.from_numpy(x), torch.from_numpy(k), label, uid, version
