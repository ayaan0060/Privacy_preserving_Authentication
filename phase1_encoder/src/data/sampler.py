# phase1_encoder/src/data/sampler.py
import numpy as np
from torch.utils.data import Sampler
from typing import Iterator, List, Dict
import random

class PKSampler(Sampler[List[int]]):
    """
    Samples P identities, K samples each -> Batch size P*K.
    Enables Batch-Hard mining inside the batch (no global mining overhead).
    """
    def __init__(self, labels: np.ndarray, p: int, k: int, shuffle: bool = True):
        self.labels = labels
        self.p = p
        self.k = k
        self.batch_size = p * k
        self.shuffle = shuffle
        
        self.label_to_indices: Dict[int, np.ndarray] = {}
        for idx, label in enumerate(labels):
            if label not in self.label_to_indices:
                self.label_to_indices[label] = []
            self.label_to_indices[label].append(idx)
        
        self.label_to_indices = {lbl_key: np.array(v) for lbl_key, v in self.label_to_indices.items()}
        self.valid_labels = [l for l, v in self.label_to_indices.items() if len(v) >= k]
        
        if len(self.valid_labels) < p:
            raise ValueError(f"Not enough identities with >= {k} samples. Found {len(self.valid_labels)}, need {p}.")
        
        self.num_batches = len(labels) // self.batch_size

    def __iter__(self) -> Iterator[List[int]]:
        for _ in range(self.num_batches):
            batch_indices = []
            # Sample P unique identities
            selected_labels = np.random.choice(self.valid_labels, size=self.p, replace=False)
            
            for label in selected_labels:
                indices = self.label_to_indices[label]
                # Sample K instances; replace=False is safe since valid_labels guarantees len >= k
                chosen = np.random.choice(indices, size=self.k, replace=len(indices) < self.k)
                batch_indices.extend(chosen)
            
            if self.shuffle:
                np.random.shuffle(batch_indices)
            yield batch_indices

    def __len__(self) -> int:
        return self.num_batches
