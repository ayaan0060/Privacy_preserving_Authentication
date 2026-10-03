# phase2_keymgmt/scripts/keycli.py
"""
Key management CLI for development and debugging.
"""
import argparse
import sys, os
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from keystore.software import SoftwareSecureKeyStore
from keystore.interface import KeyExistsError, KeyNotFoundError, KeyRevokedError

def main():
    parser = argparse.ArgumentParser(description="Cancelable Biometric Key Management")
    parser.add_argument("--storage", type=Path, default=Path("./keystore_data"), help="Keystore directory")
    parser.add_argument("--master-key", type=str, help="Hex-encoded master key (32 bytes)")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # gen
    gen = subparsers.add_parser("gen", help="Generate new key for user")
    gen.add_argument("user_id", type=str)
    gen.add_argument("--force", action="store_true", help="Overwrite existing active key")
    
    # rotate
    rot = subparsers.add_parser("rotate", help="Rotate user's key")
    rot.add_argument("user_id", type=str)
    rot.add_argument("--reason", type=str, default="scheduled_rotation")
    
    # list
    lst = subparsers.add_parser("list", help="List key versions for user")
    lst.add_argument("user_id", type=str)
    
    # show
    show = subparsers.add_parser("show", help="Show key material (DEV ONLY)")
    show.add_argument("user_id", type=str)
    show.add_argument("--version", type=int, default=None)
    
    # delete
    delete = subparsers.add_parser("delete", help="Delete all keys for user")
    delete.add_argument("user_id", type=str)
    
    # test-revocation
    test = subparsers.add_parser("test-revocation", help="Test revocation effectiveness")
    test.add_argument("user_id", type=str)
    
    args = parser.parse_args()
    
    # Parse master key
    if args.master_key:
        master_key = bytes.fromhex(args.master_key)
        assert len(master_key) == 32
    else:
        master_key = None  # Auto-generate
    
    store = SoftwareSecureKeyStore(
        storage_dir=args.storage,
        master_key=master_key,
        use_mlock=False,
    )
    
    try:
        if args.command == "gen":
            try:
                version = store.generate_seed(args.user_id)
                print(f"Generated key v{version.version} for {args.user_id}")
            except KeyExistsError as e:
                if args.force:
                    store.rotate_key(args.user_id, "forced_regeneration")
                    print(f"Forced rotation for {args.user_id}")
                else:
                    print(f"Error: {e}")
                    sys.exit(1)
        
        elif args.command == "rotate":
            version = store.rotate_key(args.user_id, args.reason)
            print(f"Rotated {args.user_id} to v{version.version} (reason: {args.reason})")
        
        elif args.command == "list":
            versions = store.list_versions(args.user_id)
            print(f"Key versions for {args.user_id}:")
            for v in versions:
                status = "ACTIVE" if v.is_active else f"REVOKED ({v.revoked_reason})"
                print(f"  v{v.version}: {status} (created: {v.created_at.isoformat()})")
        
        elif args.command == "show":
            material = store.get_key_material(args.user_id, args.version)
            print(f"User: {args.user_id}")
            print(f"Version: {material.version.version}")
            print(f"Seed (hex): {material.seed.hex()}")
            print(f"Key vector: shape={material.key_vector.shape}, "
                  f"range=[{material.key_vector.min():.4f}, {material.key_vector.max():.4f}], "
                  f"mean={material.key_vector.mean():.4f}, std={material.key_vector.std():.4f}")
            print(f"First 8: {material.key_vector[:8]}")
        
        elif args.command == "delete":
            if store.delete_user(args.user_id):
                print(f"Deleted all keys for {args.user_id}")
            else:
                print(f"No keys found for {args.user_id}")
        
        elif args.command == "test-revocation":
            # Generate, rotate, test
            v1 = store.generate_seed(args.user_id)
            v2 = store.rotate_key(args.user_id, "test")
            
            mat1 = store.get_key_material(args.user_id, v1.version)
            mat2 = store.get_key_material(args.user_id, v2.version)
            
            sim = np.dot(mat1.key_vector, mat2.key_vector)
            print(f"Key vector cosine similarity v{v1.version} vs v{v2.version}: {sim:.6f}")
            print(f"Threshold for unlinkability: < 0.15")
            print(f"Result: {'PASS (unlinkable)' if abs(sim) < 0.15 else 'FAIL (correlated)'}")
    
    except (KeyNotFoundError, KeyRevokedError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
