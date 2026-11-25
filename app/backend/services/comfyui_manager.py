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
            # Absolute: start() runs main.py with cwd set to this folder, so a
            # relative path would resolve to app/runtime/comfyui/app/runtime/comfyui.
            return str(c.resolve())
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

    # ComfyUI gets its own venv (CUDA PyTorch + ComfyUI-GGUF) so the backend's
    # environment can stay small; fall back to our interpreter if it is missing.
    python = sys.executable
    for venv_py in (Path(path) / "venv" / "Scripts" / "python.exe",
                    Path(path) / "venv" / "bin" / "python"):
        if venv_py.exists():
            python = str(venv_py)
            break

    log = open(Path(path) / "comfyui.log", "ab")
    _process = subprocess.Popen(
        [python, str(main_py), "--listen", "127.0.0.1", "--port", "8188"],
        cwd=path,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    for _ in range(90):
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
