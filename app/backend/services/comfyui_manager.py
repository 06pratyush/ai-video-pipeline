"""Manages the ComfyUI subprocess lifecycle (lazy — starts on first generation request)."""
import subprocess
import time
import sys
import requests
import shutil
from pathlib import Path

COMFYUI_URL = "http://localhost:8188"
_process: subprocess.Popen | None = None
_comfyui_path: str | None = None


def find_comfyui() -> str | None:
    """Locate ComfyUI installation."""
    candidates = [
        Path("app/runtime/comfyui"),
        Path.home() / "ComfyUI",
        Path("ComfyUI"),
    ]
    for c in candidates:
        if (c / "main.py").exists():
            return str(c)
    return None


def is_running() -> bool:
    try:
        return requests.get(f"{COMFYUI_URL}/system_stats", timeout=3).status_code == 200
    except Exception:
        return False


def start(comfyui_path: str | None = None) -> bool:
    global _process, _comfyui_path
    if is_running():
        return True

    path = comfyui_path or find_comfyui()
    if not path:
        return False

    _comfyui_path = path
    main_py = Path(path) / "main.py"
    if not main_py.exists():
        return False

    # Use the same Python interpreter that's running us
    _process = subprocess.Popen(
        [sys.executable, str(main_py), "--listen", "127.0.0.1", "--port", "8188"],
        cwd=path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        time.sleep(2)
        if is_running():
            return True
    return False


def stop():
    global _process
    if _process and _process.poll() is None:
        _process.terminate()
        try:
            _process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _process.kill()
    _process = None


def status() -> dict:
    running = is_running()
    return {
        "running": running,
        "url": COMFYUI_URL,
        "managed": _process is not None,
        "path": _comfyui_path,
    }
