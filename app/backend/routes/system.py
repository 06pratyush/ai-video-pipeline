"""System health, hardware info, and service status endpoints."""
import time
from fastapi import APIRouter
from app.backend.services import ollama_manager, comfyui_manager
from app.backend.services.hardware_monitor import detect_hardware, get_free_vram_mb

router = APIRouter(prefix="/system", tags=["system"])

# Cache full hardware detection (nvidia-smi is slow ~8s on some systems)
_hw_cache: dict = {}
_hw_cache_ts: float = 0.0
_HW_CACHE_TTL = 15.0  # seconds


def _get_hardware():
    global _hw_cache, _hw_cache_ts
    now = time.monotonic()
    if not _hw_cache or now - _hw_cache_ts > _HW_CACHE_TTL:
        hw = detect_hardware()
        _hw_cache = {
            "gpu_name": hw.gpu_name,
            "vram_total_gb": round(hw.vram_total_gb, 1),
            "vram_free_mb": hw.vram_free_mb,
            "vram_tier": hw.vram_tier,
            "cpu_cores": hw.cpu_cores,
            "ram_total_gb": hw.ram_total_gb,
            "platform": hw.platform,
        }
        _hw_cache_ts = now
    return _hw_cache


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/status")
def full_status():
    return {
        "hardware": _get_hardware(),
        "services": {
            "ollama":  ollama_manager.status(),
            "comfyui": comfyui_manager.status(),
        },
    }


@router.get("/vram")
def vram_live():
    """Fast endpoint — only queries free VRAM, no full hardware scan."""
    free_mb = get_free_vram_mb()
    hw = _hw_cache  # use cached total if available
    total_mb = int(hw.get("vram_total_gb", 0) * 1024) if hw else 0
    used_mb  = total_mb - free_mb if total_mb > 0 else 0
    return {
        "free_mb":  free_mb,
        "used_mb":  used_mb,
        "total_mb": total_mb,
        "pct_used": round(used_mb / total_mb * 100, 1) if total_mb > 0 else 0,
    }


@router.get("/cache")
def cache_stats():
    from app.backend.services.generation_cache import stats
    return stats()


@router.delete("/cache")
def clear_cache():
    from app.backend.services.generation_cache import clear
    n = clear()
    return {"cleared": n}


@router.post("/services/ollama/start")
def start_ollama():
    ok = ollama_manager.start()
    return {"started": ok, "status": ollama_manager.status()}


@router.post("/services/comfyui/start")
def start_comfyui():
    ok = comfyui_manager.start()
    return {"started": ok, "status": comfyui_manager.status()}


@router.post("/services/ollama/stop")
def stop_ollama():
    ollama_manager.stop()
    return {"stopped": True}


@router.post("/services/comfyui/stop")
def stop_comfyui():
    comfyui_manager.stop()
    return {"stopped": True}
