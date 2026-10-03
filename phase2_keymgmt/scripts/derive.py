# phase2_keymgmt/scripts/derive.py
"""
Derive FiLM key vector 'k' for a user's active key version.
"""
import argparse
import logging
import sys
import os
# pyrefly: ignore [missing-import]
import numpy as np
from pathlib import Path

# Add phase2_keymgmt root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from keystore.software import SoftwareSecureKeyStore
from keystore.interface import KeyNotFoundError, KeyRevokedError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Derive FiLM Key Vector 'k' for active key version")
    parser.add_argument('--user_id', required=True, help='User ID')
    parser.add_argument('--output', required=True, help='Output .npy file for key vector k')
    parser.add_argument('--storage', default='./keystore_data', help='Keystore storage directory')
    parser.add_argument('--version', type=int, default=None, help='Optional specific version')
    args = parser.parse_args()

    store = SoftwareSecureKeyStore(storage_dir=args.storage, use_mlock=False)

    try:
        material = store.get_key_material(args.user_id, version=args.version)
        k = material.key_vector
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(output_path, k)
        print(f"✅ Derived key vector 'k' for User '{args.user_id}' (Version {material.version.version})")
        print(f"   Shape: {k.shape}, Dtype: {k.dtype}")
        print(f"   Range: [{k.min():.4f}, {k.max():.4f}]")
        print(f"   L2 Norm: {np.linalg.norm(k):.4f}")
        print(f"   Saved to: {output_path}")
    except (KeyNotFoundError, KeyRevokedError) as e:
        log.error(f"Derivation failed: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        log.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
