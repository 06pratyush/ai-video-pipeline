#!/usr/bin/env python3
"""
Reader-model bridge. Usage:
    ask.py <file-or-"-"> "<question>" [max-lines]

Talks to Ollama over HTTP rather than `ollama run`, because the CLI scans the
prompt text for quoted file paths and tries to attach them as multimodal
inputs -- which makes any prompt containing source code fail outright.
"""
import json
import os
import sys
import urllib.request

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
READER = os.environ.get("ORCH_READER", "orch-reader")

PREAMBLE = (
    "You are a code-reading assistant. Answer ONLY from the content below.\n"
    "If the answer is not present, reply exactly: NOT_FOUND.\n"
    "Do not summarize anything not asked. Do not add preamble or opinions.\n"
    "Quote exact identifiers, signatures and line numbers where relevant.\n"
)


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: ask.py <file|-> <question> [max-lines]", file=sys.stderr)
        return 2
    src, question = sys.argv[1], sys.argv[2]
    max_lines = int(sys.argv[3]) if len(sys.argv) > 3 else 25

    if src == "-":
        body = sys.stdin.read()
    else:
        with open(src, encoding="utf-8", errors="replace") as fh:
            body = fh.read()

    # Number the lines so the model can cite them accurately.
    numbered = "\n".join(f"{i}: {ln}" for i, ln in enumerate(body.splitlines(), 1))

    prompt = (
        f"{PREAMBLE}Hard limit: {max_lines} lines of output.\n\n"
        f"QUESTION: {question}\n\n"
        f"--- CONTENT START ---\n{numbered}\n--- CONTENT END ---\n"
    )

    payload = json.dumps({
        "model": READER,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "8h",
        "options": {"temperature": 0.1, "num_ctx": 65536},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{HOST}/api/generate", data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller, not swallowed
        print(f"READER_ERROR: {exc}", file=sys.stderr)
        return 1

    text = (data.get("response") or "").strip()
    if not text:
        print("READER_EMPTY", file=sys.stderr)
        return 1
    for line in text.splitlines()[:max_lines]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
