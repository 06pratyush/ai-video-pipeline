"""Wan2.2 video generation via ComfyUI (text-to-video and image-to-video).

The workflow JSON is in ComfyUI's API format with readable node ids (``positive``,
``negative``, ``latent``, ``sampler``, ``save``). Values are set on those nodes by id, so
the negative prompt is never overwritten with the scene prompt.

v2: pass ``start_image`` to animate from a keyframe. The client uploads the image and
wires a ``LoadImage`` node into ``Wan22ImageToVideoLatent.start_image``, so one workflow
file serves both modes and the character drawn in the keyframe carries into the clip.

Default workflow: ``app/workflows/wan22_ti2v_5b_gguf.json`` (Wan2.2 TI2V 5B, GGUF,
fits an 8 GB laptop GPU).
"""
import time
from pathlib import Path

from app.backend.pipeline.comfy_client import (
    COMFYUI_URL, VIDEO_EXT, ComfyClient, load_workflow, require_nodes, set_inputs,
)

DEFAULT_WORKFLOW = "app/workflows/wan22_ti2v_5b_gguf.json"

# Wan2.2 TI2V-5B: width/height must be multiples of 32, length = 4k + 1 frames, 24 fps.
FPS = 24


def frames_for_seconds(seconds: float) -> int:
    """Nearest valid Wan frame count (4k + 1) for a clip length in seconds."""
    k = max(1, round(seconds * FPS / 4))
    return 4 * k + 1


def build_workflow(template: dict, prompt: str, width: int, height: int, num_frames: int,
                   steps: int, seed: int, negative_prompt: str | None = None,
                   start_image: str | None = None) -> dict:
    """Pure function: the API workflow for one clip (``start_image`` is a ComfyUI input name)."""
    values = {
        "positive": {"text": prompt},
        "latent": {"width": int(width) // 32 * 32, "height": int(height) // 32 * 32,
                   "length": int(num_frames)},
        "sampler": {"seed": int(seed), "steps": int(steps)},
    }
    if negative_prompt and "negative" in template:
        values["negative"] = {"text": negative_prompt}
    wf = set_inputs(template, values)
    if start_image:
        wf["start"] = {"class_type": "LoadImage", "inputs": {"image": start_image},
                       "_meta": {"title": "Keyframe"}}
        wf["latent"]["inputs"]["start_image"] = ["start", 0]
    return wf


class WanVideoClient:
    def __init__(self, workflow_path: str = DEFAULT_WORKFLOW, comfyui_url: str = COMFYUI_URL):
        self.comfy = ComfyClient(comfyui_url)
        self.workflow_template = load_workflow(workflow_path)
        require_nodes(self.workflow_template, "positive", "latent", "sampler", "save",
                      name=workflow_path)

    def generate(
        self,
        prompt: str,
        output_dir: str,
        width: int = 480,
        height: int = 832,
        num_frames: int = 73,
        steps: int = 20,
        seed: int | None = None,
        negative_prompt: str | None = None,
        start_image: str | None = None,
        timeout_s: float = 3600,
        progress_callback=None,
    ) -> str:
        """Render one clip and wait for it. Returns the saved MP4 path.

        ``start_image`` is a local image path; the clip starts from that frame.
        """
        seed = int(seed) if seed is not None else int(time.time() * 1000) % (2**32)
        start_name = self.comfy.upload(start_image) if start_image else None
        wf = build_workflow(self.workflow_template, prompt, width, height, num_frames, steps,
                            seed, negative_prompt, start_name)
        dest = Path(output_dir) / f"wan_{seed}_{int(time.time())}.mp4"
        return str(self.comfy.run(wf, dest, VIDEO_EXT, timeout_s, progress_callback))

    def health_check(self) -> bool:
        return self.comfy.is_up()
