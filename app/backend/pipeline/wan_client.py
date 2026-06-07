"""Wan2.1 video generation via ComfyUI — adapted from root wan_client.py."""
import json
import time
import uuid
import requests
from pathlib import Path

COMFYUI_URL = "http://localhost:8188"


class WanVideoClient:
    def __init__(self, workflow_path: str, comfyui_url: str = COMFYUI_URL):
        self.comfyui_url = comfyui_url
        wf_file = Path(workflow_path)
        if not wf_file.exists():
            raise FileNotFoundError(f"Workflow JSON not found: {workflow_path}")
        with open(wf_file) as f:
            self.workflow_template = json.load(f)

    def generate(
        self,
        prompt: str,
        output_dir: str,
        width: int = 832,
        height: int = 480,
        num_frames: int = 81,
        steps: int = 20,
        seed: int | None = None,
        progress_callback=None,
    ) -> str:
        """Submit prompt to ComfyUI and poll until done. Returns output video path."""
        workflow = json.loads(json.dumps(self.workflow_template))
        actual_seed = seed if seed is not None else int(time.time() * 1000) % (2**32)

        for node in workflow.values():
            inputs = node.get("inputs", {})
            if "positive" in inputs or "text" in inputs:
                for key in ("text", "positive"):
                    if key in inputs:
                        inputs[key] = prompt
            if "seed" in inputs:
                inputs["seed"] = actual_seed
            if "width" in inputs:
                inputs["width"] = width
            if "height" in inputs:
                inputs["height"] = height
            if "num_frames" in inputs or "frame_count" in inputs:
                for key in ("num_frames", "frame_count"):
                    if key in inputs:
                        inputs[key] = num_frames
            if "steps" in inputs:
                inputs["steps"] = steps

        client_id = str(uuid.uuid4())
        payload = {"prompt": workflow, "client_id": client_id}
        resp = requests.post(f"{self.comfyui_url}/prompt", json=payload, timeout=30)
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        output_path = self._poll_until_done(prompt_id, client_id, output_dir, progress_callback)
        return output_path

    def _poll_until_done(
        self, prompt_id: str, client_id: str, output_dir: str, progress_callback=None
    ) -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        while True:
            time.sleep(2)
            resp = requests.get(f"{self.comfyui_url}/history/{prompt_id}", timeout=10)
            history = resp.json()
            if prompt_id not in history:
                if progress_callback:
                    progress_callback(0.0, "waiting")
                continue

            entry = history[prompt_id]
            if "outputs" not in entry:
                continue

            for node_output in entry["outputs"].values():
                if "videos" in node_output:
                    for vid in node_output["videos"]:
                        filename = vid["filename"]
                        subfolder = vid.get("subfolder", "")
                        dl_url = (
                            f"{self.comfyui_url}/view?"
                            f"filename={filename}&subfolder={subfolder}&type=output"
                        )
                        dest = Path(output_dir) / filename
                        self._download(dl_url, str(dest))
                        return str(dest)

    def _download(self, url: str, dest: str):
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

    def health_check(self) -> bool:
        try:
            resp = requests.get(f"{self.comfyui_url}/system_stats", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
