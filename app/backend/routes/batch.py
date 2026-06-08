"""Batch generation — queue multiple projects in one request."""
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.backend.db import get_db
from app.backend.models.project import Project
from app.backend.services import generation_queue

router = APIRouter(prefix="/batch", tags=["batch"])


class BatchItem(BaseModel):
    name: str
    topic: str
    script: str
    voice: Optional[str] = None
    num_scenes: Optional[int] = None
    skill_id: Optional[str] = None


class BatchRenderOpts(BaseModel):
    subtitles: bool = False
    music: bool = False
    interpolation: bool = False
    upscaling: bool = False


class BatchRequest(BaseModel):
    items: list[BatchItem]
    template_id: Optional[str] = None    # apply this template's settings to all items
    render_opts: Optional[BatchRenderOpts] = None


@router.post("/")
def create_batch(req: BatchRequest, db: Session = Depends(get_db)):
    """
    Create N projects and enqueue them all. They run sequentially through the
    generation queue worker. Returns created project + queue ids.
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="Batch must contain at least one item")

    template = None
    if req.template_id:
        from app.backend.models.template import Template
        template = db.query(Template).filter_by(id=req.template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

    results = []
    opts_dict = req.render_opts.model_dump() if req.render_opts else {}

    for item in req.items:
        voice      = item.voice      or (template.voice      if template else "af_sarah")
        num_scenes = item.num_scenes or (template.num_scenes if template else 3)
        skill_id   = item.skill_id   or (template.skill_id   if template else None)

        project = Project(
            id=str(uuid.uuid4()),
            name=item.name,
            topic=item.topic,
            script=item.script,
            voice=voice,
            num_scenes=num_scenes,
            skill_id=skill_id,
            status="queued",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        Path(f"app/projects/{project.id}").mkdir(parents=True, exist_ok=True)

        queue_id = generation_queue.enqueue(project.id, opts_dict)
        results.append({
            "project_id":    project.id,
            "queue_item_id": queue_id,
            "name":          project.name,
        })

    # Bump template use_count
    if template:
        template.use_count = (template.use_count or 0) + len(req.items)
        db.commit()

    return {
        "batch_size": len(results),
        "items":      results,
    }


@router.get("/")
def batch_status(db: Session = Depends(get_db)):
    """Return all currently queued/running batch projects."""
    from app.backend.models.queue_item import QueueItem
    items = (
        db.query(QueueItem)
        .filter(QueueItem.status.in_(["queued", "running"]))
        .order_by(QueueItem.created_at)
        .all()
    )
    return [
        {
            "queue_item_id": i.id,
            "project_id":    i.project_id,
            "stage":         i.stage,
            "status":        i.status,
            "progress":      i.progress,
        }
        for i in items
    ]
