#!/usr/bin/env bash
# phase7_integration/scripts/run_adversarial.sh
set -euo pipefail

echo "=========================================="
echo "ADVERSARIAL TEST SUITE"
echo "=========================================="

pytest tests/test_adversarial.py \
    adversarial/replay_tests.py \
    adversarial/rotation_tests.py \
    adversarial/inversion_tests.py \
    adversarial/side_channel_tests.py \
    adversarial/model_extraction.py \
    -v --tb=short \
    --cov=adversarial \
    --cov-report=term-missing \
    --cov-report=html:./exports/adversarial_coverage

echo
echo "Generating adversarial report..."
python -c "
import json
from datetime import datetime
report = {
    'timestamp': datetime.now().isoformat(),
    'suite': 'adversarial',
    'tests': [
        'replay_protection',
        'rotation_invalidation', 
        'template_inversion',
        'side_channel',
        'model_extraction'
    ],
    'status': 'PASS'
}
with open('./exports/adversarial_report.json', 'w') as f:
    json.dump(report, f, indent=2)
print('Report saved to ./exports/adversarial_report.json')
"
