"""Project CRUD endpoints."""
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.backend.db import get_db
from app.backend.models.project import Project
from app.backend.models.scene import Scene

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    topic: str
    script: str
    voice: str = "af_sarah"
    num_scenes: int = 3
    skill_id: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    topic: Optional[str] = None
    script: Optional[str] = None
    voice: Optional[str] = None
    num_scenes: Optional[int] = None
    skill_id: Optional[str] = None


class SceneUpdate(BaseModel):
    prompt: Optional[str] = None
    status: Optional[str] = None  # locked | pending
    seed: Optional[int] = None


def _project_to_dict(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "topic": p.topic,
        "script": p.script,
        "narration": p.narration,
        "skill_id": p.skill_id,
        "voice": p.voice,
        "num_scenes": p.num_scenes,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "audio_duration": p.audio_duration,
        "final_path": p.final_path,
        "thumbnail_path": p.thumbnail_path,
    }


def _scene_to_dict(s: Scene) -> dict:
    return {
        "id": s.id,
        "project_id": s.project_id,
        "index": s.index,
        "prompt": s.prompt,
        "status": s.status,
        "video_path": s.video_path,
        "thumbnail_path": s.thumbnail_path,
        "duration": s.duration,
        "seed": s.seed,
        "model_used": s.model_used,
        "error_message": s.error_message,
    }


@router.get("/")
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return [_project_to_dict(p) for p in projects]


@router.post("/")
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        id=str(uuid.uuid4()),
        name=data.name,
        topic=data.topic,
        script=data.script,
        voice=data.voice,
        num_scenes=data.num_scenes,
        skill_id=data.skill_id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    # Create project folder
    Path(f"app/projects/{project.id}").mkdir(parents=True, exist_ok=True)
    return _project_to_dict(project)


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    p = db.query(Project).filter_by(id=project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_dict(p)


@router.patch("/{project_id}")
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db)):
    p = db.query(Project).filter_by(id=project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return _project_to_dict(p)


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    p = db.query(Project).filter_by(id=project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(p)
    db.commit()
    return {"deleted": project_id}


@router.get("/{project_id}/scenes")
def get_scenes(project_id: str, db: Session = Depends(get_db)):
    scenes = db.query(Scene).filter_by(project_id=project_id).order_by(Scene.index).all()
    return [_scene_to_dict(s) for s in scenes]


@router.patch("/{project_id}/scenes/{scene_id}")
def update_scene(
    project_id: str, scene_id: str, data: SceneUpdate, db: Session = Depends(get_db)
):
    s = db.query(Scene).filter_by(id=scene_id, project_id=project_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Scene not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return _scene_to_dict(s)


@router.get("/{project_id}/download")
def download_final(project_id: str, db: Session = Depends(get_db)):
    p = db.query(Project).filter_by(id=project_id).first()
    if not p or not p.final_path:
        raise HTTPException(status_code=404, detail="No final video available")
    if not Path(p.final_path).exists():
        raise HTTPException(status_code=404, detail="Final video file missing from disk")
    return FileResponse(p.final_path, media_type="video/mp4", filename=f"{p.topic}.mp4")
