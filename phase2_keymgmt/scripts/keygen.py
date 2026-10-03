# phase2_keymgmt/scripts/keygen.py
"""
Enroll new user (generate seed v1).
"""
import argparse
import logging
import sys
import os
from pathlib import Path

# Add phase2_keymgmt root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from keystore.software import SoftwareSecureKeyStore
from keystore.interface import KeyExistsError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Enroll new user (Generate Seed v1)")
    parser.add_argument('--user_id', required=True, help='Unique User Identifier')
    parser.add_argument('--storage', default='./keystore_data', help='Keystore storage directory')
    args = parser.parse_args()

    store = SoftwareSecureKeyStore(storage_dir=args.storage, use_mlock=False)

    try:
        version = store.generate_seed(args.user_id)
        print(f"✅ User '{args.user_id}' enrolled successfully.")
        print(f"   Version: {version.version}")
        print(f"   Created: {version.created_at}")
    except KeyExistsError as e:
        log.error(f"Enrollment failed: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
