"""System health, hardware info, and service status endpoints."""
from fastapi import APIRouter
from app.backend.services import ollama_manager, comfyui_manager
from app.backend.services.hardware_monitor import detect_hardware

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/status")
def full_status():
    hw = detect_hardware()
    return {
        "hardware": {
            "gpu_name": hw.gpu_name,
            "vram_total_gb": round(hw.vram_total_gb, 1),
            "vram_free_mb": hw.vram_free_mb,
            "vram_tier": hw.vram_tier,
            "cpu_cores": hw.cpu_cores,
            "ram_total_gb": hw.ram_total_gb,
            "platform": hw.platform,
        },
        "services": {
            "ollama": ollama_manager.status(),
            "comfyui": comfyui_manager.status(),
        },
    }


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
