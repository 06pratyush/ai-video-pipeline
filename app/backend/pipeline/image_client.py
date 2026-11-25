"""Keyframe images for character consistency (FLUX via ComfyUI, on the GPU).

Two modes, chosen per story with ``consistency``:

* ``schnell`` - FLUX.1 schnell, text only, 4 steps, Apache-2.0 (commercial use is fine).
  Consistency comes from repeating the same character description and seed.
* ``kontext`` - FLUX.1 Kontext dev edits a character reference image into each scene,
  so the face, beard and clothes carry over best. Its licence is NON-COMMERCIAL.

The usual flow: draw each character once with schnell (the "character sheet"), then
draw one keyframe per scene with Kontext (or schnell), then let Wan2.2 animate from it.
"""
from __future__ import annotations

from pathlib import Path

from app.backend.pipeline.comfy_client import (
    COMFYUI_URL, IMAGE_EXT, ComfyClient, load_workflow, require_nodes, set_inputs,
)

WORKFLOWS = {"schnell": "flux_schnell_gguf.json", "kontext": "flux_kontext_gguf.json"}
DEFAULT_STEPS = {"schnell": 4, "kontext": 20}
LICENCE = {"schnell": "apache-2.0", "kontext": "flux-1-dev-non-commercial"}


def snap16(v: int) -> int:
    return max(256, int(v) // 16 * 16)


def keyframe_size(video_w: int, video_h: int, megapixels: float = 1.0) -> tuple[int, int]:
    """Same aspect ratio as the video, about 1 MP (what FLUX is trained for), multiple of 16."""
    scale = (megapixels * 1_000_000 / (video_w * video_h)) ** 0.5
    return snap16(video_w * scale), snap16(video_h * scale)


def build_workflow(template: dict, mode: str, prompt: str, width: int, height: int,
                   seed: int, steps: int | None = None, reference: str | None = None) -> dict:
    values = {
        "positive": {"text": prompt},
        "latent": {"width": snap16(width), "height": snap16(height)},
        "sampler": {"seed": int(seed), "steps": int(steps or DEFAULT_STEPS[mode])},
    }
    if mode == "kontext":
        if not reference:
            raise ValueError("kontext mode needs a reference image")
        values["ref"] = {"image": reference}
    return set_inputs(template, values)


class ImageClient:
    def __init__(self, mode: str = "schnell", comfyui_url: str = COMFYUI_URL):
        if mode not in WORKFLOWS:
            raise ValueError(f"unknown image mode {mode!r}; use one of {sorted(WORKFLOWS)}")
        self.mode = mode
        self.comfy = ComfyClient(comfyui_url)
        self.template = load_workflow(WORKFLOWS[mode])
        require_nodes(self.template, "positive", "latent", "sampler", "save", name=WORKFLOWS[mode])
        if mode == "kontext":
            require_nodes(self.template, "ref", name=WORKFLOWS[mode])

    def generate(self, prompt: str, dest: str | Path, width: int = 768, height: int = 1344,
                 seed: int = 0, steps: int | None = None, reference: str | Path | None = None,
                 timeout_s: float = 1800) -> Path:
        ref_name = self.comfy.upload(reference) if reference else None
        wf = build_workflow(self.template, self.mode, prompt, width, height, seed, steps, ref_name)
        return self.comfy.run(wf, dest, IMAGE_EXT, timeout_s)
