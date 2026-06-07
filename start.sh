#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  AI Video Studio — Starting..."
echo "============================================================"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3.10+ is required but not found."
    echo "        Install via your package manager or https://python.org/downloads"
    exit 1
fi

# Run system check
python3 installer/system_check.py >/dev/null 2>&1 || echo "[WARNING] System check issues detected."

VENV_PYTHON="app/runtime/python/bin/python"

# Bootstrap on first run
if [ ! -f "$VENV_PYTHON" ]; then
    echo "[SETUP] First run — installing dependencies (5-15 min)..."
    python3 installer/bootstrap.py
fi

# Start backend daemon in background
echo "[DAEMON] Starting backend on http://localhost:7860 ..."
"$VENV_PYTHON" -m uvicorn app.backend.main:app --host 127.0.0.1 --port 7860 &
DAEMON_PID=$!

# Wait for backend to be ready
echo "[DAEMON] Waiting for backend..."
for i in $(seq 1 30); do
    sleep 2
    if curl -s http://localhost:7860/system/health >/dev/null 2>&1; then
        echo "[DAEMON] Backend ready."
        break
    fi
done

# Launch frontend
if [ -d "app/frontend/node_modules" ]; then
    cd app/frontend
    npx electron .
    cd ../..
elif [ -f "app/frontend/package.json" ]; then
    cd app/frontend
    npm install
    npm run dev
    cd ../..
else
    echo "[INFO] No frontend found. Backend running at http://localhost:7860"
    echo "       API docs: http://localhost:7860/docs"
    wait $DAEMON_PID
fi
