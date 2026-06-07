"""Manages the Ollama subprocess lifecycle."""
import subprocess
import time
import requests
import shutil
from pathlib import Path

OLLAMA_URL = "http://localhost:11434"
_process: subprocess.Popen | None = None


def is_running() -> bool:
    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).status_code == 200
    except Exception:
        return False


def start() -> bool:
    global _process
    if is_running():
        return True

    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        return False

    _process = subprocess.Popen(
        [ollama_bin, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        time.sleep(1)
        if is_running():
            return True
    return False


def stop():
    global _process
    if _process and _process.poll() is None:
        _process.terminate()
        try:
            _process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _process.kill()
    _process = None


def list_models() -> list[dict]:
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        return resp.json().get("models", [])
    except Exception:
        return []


def status() -> dict:
    running = is_running()
    return {
        "running": running,
        "url": OLLAMA_URL,
        "managed": _process is not None,
        "models": list_models() if running else [],
    }
