"""Shared ComfyUI client for every GPU stage (images, video, smoothing, music).

Workflows live in ``app/workflows/`` in ComfyUI's API format with readable node ids
(``positive``, ``latent``, ``sampler``, ``save`` ...). Callers change inputs by node id
with :func:`set_inputs`, so a workflow edit that renames a node fails loudly here
instead of silently rendering the wrong thing.

Everything talks to ComfyUI on 127.0.0.1 only. Files handed to ComfyUI are uploaded
under names this client generates, so nothing a story file says can choose a path.
"""
from __future__ import annotations

import copy
import json
import time
import uuid
from pathlib import Path

import requests

COMFYUI_URL = "http://127.0.0.1:8188"
WORKFLOW_DIR = Path(__file__).resolve().parents[2] / "workflows"

MEDIA_KEYS = ("videos", "gifs", "images", "audio")
VIDEO_EXT = (".mp4", ".webm", ".mkv", ".mov")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
AUDIO_EXT = (".flac", ".wav", ".mp3", ".opus", ".ogg")


class ComfyError(RuntimeError):
    """ComfyUI rejected or failed a job; the message is ComfyUI's own error text."""


def load_workflow(name_or_path: str | Path) -> dict:
    """Load a workflow by file name from app/workflows/ or by explicit path."""
    p = Path(name_or_path)
    if not p.is_absolute() and not p.exists():
        p = WORKFLOW_DIR / p.name
    if not p.exists():
        raise FileNotFoundError(f"Workflow JSON not found: {name_or_path}")
    return json.loads(p.read_text(encoding="utf-8"))


def set_inputs(wf: dict, values: dict[str, dict]) -> dict:
    """Return a copy of ``wf`` with ``{node_id: {input: value}}`` applied."""
    out = copy.deepcopy(wf)
    for node_id, inputs in values.items():
        if node_id not in out:
            raise KeyError(f"Workflow has no node '{node_id}'")
        out[node_id]["inputs"].update(inputs)
    return out


def require_nodes(wf: dict, *node_ids: str, name: str = "workflow") -> None:
    missing = [n for n in node_ids if n not in wf]
    if missing:
        raise ValueError(f"{name} is missing node(s): {', '.join(missing)}")


class ComfyClient:
    def __init__(self, url: str = COMFYUI_URL, session: requests.Session | None = None):
        self.url = url.rstrip("/")
        self.http = session or requests.Session()

    # -- health -------------------------------------------------------------------
    def is_up(self) -> bool:
        try:
            return self.http.get(f"{self.url}/system_stats", timeout=5).status_code == 200
        except requests.RequestException:
            return False

    def free(self, unload_models: bool = True) -> None:
        """Ask ComfyUI to drop cached models so the next stage gets the whole GPU."""
        try:
            self.http.post(f"{self.url}/free",
                           json={"unload_models": unload_models, "free_memory": True}, timeout=30)
        except requests.RequestException:
            pass

    # -- inputs ---------------------------------------------------------------------
    def upload(self, path: str | Path, kind: str = "image") -> str:
        """Upload a local file into ComfyUI's input folder; returns the name to reference.

        The stored name is generated here (``aivs_<uuid><ext>``), never taken from the
        caller, so an upload cannot be steered to another folder.
        """
        src = Path(path)
        name = f"aivs_{uuid.uuid4().hex}{src.suffix.lower()}"
        with open(src, "rb") as f:
            r = self.http.post(
                f"{self.url}/upload/image",
                files={"image": (name, f, "application/octet-stream")},
                data={"type": "input", "overwrite": "true"},
                timeout=300,
            )
        if r.status_code != 200:
            raise ComfyError(f"Upload of {src.name} failed: {r.text[:300]}")
        info = r.json()
        sub = info.get("subfolder") or ""
        return f"{sub}/{info['name']}" if sub else info["name"]

    # -- jobs -------------------------------------------------------------------------
    def submit(self, wf: dict) -> str:
        r = self.http.post(f"{self.url}/prompt",
                           json={"prompt": wf, "client_id": str(uuid.uuid4())}, timeout=60)
        if r.status_code != 200:
            raise ComfyError(f"ComfyUI rejected the workflow: {r.text[:1200]}")
        return r.json()["prompt_id"]

    def wait(self, prompt_id: str, timeout_s: float = 3600, poll_s: float = 2.0,
             progress_callback=None) -> dict:
        """Block until the job finishes; return its ``outputs`` dict."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            time.sleep(poll_s)
            entry = self.http.get(f"{self.url}/history/{prompt_id}", timeout=15).json().get(prompt_id)
            if not entry:
                if progress_callback:
                    progress_callback(0.0, "rendering")
                continue
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                detail = msgs[-1][1] if msgs else {}
                raise ComfyError(
                    f"ComfyUI failed in node {detail.get('node_id', '?')} "
                    f"({detail.get('node_type', '?')}): {detail.get('exception_message', 'unknown error')}"
                )
            if status.get("completed"):
                return entry.get("outputs", {})
        raise TimeoutError(f"ComfyUI did not finish within {timeout_s:.0f}s")

    @staticmethod
    def output_files(outputs: dict, exts: tuple[str, ...]) -> list[dict]:
        """Files the job *saved* (type "output"). Loader nodes such as LoadVideo also list
        their input file in the history, so anything of type "input" is never returned."""
        found = []
        for node_output in outputs.values():
            for key in MEDIA_KEYS:
                for item in node_output.get(key, []) or []:
                    if (isinstance(item, dict) and item.get("type", "output") == "output"
                            and item.get("filename", "").lower().endswith(exts)):
                        found.append(item)
        return found

    def download(self, item: dict, dest: str | Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        params = {"filename": item["filename"], "subfolder": item.get("subfolder", ""),
                  "type": item.get("type", "output")}
        with self.http.get(f"{self.url}/view", params=params, stream=True, timeout=300) as r:
            r.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            tmp.replace(dest)
        return dest

    def run(self, wf: dict, dest: str | Path, exts: tuple[str, ...], timeout_s: float = 3600,
            progress_callback=None) -> Path:
        """Submit, wait, and save the first output file with one of ``exts`` to ``dest``."""
        outputs = self.wait(self.submit(wf), timeout_s, progress_callback=progress_callback)
        files = self.output_files(outputs, exts)
        if not files:
            raise ComfyError(f"ComfyUI finished but produced no {'/'.join(exts)} file")
        return self.download(files[0], dest)
