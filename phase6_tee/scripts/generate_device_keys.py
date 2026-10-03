#!/usr/bin/env python3
# phase6_tee/scripts/generate_device_keys.py
"""
Device Key Provisioning Script.
Generates device signing keys for simulation or production enrollment.
"""
import argparse
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tee.device_keys import DeviceKeyManager


def main():
    parser = argparse.ArgumentParser(description="Generate device signing keys")
    parser.add_argument("--key-dir", type=Path, default=Path("./exports/device_keys"))
    parser.add_argument("--password", type=str, help="Encryption password (env: DEVICE_KEY_PASSWORD)")
    parser.add_argument("--rotate", action="store_true", help="Rotate existing key")
    args = parser.parse_args()
    
    print(f"Generating device keys in: {args.key_dir}")
    
    mgr = DeviceKeyManager(args.key_dir, master_password=args.password)
    
    if args.rotate:
        new_id = mgr.rotate_key()
        print(f"Rotated device key. New ID: {new_id}")
    else:
        print(f"Device ID: {mgr.get_device_id()}")
        print(f"Public Key (PEM):")
        print(mgr.get_public_key_pem().decode())
    
    mgr.close()


if __name__ == "__main__":
    main()
