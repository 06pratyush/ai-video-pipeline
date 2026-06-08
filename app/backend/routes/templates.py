"""Template CRUD + apply-to-project endpoints."""
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.backend.db import get_db
from app.backend.models.project import Project
from app.backend.models.template import Template

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    skill_id: Optional[str] = None
    voice: str = "af_sarah"
    num_scenes: int = 3
    script_seed: Optional[str] = None
    render_opts: Optional[dict] = None
    source_project_id: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    skill_id: Optional[str] = None
    voice: Optional[str] = None
    num_scenes: Optional[int] = None
    script_seed: Optional[str] = None
    render_opts: Optional[dict] = None


class TemplateApply(BaseModel):
    project_name: str
    topic: str
    script: Optional[str] = None  # overrides script_seed


def _to_dict(t: Template) -> dict:
    return {
        "id":          t.id,
        "name":        t.name,
        "description": t.description,
        "skill_id":    t.skill_id,
        "voice":       t.voice,
        "num_scenes":  t.num_scenes,
        "script_seed": t.script_seed,
        "render_opts": json.loads(t.render_opts) if t.render_opts else None,
        "source_project_id": t.source_project_id,
        "use_count":   t.use_count,
        "created_at":  t.created_at.isoformat() if t.created_at else None,
        "updated_at":  t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("/")
def list_templates(db: Session = Depends(get_db)):
    items = db.query(Template).order_by(Template.created_at.desc()).all()
    return [_to_dict(t) for t in items]


@router.post("/")
def create_template(data: TemplateCreate, db: Session = Depends(get_db)):
    t = Template(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        skill_id=data.skill_id,
        voice=data.voice,
        num_scenes=data.num_scenes,
        script_seed=data.script_seed,
        render_opts=json.dumps(data.render_opts) if data.render_opts else None,
        source_project_id=data.source_project_id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_dict(t)


@router.post("/from-project/{project_id}")
def create_template_from_project(
    project_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Save a project's current configuration as a reusable template."""
    p = db.query(Project).filter_by(id=project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    t = Template(
        id=str(uuid.uuid4()),
        name=payload.get("name") or f"{p.name} template",
        description=payload.get("description"),
        skill_id=p.skill_id,
        voice=p.voice,
        num_scenes=p.num_scenes,
        script_seed=payload.get("include_script", False) and p.script or None,
        render_opts=json.dumps(payload.get("render_opts")) if payload.get("render_opts") else None,
        source_project_id=p.id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_dict(t)


@router.get("/{template_id}")
def get_template(template_id: str, db: Session = Depends(get_db)):
    t = db.query(Template).filter_by(id=template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return _to_dict(t)


@router.patch("/{template_id}")
def update_template(template_id: str, data: TemplateUpdate, db: Session = Depends(get_db)):
    t = db.query(Template).filter_by(id=template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    for field, value in data.model_dump(exclude_none=True).items():
        if field == "render_opts":
            setattr(t, field, json.dumps(value))
        else:
            setattr(t, field, value)
    db.commit()
    db.refresh(t)
    return _to_dict(t)


@router.delete("/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db)):
    t = db.query(Template).filter_by(id=template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(t)
    db.commit()
    return {"deleted": template_id}


@router.post("/{template_id}/apply")
def apply_template(template_id: str, data: TemplateApply, db: Session = Depends(get_db)):
    """Create a new project from a template."""
    t = db.query(Template).filter_by(id=template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    script = data.script if data.script is not None else (t.script_seed or "")
    project = Project(
        id=str(uuid.uuid4()),
        name=data.project_name,
        topic=data.topic,
        script=script,
        voice=t.voice,
        num_scenes=t.num_scenes,
        skill_id=t.skill_id,
    )
    db.add(project)

    # Increment use_count
    t.use_count = (t.use_count or 0) + 1
    db.commit()
    db.refresh(project)

    from pathlib import Path
    Path(f"app/projects/{project.id}").mkdir(parents=True, exist_ok=True)

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "topic": project.topic,
            "script": project.script,
            "voice": project.voice,
            "num_scenes": project.num_scenes,
            "skill_id": project.skill_id,
            "status": project.status,
        },
        "template_render_opts": json.loads(t.render_opts) if t.render_opts else None,
    }
