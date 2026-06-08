"""Voice cloning — reference voice management for XTTS."""
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File

router = APIRouter(prefix="/voices", tags=["voices"])

VOICES_DIR = Path("app/voices")


@router.get("/")
def list_voices():
    """Return all user-uploaded reference voice clips for XTTS."""
    from app.backend.pipeline.xtts_client import list_cached_voices, is_available
    return {
        "xtts_available": is_available(),
        "voices":         list_cached_voices(str(VOICES_DIR)),
    }


@router.post("/upload")
async def upload_voice(name: str, file: UploadFile = File(...)):
    """
    Upload a 6-30 second WAV/MP3 clip as a reference for voice cloning.
    `name` becomes the voice id (slugified).
    """
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name).strip("_").lower()
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid voice name")

    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    dest = VOICES_DIR / f"{safe_name}.wav"

    if dest.exists():
        raise HTTPException(status_code=409, detail=f"Voice '{safe_name}' already exists")

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "id":       safe_name,
        "name":     name,
        "path":     str(dest),
        "size_kb":  dest.stat().st_size // 1024,
    }


@router.delete("/{voice_id}")
def delete_voice(voice_id: str):
    path = VOICES_DIR / f"{voice_id}.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")
    path.unlink()
    return {"deleted": voice_id}
