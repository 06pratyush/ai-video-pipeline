"""Long-form mode — preview script chunking and queue sub-project batches."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
from pathlib import Path

from app.backend.db import get_db
from app.backend.models.project import Project
from app.backend.services import generation_queue, long_form_chunker

router = APIRouter(prefix="/longform", tags=["longform"])


class PreviewRequest(BaseModel):
    script: str
    chunk_words: int = 180


class CreateRequest(BaseModel):
    base_name: str
    topic: str
    script: str
    voice: str = "af_sarah"
    skill_id: Optional[str] = None
    chunk_words: int = 180
    render_opts: Optional[dict] = None


@router.post("/preview")
def preview_chunks(req: PreviewRequest):
    """Show how a script would be split without creating any projects."""
    chunks = long_form_chunker.plan_long_form(req.script, chunk_words=req.chunk_words)
    total_seconds = sum(c["est_duration_sec"] for c in chunks)
    return {
        "chunks":            chunks,
        "total_chunks":      len(chunks),
        "total_est_seconds": round(total_seconds, 1),
        "needs_chunking":    long_form_chunker.needs_chunking(req.script),
    }


@router.post("/create")
def create_long_form(req: CreateRequest, db: Session = Depends(get_db)):
    """
    Split the script and create N sub-projects, queueing them all.
    Each sub-project renders as a normal pipeline run; user concatenates after.
    """
    if not req.script.strip():
        raise HTTPException(status_code=400, detail="Script is required")

    plans = long_form_chunker.plan_long_form(req.script, chunk_words=req.chunk_words)
    if not plans:
        raise HTTPException(status_code=400, detail="Script produced no chunks")

    opts_dict = req.render_opts or {}
    created: list[dict] = []

    for plan in plans:
        project = Project(
            id=str(uuid.uuid4()),
            name=f"{req.base_name} — part {plan['index'] + 1}/{plan['total']}",
            topic=f"{req.topic}-pt{plan['index'] + 1}",
            script=plan["script"],
            voice=req.voice,
            num_scenes=plan["num_scenes"],
            skill_id=req.skill_id,
            status="queued",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        Path(f"app/projects/{project.id}").mkdir(parents=True, exist_ok=True)
        queue_id = generation_queue.enqueue(project.id, opts_dict)

        created.append({
            "project_id":    project.id,
            "queue_item_id": queue_id,
            "chunk_index":   plan["index"],
            "scene_count":   plan["num_scenes"],
            "est_seconds":   plan["est_duration_sec"],
        })

    return {
        "total_chunks": len(created),
        "items":        created,
    }
