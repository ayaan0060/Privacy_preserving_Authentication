# phase1_encoder/data/download.py
"""
Download SOCOFing and FVC2004 datasets with checksum verification.
SOCOFing: https://github.com/seasonSH/MPALab-Research/tree/master/Fingerprint/SOCOFing
FVC2004:  http://bias.csr.unibo.it/fvc2004/download.asp (requires registration)
"""
import hashlib
import os
import requests
import tarfile
import zipfile
from pathlib import Path
from tqdm import tqdm

SOCOFING_URL = "https://github.com/seasonSH/MPALab-Research/raw/master/Fingerprint/SOCOFing/Real/Real.zip"
SOCOFING_SHA256 = "d41d8cd98f00b204e9800998ecf8427e"  # PLACEHOLDER — replace with actual after download

FVC2004_URL = "https://example.com/fvc2004_db1_a.zip"  # USER MUST PROVIDE
FVC2004_SHA256 = "PLACEHOLDER"

def download_file(url: str, dest: Path, expected_sha256: str | None = None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and expected_sha256:
        with open(dest, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() == expected_sha256:
                print(f"[OK] {dest.name} already present and verified.")
                return
    print(f"[DOWNLOAD] {url} -> {dest}")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True) as pbar:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                pbar.update(len(chunk))
    if expected_sha256:
        with open(dest, "rb") as f:
            actual = hashlib.sha256(f.read()).hexdigest()
        assert actual == expected_sha256, f"Checksum mismatch: {actual} != {expected_sha256}"
        print(f"[VERIFIED] {dest.name}")

def extract_archive(archive: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[EXTRACT] {archive} -> {out_dir}")
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive, "r") as z:
            z.extractall(out_dir)
    elif archive.suffix in (".tar", ".gz", ".tgz"):
        with tarfile.open(archive, "r:*") as t:
            t.extractall(out_dir)
    else:
        raise ValueError(f"Unsupported archive format: {archive.suffix}")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["socofing", "fvc2004", "both"], default="socofing")
    parser.add_argument("--root", type=Path, default=Path("./data/raw"))
    args = parser.parse_args()

    if args.dataset in ("socofing", "both"):
        zip_path = args.root / "SOCOFing_Real.zip"
        download_file(SOCOFING_URL, zip_path, SOCOFING_SHA256)
        extract_archive(zip_path, args.root / "SOCOFing")

    if args.dataset in ("fvc2004", "both"):
        zip_path = args.root / "FVC2004_DB1_A.zip"
        download_file(FVC2004_URL, zip_path, FVC2004_SHA256)
        extract_archive(zip_path, args.root / "FVC2004")

if __name__ == "__main__":
    main()
