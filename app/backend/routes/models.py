"""Model registry endpoints."""
import json
from pathlib import Path
from fastapi import APIRouter
from app.backend.services import model_registry

router = APIRouter(prefix="/models", tags=["models"])

CATALOG_PATH = Path("installer/catalog.json")


@router.get("/")
def list_models():
    return model_registry.get_all()


@router.get("/llm")
def list_llm_models():
    return model_registry.get_by_type("llm")


@router.get("/video")
def list_video_models():
    return model_registry.get_by_type("video")


@router.get("/tts")
def list_tts_models():
    return model_registry.get_by_type("tts")


@router.post("/refresh")
def refresh_registry():
    model_registry.refresh()
    return {"refreshed": True, "count": len(model_registry.get_all())}


@router.get("/catalog")
def get_catalog():
    if CATALOG_PATH.exists():
        return json.loads(CATALOG_PATH.read_text())
    return {"version": "unknown", "models": []}


@router.post("/install/ollama/{model_id}")
def install_ollama_model(model_id: str):
    """Trigger an ollama pull for a catalog model. Returns immediately — pull runs in background."""
    import subprocess, threading
    catalog_data = json.loads(CATALOG_PATH.read_text()) if CATALOG_PATH.exists() else {}
    entry = next((m for m in catalog_data.get("models", []) if m["id"] == model_id), None)
    if not entry or entry.get("install_method") != "ollama":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Not an Ollama-installable model")
    ollama_model = entry["ollama_model"]

    def _pull():
        subprocess.run(["ollama", "pull", ollama_model], capture_output=True)
        model_registry.refresh()

    threading.Thread(target=_pull, daemon=True).start()
    return {"pulling": ollama_model, "message": f"Pulling {ollama_model} in background"}
