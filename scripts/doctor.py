"""AI Video Studio v2 health check: is every stage ready, and will it run on the GPU?

    venv311\\Scripts\\python.exe scripts\\doctor.py

Exit code 0 only when every required check passes. Checks:
  * backend venv: PyTorch sees CUDA (Kokoro), CTranslate2 sees CUDA (faster-whisper)
  * ComfyUI venv: PyTorch sees CUDA; custom nodes present
  * every model file in installer/catalog.json for the v2 stack, at its exact size
  * ComfyUI answers on 127.0.0.1 only, and knows every node the v2 workflows use
  * FFmpeg can encode with NVENC (GPU)
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
COMFY = ROOT / "app" / "runtime" / "comfyui"
V2_MODELS = ["wan2.2-ti2v-5b", "flux-schnell", "flux-kontext", "ace-step-3.5b", "rife-esrgan"]
NODES = ["ComfyUI-GGUF", "ComfyUI-Frame-Interpolation"]

results: list[tuple[str, bool, str, bool]] = []


def check(name: str, ok: bool, detail: str = "", required: bool = True):
    results.append((name, ok, detail, required))


def comfy_python() -> Path:
    for p in (COMFY / "venv" / "Scripts" / "python.exe", COMFY / "venv" / "bin" / "python"):
        if p.exists():
            return p
    return Path(sys.executable)


def main() -> int:
    # Backend GPU.
    try:
        import torch
        check("backend torch CUDA (Kokoro)", torch.cuda.is_available(),
              f"torch {torch.__version__}" + (f", {torch.cuda.get_device_name(0)}"
                                              if torch.cuda.is_available() else ""))
    except ImportError:
        check("backend torch CUDA (Kokoro)", False, "torch not installed")
    try:
        from app.backend.pipeline import whisper_client
        whisper_client._add_cuda_dll_dirs()
        dev = whisper_client._device()
        check("faster-whisper on CUDA", dev[0] == "cuda", f"{dev[0]} / {dev[1]}")
    except Exception as e:  # noqa: BLE001
        check("faster-whisper on CUDA", False, str(e)[:120])

    # ComfyUI venv GPU.
    r = subprocess.run([str(comfy_python()), "-c",
                        "import torch;print(torch.__version__, torch.cuda.is_available())"],
                       capture_output=True, text=True)
    check("ComfyUI torch CUDA", r.returncode == 0 and r.stdout.strip().endswith("True"),
          r.stdout.strip() or r.stderr.strip()[-120:])
    for node in NODES:
        check(f"custom node {node}", (COMFY / "custom_nodes" / node).is_dir())

    # Models at exact size.
    catalog = json.loads((ROOT / "installer" / "catalog.json").read_text(encoding="utf-8"))
    for m in catalog["models"]:
        if m["id"] not in V2_MODELS:
            continue
        for f in m.get("files", []):
            p = ROOT / f["install_path"] / Path(f["file"]).name
            size = p.stat().st_size if p.exists() else 0
            ok = p.exists() and (not f.get("bytes") or size == f["bytes"])
            check(f"model {Path(f['file']).name}", ok,
                  f"{size / 1e9:.2f} GB" + ("" if ok else f" (want {f.get('bytes', 0) / 1e9:.2f} GB)"),
                  required=m["id"] != "flux-kontext")

    # ComfyUI running, local only, knows our nodes.
    from app.backend.pipeline.comfy_client import ComfyClient, WORKFLOW_DIR
    c = ComfyClient()
    up = c.is_up()
    check("ComfyUI answering on 127.0.0.1:8188", up, "" if up else "not running (starts on demand)",
          required=False)
    if up:
        import requests
        info = requests.get(f"{c.url}/object_info", timeout=60).json()
        for wf_file in sorted(WORKFLOW_DIR.glob("*.json")):
            wf = json.loads(wf_file.read_text(encoding="utf-8"))
            missing = sorted({n["class_type"] for n in wf.values()} - set(info))
            check(f"workflow {wf_file.name}", not missing, "missing " + ", ".join(missing) if missing else "")
        try:
            import socket
            s = socket.create_connection((socket.gethostbyname(socket.gethostname()), 8188), timeout=2)
            s.close()
            check("ComfyUI not reachable from the network", False, "answers on the LAN address")
        except OSError:
            check("ComfyUI not reachable from the network", True, "bound to 127.0.0.1 only")

    # FFmpeg NVENC.
    t = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=256x256:d=0.1",
                        "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True)
    check("FFmpeg NVENC (GPU encode)", t.returncode == 0, "" if t.returncode == 0 else
          "falls back to libx264 (CPU)", required=False)

    width = max(len(n) for n, *_ in results)
    failed = 0
    for name, ok, detail, required in results:
        mark = "PASS" if ok else ("FAIL" if required else "warn")
        failed += (not ok) and required
        print(f"  {mark}  {name.ljust(width)}  {detail}")
    print(f"\n{'all required checks passed' if not failed else f'{failed} required check(s) failed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
