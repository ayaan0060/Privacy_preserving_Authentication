#!/usr/bin/env python3
"""
core/protocol.py

SINGLE SOURCE OF TRUTH for evaluation protocol definitions.

Protocol ALL  (headline):
  - Genuine pairs: every Real impression paired with every Altered impression
    (Easy, Medium, Hard) for the SAME subject and SAME finger.
  - Impostor pairs: Real impression of subject A paired with Real impression
    of subject B (A != B). |impostor| == |genuine|. Cross-subject only; no
    identity shared between the two sides of any impostor pair.
  - Pair list saved to: results/final/pairs_all.csv

Protocol EASY (secondary benchmark):
  - Genuine pairs: Real vs Altered-Easy only (same subject, same finger).
  - Impostor pairs: Real vs Real, cross-subject (A != B), |impostor| == |genuine|.
  - Pair list saved to: results/final/pairs_easy.csv

Both protocols:
  - Use ONLY the 90 held-out test subjects (results/raw/socofing_test_embeddings.npz).
  - tau chosen on the validation split under the SAME protocol, transferred to test.
  - Pair lists are deterministic given a seed + the test embeddings file.
  - Assertion: pairs_all and pairs_easy must not share the same genuine set.
"""

import csv
import random
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

import numpy as np

PROTOCOL_ALL  = "ALL"
PROTOCOL_EASY = "EASY"


class Pair(NamedTuple):
    path1: str
    path2: str
    label: int       # 1=genuine, 0=impostor
    alteration: str  # "easy" | "medium" | "hard" | "real"
    subject1: str
    subject2: str
    finger1: str
    finger2: str


def _get_subject(path: str) -> str:
    return Path(path).name.split('__')[0]


def _get_finger(path: str) -> str:
    fname = Path(path).name
    for tag in ['_CR', '_Obl', '_Zcut']:
        fname = fname.replace(tag, '')
    return fname.replace('.BMP', '')


def _get_alteration(path: str) -> str:
    if '/Altered-Easy/' in path:
        return 'easy'
    elif '/Altered-Medium/' in path:
        return 'medium'
    elif '/Altered-Hard/' in path:
        return 'hard'
    return 'real'


def build_pairs(
    test_npz_path: Path,
    seed: int = 42,
    protocols: Tuple[str, ...] = (PROTOCOL_ALL, PROTOCOL_EASY),
) -> Dict[str, List[Pair]]:
    """Build pair lists for each requested protocol from the test embedding file."""
    data = np.load(test_npz_path)
    paths = [str(p) for p in data['paths']]

    real_paths   = [p for p in paths if '/Real/' in p]
    easy_paths   = [p for p in paths if '/Altered-Easy/' in p]
    medium_paths = [p for p in paths if '/Altered-Medium/' in p]
    hard_paths   = [p for p in paths if '/Altered-Hard/' in p]

    def _by_finger(lst):
        d = {}
        for p in lst:
            d.setdefault(_get_finger(p), []).append(p)
        return d

    real_by_finger   = _by_finger(real_paths)
    easy_by_finger   = _by_finger(easy_paths)
    medium_by_finger = _by_finger(medium_paths)
    hard_by_finger   = _by_finger(hard_paths)

    def build_genuine(incl_levels):
        level_map = {'easy': easy_by_finger, 'medium': medium_by_finger, 'hard': hard_by_finger}
        genuine = []
        for fid, r_list in sorted(real_by_finger.items()):
            subj = _get_subject(r_list[0])
            for level in incl_levels:
                for r in r_list:
                    for a in level_map[level].get(fid, []):
                        genuine.append(Pair(
                            path1=r, path2=a, label=1, alteration=level,
                            subject1=subj, subject2=subj,
                            finger1=fid, finger2=fid,
                        ))
        return genuine

    def build_impostor(genuine, rng):
        real_by_subj = {}
        for p in real_paths:
            real_by_subj.setdefault(_get_subject(p), []).append(p)
        subjects = sorted(real_by_subj.keys())
        n_needed = len(genuine)
        impostors = []
        for _ in range(n_needed * 200):
            if len(impostors) >= n_needed:
                break
            s1, s2 = rng.sample(subjects, 2)
            p1 = rng.choice(real_by_subj[s1])
            p2 = rng.choice(real_by_subj[s2])
            impostors.append(Pair(
                path1=p1, path2=p2, label=0, alteration='real',
                subject1=s1, subject2=s2,
                finger1=_get_finger(p1), finger2=_get_finger(p2),
            ))
        if len(impostors) < n_needed:
            raise RuntimeError(f"Could not build {n_needed} impostor pairs")
        return impostors[:n_needed]

    result = {}
    rng = random.Random(seed)

    if PROTOCOL_ALL in protocols:
        g_all = build_genuine(('easy', 'medium', 'hard'))
        i_all = build_impostor(g_all, rng)
        pairs_all = g_all + i_all
        rng.shuffle(pairs_all)
        result[PROTOCOL_ALL] = pairs_all

    if PROTOCOL_EASY in protocols:
        g_easy = build_genuine(('easy',))
        i_easy = build_impostor(g_easy, rng)
        pairs_easy = g_easy + i_easy
        rng.shuffle(pairs_easy)
        result[PROTOCOL_EASY] = pairs_easy

    # Assertion: genuine sets must differ
    if PROTOCOL_ALL in result and PROTOCOL_EASY in result:
        all_gen  = {(p.path1, p.path2) for p in result[PROTOCOL_ALL]  if p.label == 1}
        easy_gen = {(p.path1, p.path2) for p in result[PROTOCOL_EASY] if p.label == 1}
        assert all_gen != easy_gen, "ASSERTION: ALL and EASY genuine sets are identical"
        assert easy_gen.issubset(all_gen), "ASSERTION: EASY genuine is not a subset of ALL genuine"

    return result


def save_pairs(pairs: List[Pair], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['path1','path2','label','alteration','subject1','subject2','finger1','finger2'])
        w.writeheader()
        for p in pairs:
            w.writerow(p._asdict())


def load_pairs(csv_path: Path) -> List[Pair]:
    pairs = []
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            pairs.append(Pair(
                path1=row['path1'], path2=row['path2'],
                label=int(row['label']), alteration=row['alteration'],
                subject1=row['subject1'], subject2=row['subject2'],
                finger1=row['finger1'], finger2=row['finger2'],
            ))
    return pairs


def pair_counts(pairs: List[Pair]) -> dict:
    genuine  = [p for p in pairs if p.label == 1]
    impostor = [p for p in pairs if p.label == 0]
    return {
        'total':          len(pairs),
        'genuine':        len(genuine),
        'impostor':       len(impostor),
        'genuine_easy':   sum(1 for p in genuine if p.alteration == 'easy'),
        'genuine_medium': sum(1 for p in genuine if p.alteration == 'medium'),
        'genuine_hard':   sum(1 for p in genuine if p.alteration == 'hard'),
    }
