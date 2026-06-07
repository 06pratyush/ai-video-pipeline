"""
VRAM-aware model lifecycle manager.
Ensures only one heavy model lives in VRAM at a time on memory-constrained GPUs.
"""
import requests
from typing import Optional

OLLAMA_URL = "http://localhost:11434"

# VRAM requirements in MB for known models
MODEL_VRAM_MB: dict[str, int] = {
    "wan2.1-14b":          16384,
    "wan2.1-1.3b":          8192,
    "ltx-video":            8192,
    "cogvideox-5b":        12288,
    "animatediff":          6144,
    "musicgen-small":       2048,
    "whisper-base":          512,
    "whisper-small":        1024,
}

# Preferred model → fallback chain ordered by VRAM usage (low to high)
MODEL_FALLBACK: dict[str, list[str]] = {
    "wan2.1-14b": ["wan2.1-1.3b"],
    "cogvideox-5b": ["wan2.1-1.3b"],
}


def unload_ollama_model(model: str) -> bool:
    """
    Ask Ollama to immediately unload a model from VRAM (keep_alive=0).
    Returns True if the request succeeded.
    """
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": "", "keep_alive": 0},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def prepare_for_video(llm_model: Optional[str] = None) -> None:
    """
    Called before starting video generation (ComfyUI/Wan).
    Unloads the active LLM from Ollama to free VRAM.
    """
    if llm_model:
        unload_ollama_model(llm_model)


def prepare_for_llm() -> None:
    """
    Called before running LLM inference.
    Currently a no-op — Ollama loads lazily and ComfyUI keeps its own context.
    Future: signal ComfyUI to unload if memory pressure detected.
    """
    pass


def get_free_vram_mb() -> int:
    """Query nvidia-smi for current free VRAM in MB (fast, no full hardware scan)."""
    import subprocess
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return 0


def route_video_model(
    preferred_id: str,
    free_vram_mb: int,
) -> tuple[str, Optional[str]]:
    """
    Given a preferred model and available VRAM, return the best model to use.
    Returns (model_id, warning_message | None).
    warning_message is set when we had to downgrade.
    """
    required = MODEL_VRAM_MB.get(preferred_id, 0)
    if required == 0 or free_vram_mb == 0:
        return preferred_id, None  # unknown requirements or can't check — proceed

    if free_vram_mb >= required:
        return preferred_id, None

    # Try fallbacks
    for fallback in MODEL_FALLBACK.get(preferred_id, []):
        fallback_required = MODEL_VRAM_MB.get(fallback, 0)
        if free_vram_mb >= fallback_required:
            msg = (
                f"Used {fallback} instead of {preferred_id} "
                f"({free_vram_mb}MB free, need {required}MB)"
            )
            return fallback, msg

    # No fallback fits — proceed anyway and let the model fail naturally
    return preferred_id, f"Low VRAM ({free_vram_mb}MB free, need {required}MB) — generation may fail"
