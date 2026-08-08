#!/usr/bin/env bash
# Usage: ./.orchestrator/ask.sh <file-or-"-"> "<question>" [max-lines]
# Thin wrapper over ask.py, which speaks the Ollama HTTP API. The `ollama run`
# CLI cannot be used here: it scans prompt text for quoted file paths and tries
# to attach them as multimodal inputs, so any prompt containing source code
# fails with "Couldn't process file".
set -eu
PY="${ORCH_PY:-venv/Scripts/python.exe}"
exec "$PY" .orchestrator/ask.py "$@"
