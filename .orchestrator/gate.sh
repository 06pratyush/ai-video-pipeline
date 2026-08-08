#!/usr/bin/env bash
# Usage: ./.orchestrator/gate.sh <path>   -> exits non-zero on any failure
set -uo pipefail
TARGET="${1:?path required}"
PY="${ORCH_PY:-venv/Scripts/python.exe}"
FAIL=0
case "$TARGET" in
  *.py)
    "$PY" -m py_compile "$TARGET"      || FAIL=1
    "$PY" -m ruff check "$TARGET"      2>/dev/null || true
    ;;
  *.ts|*.tsx|*.js|*.jsx)
    (cd app/frontend && npx tsc --noEmit) || FAIL=1
    ;;
esac
exit $FAIL
