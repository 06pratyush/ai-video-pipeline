"""Discovers and catalogs all installed AI models."""
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from app.backend.services import ollama_manager


@dataclass
class ModelInfo:
    id: str
    name: str
    type: str          # llm | video | tts | upscaler | interpolator | transcriber
    source: str        # ollama | comfyui | local
    vram_required_mb: int = 0
    size_mb: int = 0
    installed: bool = False
    capabilities: list[str] = field(default_factory=list)
    description: str = ""


def scan_ollama_models() -> list[ModelInfo]:
    models = []
    for m in ollama_manager.list_models():
        name = m.get("name", "")
        size_bytes = m.get("size", 0)
        models.append(ModelInfo(
            id=f"ollama:{name}",
            name=name,
            type="llm",
            source="ollama",
            size_mb=size_bytes // (1024 * 1024),
            installed=True,
            capabilities=["narration_refinement", "scene_prompt_generation"],
            description=f"Ollama LLM: {name}",
        ))
    return models


def scan_comfyui_models(comfyui_path: str | None = None) -> list[ModelInfo]:
    models = []
    candidates = [
        Path("app/runtime/comfyui/models"),
        Path("ComfyUI/models"),
    ]
    if comfyui_path:
        candidates.insert(0, Path(comfyui_path) / "models")

    for base in candidates:
        if not base.exists():
            continue
        for subdir in ("checkpoints", "unet", "diffusion_models"):
            for f in (base / subdir).glob("*.safetensors") if (base / subdir).exists() else []:
                name = f.stem
                size_mb = f.stat().st_size // (1024 * 1024)
                models.append(ModelInfo(
                    id=f"comfyui:{name}",
                    name=name,
                    type="video",
                    source="comfyui",
                    size_mb=size_mb,
                    installed=True,
                    capabilities=["text_to_video"],
                    description=f"ComfyUI video model: {name}",
                ))
        break  # only scan the first matching path
    return models


def scan_kokoro_voices() -> list[ModelInfo]:
    voices = [
        ("af_heart", "American Female - Heart"),
        ("af_bella", "American Female - Bella"),
        ("af_sarah", "American Female - Sarah"),
        ("af_nicole", "American Female - Nicole"),
        ("am_adam", "American Male - Adam"),
        ("am_michael", "American Male - Michael"),
        ("bf_emma", "British Female - Emma"),
        ("bm_george", "British Male - George"),
    ]
    return [
        ModelInfo(
            id=f"kokoro:{vid}",
            name=vname,
            type="tts",
            source="local",
            installed=True,
            capabilities=["text_to_speech"],
            description=vname,
        )
        for vid, vname in voices
    ]


def build_registry(comfyui_path: str | None = None) -> dict[str, ModelInfo]:
    registry: dict[str, ModelInfo] = {}
    for m in scan_ollama_models():
        registry[m.id] = m
    for m in scan_comfyui_models(comfyui_path):
        registry[m.id] = m
    for m in scan_kokoro_voices():
        registry[m.id] = m
    return registry


def registry_to_json(registry: dict[str, ModelInfo]) -> list[dict]:
    return [asdict(m) for m in registry.values()]


# Module-level cache, populated on daemon startup
_registry: dict[str, ModelInfo] = {}


def refresh(comfyui_path: str | None = None):
    global _registry
    _registry = build_registry(comfyui_path)


def get_all() -> list[dict]:
    return registry_to_json(_registry)


def get_by_type(model_type: str) -> list[dict]:
    return [asdict(m) for m in _registry.values() if m.type == model_type]


def get_active_llm() -> Optional[str]:
    """Return the name of the first installed Ollama LLM."""
    for m in _registry.values():
        if m.type == "llm" and m.installed:
            return m.name.split(":")[0] if ":" not in m.name else m.name
    return None
