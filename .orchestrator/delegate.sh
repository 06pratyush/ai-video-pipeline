#!/usr/bin/env bash
# Usage: ./.orchestrator/delegate.sh <model> <prompt-file> <output-file>
set -euo pipefail
MODEL="${1:?model required}"
PROMPT_FILE="${2:?prompt file required}"
OUT_FILE="${3:?output file required}"
START=$(date +%s)
ollama run "$MODEL" < "$PROMPT_FILE" > "$OUT_FILE" 2>".orchestrator/logs/last_error.log"
END=$(date +%s)
echo "MODEL=$MODEL DURATION=$((END-START))s BYTES=$(wc -c < "$OUT_FILE")"
