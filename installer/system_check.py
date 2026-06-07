"""
System pre-flight checks run by start.bat / start.sh before anything else.
Prints a JSON report to stdout so the launcher can parse it.
"""
import sys
import shutil
import subprocess
import json
import platform
import os


def check_python() -> dict:
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 10
    return {"ok": ok, "version": f"{v.major}.{v.minor}.{v.micro}", "required": "3.10+"}


def check_node() -> dict:
    node = shutil.which("node")
    if not node:
        return {"ok": False, "version": None, "required": "18+"}
    try:
        out = subprocess.check_output(["node", "--version"], text=True).strip()
        major = int(out.lstrip("v").split(".")[0])
        return {"ok": major >= 18, "version": out, "required": "18+"}
    except Exception:
        return {"ok": False, "version": None, "required": "18+"}


def check_ffmpeg() -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        local = os.path.join("app", "runtime", "ffmpeg", "ffmpeg.exe")
        if platform.system() != "Windows":
            local = os.path.join("app", "runtime", "ffmpeg", "ffmpeg")
        if os.path.exists(local):
            return {"ok": True, "path": local, "bundled": True}
        return {"ok": False, "path": None}
    return {"ok": True, "path": ffmpeg, "bundled": False}


def check_git() -> dict:
    git = shutil.which("git")
    return {"ok": bool(git), "path": git}


def check_ollama() -> dict:
    ollama = shutil.which("ollama")
    return {"ok": bool(ollama), "path": ollama}


def check_nvidia() -> dict:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            return {"ok": True, "gpu": parts[0], "vram_mb": int(parts[1]) if len(parts) > 1 else 0}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return {"ok": False, "gpu": None, "vram_mb": 0}


def check_comfyui() -> dict:
    candidates = [
        os.path.join("app", "runtime", "comfyui", "main.py"),
        os.path.join(os.path.expanduser("~"), "ComfyUI", "main.py"),
        os.path.join("ComfyUI", "main.py"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return {"ok": True, "path": os.path.dirname(c)}
    return {"ok": False, "path": None}


if __name__ == "__main__":
    report = {
        "python": check_python(),
        "node": check_node(),
        "ffmpeg": check_ffmpeg(),
        "git": check_git(),
        "ollama": check_ollama(),
        "nvidia": check_nvidia(),
        "comfyui": check_comfyui(),
        "platform": platform.system(),
    }
    print(json.dumps(report, indent=2))
    all_critical = report["python"]["ok"]
    sys.exit(0 if all_critical else 1)
