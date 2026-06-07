"""
First-run dependency installer.
Called by start.bat / start.sh on initial setup.
Installs Python backend deps into app/runtime/python/.
"""
import sys
import os
import subprocess
import json
from pathlib import Path

VENV_DIR = Path("app/runtime/python")
REQUIREMENTS = Path("app/backend/requirements.txt")


def log(msg: str):
    print(f"[BOOTSTRAP] {msg}", flush=True)


def create_venv():
    if (VENV_DIR / "Scripts" / "python.exe").exists() or (VENV_DIR / "bin" / "python").exists():
        log("Virtual environment already exists")
        return
    log(f"Creating virtual environment at {VENV_DIR}...")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    log("Virtual environment created")


def get_venv_python() -> str:
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "bin" / "python")


def install_deps():
    python = get_venv_python()
    log("Installing backend dependencies...")
    subprocess.check_call([python, "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([python, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    log("Backend dependencies installed")


def install_pytorch():
    """Install PyTorch with CUDA if NVIDIA GPU is present."""
    python = get_venv_python()
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            log("NVIDIA GPU detected — installing PyTorch with CUDA 12.1...")
            subprocess.check_call([
                python, "-m", "pip", "install",
                "torch", "torchvision", "torchaudio",
                "--index-url", "https://download.pytorch.org/whl/cu121",
            ])
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    log("No NVIDIA GPU detected — installing CPU-only PyTorch...")
    subprocess.check_call([python, "-m", "pip", "install", "torch", "torchvision", "torchaudio"])


def main():
    log("AI Video Studio — First Run Bootstrap")
    log(f"Python: {sys.version}")

    VENV_DIR.mkdir(parents=True, exist_ok=True)
    create_venv()
    install_pytorch()
    install_deps()

    log("Bootstrap complete. Run start.bat to launch the app.")


if __name__ == "__main__":
    main()
