#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "============================================================"
echo "  AI Video Studio"
echo "============================================================"
echo ""

# ── Check Python ───────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3.10+ is required but not found."
    echo "        Install via your package manager or https://python.org/downloads"
    exit 1
fi

# ── Check Node.js ──────────────────────────────────────────────────────────────
HAS_NODE=0
if command -v node &>/dev/null; then
    NODE_MAJOR=$(node --version | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then HAS_NODE=1; fi
fi
if [ $HAS_NODE -eq 0 ]; then
    echo "[WARNING] Node.js 18+ not found. The Electron GUI requires it."
    echo "          Download from: https://nodejs.org"
fi

# ── Setup check ────────────────────────────────────────────────────────────────
VENV_PYTHON="$ROOT/app/runtime/python/bin/python"
SETUP_NEEDED=0
[ ! -f "$VENV_PYTHON" ] && SETUP_NEEDED=1

if [ $SETUP_NEEDED -eq 1 ] && [ $HAS_NODE -eq 0 ]; then
    echo "[SETUP] Running headless bootstrap (no Node.js for GUI)..."
    echo "        This may take 10-20 minutes on first run."
    echo ""
    python3 "$ROOT/installer/bootstrap.py"
fi

# ── Start backend daemon ───────────────────────────────────────────────────────
if [ -f "$VENV_PYTHON" ]; then
    echo "[DAEMON] Starting backend on http://localhost:7860 ..."
    "$VENV_PYTHON" -m uvicorn app.backend.main:app \
        --host 127.0.0.1 --port 7860 &>/dev/null &
    DAEMON_PID=$!
    echo "[DAEMON] Backend PID: $DAEMON_PID"
    sleep 2
fi

# ── Launch frontend ────────────────────────────────────────────────────────────
FRONTEND="$ROOT/app/frontend"

# Production release
if [ -f "$FRONTEND/release/linux-unpacked/ai-video-studio" ]; then
    "$FRONTEND/release/linux-unpacked/ai-video-studio" &
    echo "[OK] Electron app launched."
    exit 0
fi

if [ -f "$FRONTEND/release/mac/AI Video Studio.app/Contents/MacOS/AI Video Studio" ]; then
    open "$FRONTEND/release/mac/AI Video Studio.app" &
    echo "[OK] macOS app launched."
    exit 0
fi

# Dev: Electron
if [ -d "$FRONTEND/node_modules/.bin" ] && command -v electron &>/dev/null; then
    cd "$FRONTEND"
    NODE_ENV=development electron . &
    cd "$ROOT"
    echo "[OK] Electron dev mode launched."
    exit 0
fi

# Dev: Vite browser fallback
if [ -d "$FRONTEND/node_modules" ]; then
    cd "$FRONTEND"
    npx vite &>/dev/null &
    cd "$ROOT"
    sleep 3
    if command -v xdg-open &>/dev/null; then
        xdg-open http://localhost:5173
    elif command -v open &>/dev/null; then
        open http://localhost:5173
    fi
    echo "[OK] Browser dev server at http://localhost:5173"
    exit 0
fi

# Nothing built — install then launch
echo "[SETUP] Installing frontend dependencies..."
cd "$FRONTEND"
npm install
npx vite &>/dev/null &
cd "$ROOT"
sleep 3
xdg-open http://localhost:5173 2>/dev/null || open http://localhost:5173 2>/dev/null || true
echo "[OK] Browser dev server at http://localhost:5173"
