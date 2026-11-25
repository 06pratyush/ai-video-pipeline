"""Wan video generation via ComfyUI.

The workflow JSON is in ComfyUI's API format with readable node ids
(``positive``, ``negative``, ``latent``, ``sampler``, ``save``). Values are set on
those nodes by id, so the negative prompt is never overwritten with the scene
prompt, and the client fails loudly instead of polling forever.

Default workflow: ``app/workflows/wan22_ti2v_5b_gguf.json`` (Wan2.2 TI2V 5B, GGUF,
fits an 8 GB laptop GPU).
"""
import json
import time
import uuid
from pathlib import Path

import requests

COMFYUI_URL = "http://localhost:8188"
DEFAULT_WORKFLOW = "app/workflows/wan22_ti2v_5b_gguf.json"

# Wan2.2 TI2V-5B: width/height must be multiples of 32, length = 4k + 1 frames, 24 fps.
FPS = 24


def frames_for_seconds(seconds: float) -> int:
    """Nearest valid Wan frame count (4k + 1) for a clip length in seconds."""
    k = max(1, round(seconds * FPS / 4))
    return 4 * k + 1


class WanVideoClient:
    def __init__(self, workflow_path: str = DEFAULT_WORKFLOW, comfyui_url: str = COMFYUI_URL):
        self.comfyui_url = comfyui_url
        wf_file = Path(workflow_path)
        if not wf_file.exists():
            raise FileNotFoundError(f"Workflow JSON not found: {workflow_path}")
        self.workflow_template = json.loads(wf_file.read_text(encoding="utf-8"))
        for node_id in ("positive", "latent", "sampler", "save"):
            if node_id not in self.workflow_template:
                raise ValueError(f"Workflow {workflow_path} has no '{node_id}' node")

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
        timeout_s: float = 3600,
        progress_callback=None,
    ) -> str:
        """Submit one clip to ComfyUI and wait for it. Returns the saved MP4 path."""
        wf = json.loads(json.dumps(self.workflow_template))
        wf["positive"]["inputs"]["text"] = prompt
        if negative_prompt and "negative" in wf:
            wf["negative"]["inputs"]["text"] = negative_prompt
        wf["latent"]["inputs"].update(
            width=int(width) // 32 * 32,
            height=int(height) // 32 * 32,
            length=int(num_frames),
        )
        wf["sampler"]["inputs"]["seed"] = (
            int(seed) if seed is not None else int(time.time() * 1000) % (2**32)
        )
        wf["sampler"]["inputs"]["steps"] = int(steps)

        client_id = str(uuid.uuid4())
        resp = requests.post(
            f"{self.comfyui_url}/prompt", json={"prompt": wf, "client_id": client_id}, timeout=30
        )
        if resp.status_code != 200:
            raise RuntimeError(f"ComfyUI rejected the workflow: {resp.text[:800]}")
        prompt_id = resp.json()["prompt_id"]
        return self._wait(prompt_id, output_dir, timeout_s, progress_callback)

    def _wait(self, prompt_id: str, output_dir: str, timeout_s: float, progress_callback) -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            time.sleep(2)
            history = requests.get(f"{self.comfyui_url}/history/{prompt_id}", timeout=10).json()
            entry = history.get(prompt_id)
            if not entry:
                if progress_callback:
                    progress_callback(0.0, "rendering")
                continue
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                detail = msgs[-1][1].get("exception_message", "") if msgs else "unknown error"
                raise RuntimeError(f"ComfyUI failed: {detail}")
            if not status.get("completed"):
                continue
            # SaveVideo reports its file under "images" (with animated: true);
            # older video nodes used "videos" or "gifs". Accept any of them.
            for node_output in entry.get("outputs", {}).values():
                for key in ("videos", "gifs", "images"):
                    for item in node_output.get(key, []):
                        name = item.get("filename", "")
                        if name.lower().endswith((".mp4", ".webm", ".mkv", ".mov")):
                            dest = Path(output_dir) / Path(name).name
                            self._download(item, dest)
                            return str(dest)
            raise RuntimeError("ComfyUI finished but produced no video file")
        raise TimeoutError(f"ComfyUI did not finish within {timeout_s:.0f}s")

    def _download(self, item: dict, dest: Path):
        params = {
            "filename": item["filename"],
            "subfolder": item.get("subfolder", ""),
            "type": item.get("type", "output"),
        }
        with requests.get(f"{self.comfyui_url}/view", params=params, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)

    def health_check(self) -> bool:
        try:
            return requests.get(f"{self.comfyui_url}/system_stats", timeout=5).status_code == 200
        except Exception:
            return False
