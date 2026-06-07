"""
First-run bootstrap — outputs JSON progress lines to stdout so the
Electron setup screen can render them in real-time.

Protocol: each line is a JSON object:
  {"step": <id>, "status": "running"|"done"|"error"|"skip", "message": <str>, "detail": <str|null>}
  {"step": "progress", "pct": 0-100}
  {"step": "fatal", "message": <str>}        -- unrecoverable, exit(1)
  {"step": "complete", "message": "Setup complete"}
"""
import sys
import os
import json
import subprocess
import shutil
import platform
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
VENV_DIR = ROOT / "app" / "runtime" / "python"
REQUIREMENTS = ROOT / "app" / "backend" / "requirements.txt"


def emit(step: str, status: str, message: str, detail: str = ""):
    print(json.dumps({"step": step, "status": status, "message": message, "detail": detail}), flush=True)


def emit_progress(pct: int):
    print(json.dumps({"step": "progress", "pct": pct}), flush=True)


def run_cmd(cmd: list, label: str, cwd=None, env=None) -> bool:
    """Run a subprocess, emitting its stdout as detail lines."""
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            cwd=str(cwd) if cwd else None, env=env,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                print(json.dumps({"step": "log", "message": line}), flush=True)
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        emit(label, "error", f"Command failed: {e}")
        return False


def get_venv_python() -> Path:
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def get_venv_pip() -> Path:
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"


# ── Step 1: Python version check ──────────────────────────────────────────────
def check_python() -> bool:
    emit("python_check", "running", "Checking Python version...")
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        emit("python_check", "error",
             f"Python 3.10+ required, found {v.major}.{v.minor}",
             "Download Python from https://python.org/downloads")
        print(json.dumps({"step": "fatal", "message": "Python 3.10+ is required."}), flush=True)
        return False
    emit("python_check", "done", f"Python {v.major}.{v.minor}.{v.micro} ✓")
    return True


# ── Step 2: Create venv ───────────────────────────────────────────────────────
def create_venv() -> bool:
    venv_python = get_venv_python()
    if venv_python.exists():
        emit("venv", "skip", "Virtual environment already exists")
        return True

    emit("venv", "running", "Creating isolated Python environment...",
         f"Location: {VENV_DIR}")
    VENV_DIR.mkdir(parents=True, exist_ok=True)
    ok = run_cmd([sys.executable, "-m", "venv", str(VENV_DIR)], "venv")
    if not ok:
        emit("venv", "error", "Failed to create virtual environment")
        return False
    emit("venv", "done", "Virtual environment created ✓")
    return True


# ── Step 3: Detect GPU and install PyTorch ────────────────────────────────────
def detect_gpu() -> dict:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            vram_mb = int(parts[1]) if len(parts) > 1 else 0
            return {"has_gpu": True, "name": parts[0], "vram_mb": vram_mb}
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return {"has_gpu": False, "name": "CPU", "vram_mb": 0}


def install_pytorch(gpu_info: dict) -> bool:
    python = get_venv_python()

    # Check if torch already installed
    result = subprocess.run(
        [str(python), "-c", "import torch; print(torch.__version__)"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        emit("pytorch", "skip", f"PyTorch {result.stdout.strip()} already installed")
        return True

    if gpu_info["has_gpu"]:
        emit("pytorch", "running",
             f"Installing PyTorch with CUDA 12.1 for {gpu_info['name']}...",
             "This may take 5-10 minutes on first run")
        cmd = [
            str(python), "-m", "pip", "install", "--quiet",
            "torch", "torchvision", "torchaudio",
            "--index-url", "https://download.pytorch.org/whl/cu121",
        ]
    else:
        emit("pytorch", "running", "No NVIDIA GPU detected — installing CPU PyTorch...",
             "Video generation will be slow without a GPU")
        cmd = [str(python), "-m", "pip", "install", "--quiet",
               "torch", "torchvision", "torchaudio"]

    ok = run_cmd(cmd, "pytorch")
    if not ok:
        emit("pytorch", "error", "PyTorch installation failed",
             "Check your internet connection and try again")
        return False
    emit("pytorch", "done", "PyTorch installed ✓")
    return True


# ── Step 4: Install backend deps ──────────────────────────────────────────────
def install_deps() -> bool:
    python = get_venv_python()

    # Quick check — if fastapi already present, skip
    result = subprocess.run(
        [str(python), "-c", "import fastapi"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        emit("deps", "skip", "Backend dependencies already installed")
        return True

    emit("deps", "running", "Installing backend dependencies...",
         "fastapi, uvicorn, sqlalchemy, kokoro, soundfile, psutil, requests")

    # Upgrade pip silently first
    run_cmd([str(python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"], "deps")

    ok = run_cmd(
        [str(python), "-m", "pip", "install", "--quiet", "-r", str(REQUIREMENTS)],
        "deps",
    )
    if not ok:
        emit("deps", "error", "Dependency installation failed",
             "Check your internet connection and try again")
        return False
    emit("deps", "done", "Backend dependencies installed ✓")
    return True


# ── Step 5: FFmpeg ────────────────────────────────────────────────────────────
def ensure_ffmpeg() -> bool:
    # Already on PATH?
    if shutil.which("ffmpeg"):
        emit("ffmpeg", "skip", f"FFmpeg found on PATH: {shutil.which('ffmpeg')}")
        return True

    # Bundled?
    bundled = ROOT / "app" / "runtime" / "ffmpeg"
    ffmpeg_bin = bundled / ("ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")
    if ffmpeg_bin.exists():
        emit("ffmpeg", "skip", "Bundled FFmpeg found ✓")
        return True

    emit("ffmpeg", "running", "Downloading FFmpeg binary...", "~70 MB")
    try:
        bundled.mkdir(parents=True, exist_ok=True)
        if platform.system() == "Windows":
            ok = _download_ffmpeg_windows(bundled)
        else:
            ok = _download_ffmpeg_unix(bundled)
        if ok:
            emit("ffmpeg", "done", "FFmpeg installed ✓")
            return True
    except Exception as e:
        emit("ffmpeg", "error", f"FFmpeg download failed: {e}",
             "Install FFmpeg manually from https://ffmpeg.org/download.html")
    return False


def _download_ffmpeg_windows(dest: Path) -> bool:
    import urllib.request
    import zipfile
    import tempfile

    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    emit("ffmpeg", "running", "Downloading FFmpeg for Windows...", url)

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    urllib.request.urlretrieve(url, tmp_path)
    with zipfile.ZipFile(tmp_path) as zf:
        for member in zf.namelist():
            if member.endswith("/bin/ffmpeg.exe") or member.endswith("/bin/ffprobe.exe"):
                filename = Path(member).name
                with zf.open(member) as src, open(dest / filename, "wb") as dst:
                    dst.write(src.read())
    Path(tmp_path).unlink(missing_ok=True)
    return (dest / "ffmpeg.exe").exists()


def _download_ffmpeg_unix(dest: Path) -> bool:
    import urllib.request
    import tarfile
    import tempfile

    system = platform.system()
    if system == "Darwin":
        url = "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
    else:
        url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"

    with tempfile.NamedTemporaryFile(suffix=".tar.xz", delete=False) as tmp:
        tmp_path = tmp.name
    urllib.request.urlretrieve(url, tmp_path)
    with tarfile.open(tmp_path) as tf:
        for member in tf.getmembers():
            if member.name.endswith("/ffmpeg") or member.name == "ffmpeg":
                member.name = "ffmpeg"
                tf.extract(member, dest)
    Path(tmp_path).unlink(missing_ok=True)
    ffmpeg_bin = dest / "ffmpeg"
    if ffmpeg_bin.exists():
        os.chmod(ffmpeg_bin, 0o755)
        return True
    return False


# ── Step 6: Check / install Ollama ───────────────────────────────────────────
def check_ollama() -> bool:
    if shutil.which("ollama"):
        emit("ollama", "skip", f"Ollama found: {shutil.which('ollama')}")
        return True

    emit("ollama", "running", "Ollama not found — downloading installer...",
         "Required for AI script refinement and scene prompts")
    if platform.system() == "Windows":
        _open_browser_install("https://ollama.com/download/windows", "Ollama")
        emit("ollama", "error",
             "Please install Ollama manually and restart setup",
             "https://ollama.com/download/windows")
        return False
    elif platform.system() == "Darwin":
        _open_browser_install("https://ollama.com/download/mac", "Ollama")
        emit("ollama", "error",
             "Please install Ollama manually and restart setup",
             "https://ollama.com/download/mac")
        return False
    else:
        # Linux: curl install
        emit("ollama", "running", "Installing Ollama via curl...")
        ok = run_cmd(
            ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
            "ollama",
        )
        if ok:
            emit("ollama", "done", "Ollama installed ✓")
            return True
        emit("ollama", "error", "Ollama install failed — install manually from ollama.com")
        return False


def _open_browser_install(url: str, name: str):
    try:
        if platform.system() == "Windows":
            os.startfile(url)  # type: ignore
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", url])
        else:
            subprocess.Popen(["xdg-open", url])
    except Exception:
        pass


# ── Step 7: Pull a default LLM if none installed ──────────────────────────────
def ensure_llm(gpu_info: dict) -> bool:
    if not shutil.which("ollama"):
        emit("llm", "skip", "Ollama not available — skipping LLM setup")
        return True

    # Check if any model is already installed
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
    lines = [l for l in result.stdout.strip().splitlines() if l and "NAME" not in l]
    if lines:
        first = lines[0].split()[0]
        emit("llm", "skip", f"LLM already installed: {first}")
        return True

    # Pick model based on VRAM
    vram_gb = gpu_info.get("vram_mb", 0) / 1024
    model = "gemma3:4b" if vram_gb >= 6 else "gemma3:1b"
    emit("llm", "running", f"Pulling {model} via Ollama...",
         "This may take several minutes — model is ~2-3 GB")
    ok = run_cmd(["ollama", "pull", model], "llm")
    if ok:
        emit("llm", "done", f"{model} ready ✓")
        return True
    emit("llm", "error", f"Failed to pull {model}",
         "Run 'ollama pull gemma3:4b' manually after setup")
    return True  # non-fatal


# ── Step 8: ComfyUI ───────────────────────────────────────────────────────────
def ensure_comfyui() -> bool:
    candidates = [
        ROOT / "app" / "runtime" / "comfyui",
        Path.home() / "ComfyUI",
        ROOT / "ComfyUI",
    ]
    for c in candidates:
        if (c / "main.py").exists():
            emit("comfyui", "skip", f"ComfyUI found: {c}")
            return True

    emit("comfyui", "running", "Installing ComfyUI...",
         "Cloning repository (~50 MB) + installing requirements")

    if not shutil.which("git"):
        emit("comfyui", "error", "Git is required to install ComfyUI",
             "Install Git from https://git-scm.com/downloads")
        return False

    dest = ROOT / "app" / "runtime" / "comfyui"
    dest.parent.mkdir(parents=True, exist_ok=True)

    ok = run_cmd(
        ["git", "clone", "--depth=1",
         "https://github.com/comfyanonymous/ComfyUI.git", str(dest)],
        "comfyui",
    )
    if not ok:
        emit("comfyui", "error", "Failed to clone ComfyUI",
             "Check internet connection or clone manually to app/runtime/comfyui/")
        return False

    # Install ComfyUI requirements into our venv
    python = get_venv_python()
    emit("comfyui", "running", "Installing ComfyUI requirements (~10 min on first run)...")
    req_file = dest / "requirements.txt"
    if req_file.exists():
        ok = run_cmd(
            [str(python), "-m", "pip", "install", "--quiet", "-r", str(req_file)],
            "comfyui",
        )

    emit("comfyui", "done", "ComfyUI installed ✓")
    return True


# ── Step 9: Download Wan2.1 model ─────────────────────────────────────────────
def ensure_wan_model(gpu_info: dict) -> bool:
    vram_mb = gpu_info.get("vram_mb", 0)

    # Where ComfyUI expects models
    comfyui_base = None
    for c in [ROOT / "app" / "runtime" / "comfyui", Path.home() / "ComfyUI", ROOT / "ComfyUI"]:
        if (c / "main.py").exists():
            comfyui_base = c
            break

    if comfyui_base is None:
        emit("wan_model", "skip", "ComfyUI not found — skipping model download")
        return True

    models_dir = comfyui_base / "models" / "unet"
    models_dir.mkdir(parents=True, exist_ok=True)

    # Check if any wan model already exists
    existing = list(models_dir.glob("*wan*")) + list(models_dir.glob("*Wan*"))
    if existing:
        emit("wan_model", "skip", f"Wan model already present: {existing[0].name}")
        return True

    # Choose variant based on VRAM
    if vram_mb >= 16000:
        model_id = "Wan-AI/Wan2.1-T2V-14B"
        filename = "wan2.1-t2v-14b.safetensors"
        size_hint = "~28 GB"
    else:
        model_id = "Wan-AI/Wan2.1-T2V-1.3B"
        filename = "wan2.1-t2v-1.3b.safetensors"
        size_hint = "~2.8 GB"

    emit("wan_model", "running",
         f"Downloading {filename} ({size_hint})...",
         f"Model: {model_id}")

    python = get_venv_python()
    script = f"""
from huggingface_hub import hf_hub_download
import shutil, os
path = hf_hub_download(
    repo_id="{model_id}",
    filename="{filename}",
    cache_dir=None,
)
import shutil
shutil.copy(path, r"{models_dir / filename}")
print("DONE:" + r"{models_dir / filename}")
"""
    try:
        result = subprocess.run(
            [str(python), "-c", script],
            capture_output=True, text=True, timeout=3600,
        )
        if "DONE:" in result.stdout:
            emit("wan_model", "done", f"{filename} downloaded ✓")
            return True
        emit("wan_model", "error",
             "Model download failed — you can download it manually",
             f"huggingface.co/{model_id}")
    except subprocess.TimeoutExpired:
        emit("wan_model", "error", "Download timed out",
             "Run setup again or download manually")
    return True  # non-fatal — ComfyUI can still work without it


# ── Step 10: Frontend npm install ─────────────────────────────────────────────
def install_frontend() -> bool:
    frontend_dir = ROOT / "app" / "frontend"
    node_modules = frontend_dir / "node_modules"

    if node_modules.exists() and (node_modules / ".package-lock.json").exists():
        emit("frontend", "skip", "Frontend dependencies already installed")
        return True

    if not shutil.which("node") and not shutil.which("node.exe"):
        emit("frontend", "error", "Node.js 18+ required for the frontend",
             "Download from https://nodejs.org")
        return False

    emit("frontend", "running", "Installing frontend dependencies...",
         "npm install in app/frontend/")
    npm = shutil.which("npm") or "npm"
    ok = run_cmd([npm, "install"], "frontend", cwd=frontend_dir)
    if ok:
        emit("frontend", "done", "Frontend dependencies installed ✓")
        return True
    emit("frontend", "error", "npm install failed")
    return False


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    emit("start", "running", "AI Video Studio — First Run Setup", "Initializing...")
    emit_progress(0)

    gpu_info = detect_gpu()
    if gpu_info["has_gpu"]:
        emit("gpu_detect", "done",
             f"GPU detected: {gpu_info['name']} ({gpu_info['vram_mb']//1024} GB VRAM)")
    else:
        emit("gpu_detect", "done", "No NVIDIA GPU detected — CPU mode")

    steps = [
        (check_python,                    5),
        (create_venv,                    15),
        (lambda: install_pytorch(gpu_info), 40),
        (install_deps,                   55),
        (ensure_ffmpeg,                  65),
        (check_ollama,                   72),
        (lambda: ensure_llm(gpu_info),   80),
        (ensure_comfyui,                 88),
        (lambda: ensure_wan_model(gpu_info), 97),
        (install_frontend,              100),
    ]

    for fn, pct in steps:
        ok = fn()
        emit_progress(pct)
        if not ok and pct <= 55:  # early critical steps
            print(json.dumps({"step": "fatal", "message": "Setup failed at a critical step. See errors above."}), flush=True)
            sys.exit(1)

    print(json.dumps({"step": "complete", "message": "Setup complete — launching AI Video Studio"}), flush=True)


if __name__ == "__main__":
    main()
