"""Smooth motion on the GPU: RIFE frame interpolation + Real-ESRGAN upscale, in ComfyUI.

Wan2.2 renders at 24 fps and 480p. RIFE doubles that to 48 fps (new in-between frames,
not repeated ones), and Real-ESRGAN x2 sharpens to 960x1664 before the edit scales to
1080x1920. Both run on CUDA inside ComfyUI. If ComfyUI is not reachable the old CPU path
(FFmpeg minterpolate + lanczos, ``rife_client`` / ``esrgan_client``) is used instead.
"""
from __future__ import annotations

from pathlib import Path

from app.backend.pipeline.comfy_client import (
    COMFYUI_URL, VIDEO_EXT, ComfyClient, load_workflow, require_nodes, set_inputs,
)

WORKFLOW = "rife_upscale.json"


def build_workflow(template: dict, video_name: str, multiplier: int = 2, fps: float = 48.0,
                   upscale: bool = True) -> dict:
    wf = set_inputs(template, {
        "load": {"file": video_name},
        "rife": {"multiplier": int(multiplier)},
        "video": {"fps": float(fps)},
    })
    if not upscale:
        wf["video"]["inputs"]["images"] = ["rife", 0]
        del wf["upscale"], wf["upmodel"]
    return wf


class SmoothClient:
    def __init__(self, comfyui_url: str = COMFYUI_URL):
        self.comfy = ComfyClient(comfyui_url)
        self.template = load_workflow(WORKFLOW)
        require_nodes(self.template, "load", "rife", "upscale", "video", "save", name=WORKFLOW)

    def smooth(self, src: str | Path, dest: str | Path, src_fps: float = 24.0,
               multiplier: int = 2, upscale: bool = True, timeout_s: float = 1800) -> Path:
        name = self.comfy.upload(src)
        wf = build_workflow(self.template, name, multiplier, src_fps * multiplier, upscale)
        return self.comfy.run(wf, dest, VIDEO_EXT, timeout_s)


def smooth_or_fallback(src: str, dest: str, src_fps: float = 24.0, upscale: bool = True) -> str:
    """GPU path if ComfyUI is up, otherwise the CPU FFmpeg path. Returns the output path."""
    client = SmoothClient()
    if client.comfy.is_up():
        return str(client.smooth(src, dest, src_fps, upscale=upscale))
    from app.backend.pipeline.rife_client import interpolate_to_fps
    return interpolate_to_fps(src, dest, int(src_fps * 2))
