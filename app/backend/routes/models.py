"""Model registry endpoints."""
from fastapi import APIRouter
from app.backend.services import model_registry

router = APIRouter(prefix="/models", tags=["models"])


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
