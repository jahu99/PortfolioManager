#!/bin/bash
set -euo pipefail

cd /Users/jameshulin/Documents/stock-momentum-agent

echo "============================================================"
echo "STOCK MOMENTUM AGENT — VULTURE REDUNDANCY AUDIT"
echo "============================================================"
echo
echo "Git baseline:"
git status --short
git log -1 --oneline
echo

if ! python -m vulture --version >/dev/null 2>&1; then
    echo "Vulture is not installed."
    echo "Install with: pip install vulture"
    exit 1
fi

mkdir -p reports

echo "Running Vulture..."
python -m vulture     .     --exclude-dir=.venv     --exclude-dir=.git     --exclude-dir=__pycache__     --exclude="*_backup.py"     --exclude="main_backup_before_epic15.py"     > reports/vulture_audit.txt || true

echo
echo "Vulture output:"
echo "------------------------------------------------------------"
cat reports/vulture_audit.txt
echo "------------------------------------------------------------"

echo
echo "No files have been removed or modified by this audit."
echo
echo "Now inspect the findings alongside the architecture document."
