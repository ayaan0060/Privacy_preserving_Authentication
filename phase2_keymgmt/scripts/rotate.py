# phase2_keymgmt/scripts/rotate.py
"""
Rotate User Key (Cancelable Biometric Revocation).
"""
import argparse
import logging
import sys
import os
from pathlib import Path

# Add phase2_keymgmt root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from keystore.software import SoftwareSecureKeyStore
from keystore.interface import KeyNotFoundError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Rotate User Key (Cancelable Biometric Revocation)")
    parser.add_argument('--user_id', required=True, help='User ID')
    parser.add_argument('--reason', default='scheduled_rotation', help='Reason for key rotation')
    parser.add_argument('--storage', default='./keystore_data', help='Keystore storage directory')
    args = parser.parse_args()

    store = SoftwareSecureKeyStore(storage_dir=args.storage, use_mlock=False)

    try:
        # Show history before
        versions_before = store.list_versions(args.user_id)
        print(f"History Before Rotation: {[(v.version, not v.is_active) for v in versions_before]}")

        new_version = store.rotate_key(args.user_id, reason=args.reason)

        # Show history after
        versions_after = store.list_versions(args.user_id)
        print(f"History After Rotation:  {[(v.version, not v.is_active) for v in versions_after]}")
        print(f"✅ User '{args.user_id}' rotated to Version {new_version.version}")

    except KeyNotFoundError as e:
        log.error(f"Rotation failed: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
