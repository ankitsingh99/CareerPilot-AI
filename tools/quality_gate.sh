#!/usr/bin/env bash
# CareerPilot AI Automated Quality Verification Gate
# Inspired by vibe-coding-playbook & context engineering standards.
# Exits with 0 if all quality, security, and test criteria pass; exits 1 on failure.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "============================================================"
echo "🛡️  CAREERPILOT AI - AUTOMATED QUALITY VERIFICATION GATE"
echo "============================================================"

# Resolve Python runtime
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
    PYTEST=".venv/bin/pytest"
else
    PYTHON="python3"
    PYTEST="pytest"
fi

echo -e "\n[1/5] 🔒 Running PII & Leaked Secret Audit..."
$PYTHON tools/generate_workspace_from_master.py --audit-pii

echo -e "\n[2/5] 🌐 Verifying SSRF Defense Protocol..."
$PYTEST tests/test_ssrf_guard.py -q

echo -e "\n[3/5] 📝 Verifying Cover Letter Integrity Linter..."
$PYTHON -c "
from parsers.linter import audit_structural_integrity
test_text = 'Reduced anomalies by 40% using 15+ Airflow pipelines. Req ID: 12345. https://linkedin.com/in/ankit-singh99'
errs = audit_structural_integrity(test_text)
assert len(errs) == 0, f'Linter error: {errs}'
print('[Linter] PASS: Structural integrity audit operational.')
"

echo -e "\n[4/5] ⚡ Checking Python 3.15 Lazy Import Compatibility..."
$PYTHON -c "
import sys
import utils.lazy_bootstrap
print(f'[Runtime] CPython {sys.version.split()[0]} running cleanly.')
"

echo -e "\n[5/5] 🧪 Executing Comprehensive Test Suite..."
$PYTEST -q

echo -e "\n============================================================"
echo "✅ ALL QUALITY & SECURITY GATES PASSED (100% OPERATIONAL)"
echo "============================================================"
exit 0
