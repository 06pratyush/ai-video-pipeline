"""Keyframe images for character consistency (FLUX via ComfyUI, on the GPU).

Engines, chosen per render with ``consistency``:

* ``schnell`` - FLUX.1 schnell, text only, 4 steps, Apache-2.0 (commercial use is fine).
  Consistency comes from repeating the same character description and seed.
* ``kontext`` - FLUX.1 Kontext dev edits a character reference image into each scene, so
  the face, beard and clothes carry over best. Its licence is NON-COMMERCIAL.
* ``qwen`` - reserved: Qwen-Image-Edit takes three references natively and is Apache-2.0,
  but needs far more memory than an 8 GB card has. Added with its workflow in a later PR.

The usual flow: draw each character once with schnell (the "character sheet"), then draw
one keyframe per scene with Kontext, then let Wan2.2 animate from it. A scene with several
characters hands Kontext one stitched sheet, because Kontext conditions on a single image.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from app.backend.pipeline.comfy_client import (
    COMFYUI_URL, IMAGE_EXT, ComfyClient, load_workflow, require_nodes, set_inputs,
)

WORKFLOWS = {"schnell": "flux_schnell_gguf.json", "kontext": "flux_kontext_gguf.json"}
DEFAULT_STEPS = {"schnell": 4, "kontext": 20}
MAX_REFS = {"schnell": 0, "kontext": 1}
LICENCE = {"schnell": "apache-2.0", "kontext": "flux-1-dev-non-commercial"}
NON_COMMERCIAL = {"kontext"}

# Rough peak VRAM per engine, used only to refuse an engine that cannot fit.
VRAM_MB = {"schnell": 6144, "kontext": 6656}

# Chosen when the caller expresses no preference. Only commercial-safe engines belong
# here: a non-commercial model is something a user opts into by name, never by default.
AUTO_PREFERENCE = ("schnell",)
# Tried in turn when the requested engine is missing or will not fit.
DEGRADE = ("kontext", "schnell")

_FLUX_SHARED = ("text_encoders/t5-v1_1-xxl-encoder-Q4_K_M.gguf",
                "text_encoders/clip_l.safetensors", "vae/ae.safetensors")

# Per engine, because the shared files are not shared across model families.
REQUIRED_FILES: dict[str, tuple[str, ...]] = {
    "schnell": ("unet/flux1-schnell-Q4_K_S.gguf", *_FLUX_SHARED),
    "kontext": ("unet/flux1-kontext-dev-Q4_K_M.gguf", *_FLUX_SHARED),
}


def _models_dir(models_dir: str | Path | None = None) -> Path:
    if models_dir:
        return Path(models_dir)
    return Path(__file__).resolve().parents[2] / "runtime" / "comfyui" / "models"


def available(mode: str, models_dir: str | Path | None = None) -> bool:
    """True when every file this engine needs is installed."""
    if mode not in REQUIRED_FILES:
        return False
    base = _models_dir(models_dir)
    return all((base / n).is_file() for n in REQUIRED_FILES[mode])


def fits(mode: str, budget_mb: int | None) -> bool:
    """True when the engine fits the caller's memory budget (None = do not check)."""
    return budget_mb is None or VRAM_MB.get(mode, 0) <= budget_mb


def resolve_engine(requested: str | None, *, models_dir: str | Path | None = None,
                   budget_mb: int | None = None) -> str:
    """Pick the keyframe engine to actually use. Degrades, never raises.

    ``"none"`` is honoured literally. A named engine is honoured when it is installed and
    affordable, otherwise the next engine in :data:`DEGRADE` that is, and finally
    ``"none"``. ``None`` means "choose for me", which only ever picks a commercial-safe
    engine. ``budget_mb`` comes from the caller (the app passes free VRAM) so this module
    stays free of service imports.
    """
    if requested == "none":
        return "none"
    if requested:
        if available(requested, models_dir) and fits(requested, budget_mb):
            return requested
        for fallback in DEGRADE:
            if fallback != requested and available(fallback, models_dir) \
                    and fits(fallback, budget_mb):
                return fallback
        return "none"
    for mode in AUTO_PREFERENCE:
        if available(mode, models_dir) and fits(mode, budget_mb):
            return mode
    return "none"


def snap16(v: int) -> int:
    return max(256, int(v) // 16 * 16)


def keyframe_size(video_w: int, video_h: int, megapixels: float = 1.0) -> tuple[int, int]:
    """Same aspect ratio as the video, about 1 MP (what FLUX is trained for), multiple of 16."""
    scale = (megapixels * 1_000_000 / (video_w * video_h)) ** 0.5
    return snap16(video_w * scale), snap16(video_h * scale)


def _as_sequence(references: str | Path | Sequence[str | Path] | None) -> tuple[str, ...]:
    if references is None:
        return ()
    if isinstance(references, (str, Path)):
        return (str(references),)
    return tuple(str(r) for r in references)


def build_workflow(template: dict, mode: str, prompt: str, width: int, height: int,
                   seed: int, steps: int | None = None,
                   references: str | Path | Sequence[str | Path] | None = None) -> dict:
    refs = _as_sequence(references)
    allowed = MAX_REFS.get(mode, 0)
    if len(refs) > allowed:
        raise ValueError(f"{mode} takes at most {allowed} reference image(s), got {len(refs)}; "
                         f"stitch them into one sheet first")
    values = {
        "positive": {"text": prompt},
        "latent": {"width": snap16(width), "height": snap16(height)},
        "sampler": {"seed": int(seed), "steps": int(steps or DEFAULT_STEPS[mode])},
    }
    if mode == "kontext":
        if len(refs) != 1:
            raise ValueError("kontext mode needs exactly one reference image")
        values["ref"] = {"image": refs[0]}
    return set_inputs(template, values)


class ImageClient:
    def __init__(self, mode: str = "schnell", comfyui_url: str = COMFYUI_URL,
                 session=None):
        if mode not in WORKFLOWS:
            raise ValueError(f"unknown image mode {mode!r}; use one of {sorted(WORKFLOWS)}")
        self.mode = mode
        self.comfy = ComfyClient(comfyui_url, session)
        self.template = load_workflow(WORKFLOWS[mode])
        require_nodes(self.template, "positive", "latent", "sampler", "save", name=WORKFLOWS[mode])
        if mode == "kontext":
            require_nodes(self.template, "ref", name=WORKFLOWS[mode])

    def generate(self, prompt: str, dest: str | Path, width: int = 768, height: int = 1344,
                 seed: int = 0, steps: int | None = None,
                 references: str | Path | Sequence[str | Path] | None = None,
                 timeout_s: float = 1800) -> Path:
        uploaded = [self.comfy.upload(r) for r in _as_sequence(references)]
        wf = build_workflow(self.template, self.mode, prompt, width, height, seed, steps,
                            uploaded)
        return self.comfy.run(wf, dest, IMAGE_EXT, timeout_s)
