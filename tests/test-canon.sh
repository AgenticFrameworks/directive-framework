#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$R/tools/gate-runner.py" --validate-templates "$R/gates"
python3 -m py_compile "$R"/tools/*.py
bash "$R/tools/check-canon-purity.sh"
