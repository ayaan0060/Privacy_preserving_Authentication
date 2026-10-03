#!/usr/bin/env bash
# phase4_he/scripts/gen_keys.sh
set -euo pipefail

KEY_DIR="${1:-./exports/he_keys}"
FORCE="${2:-false}"

echo "=== GENERATING CKKS KEYS ==="
echo "Key directory: $KEY_DIR"
echo "Force overwrite: $FORCE"

python -c "
from he.context import HEContextManager
from he.params import DEFAULT_PARAMS
mgr = HEContextManager('$KEY_DIR', DEFAULT_PARAMS)
mgr.generate_keys(force=$FORCE)
print('Keys generated successfully')
"
