"""Project versioning — snapshots and restore."""
import json
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.backend.db import get_db
from app.backend.models.project import Project
from app.backend.models.scene import Scene
from app.backend.models.project_version import ProjectVersion, next_version_num

router = APIRouter(prefix="/projects/{project_id}/versions", tags=["versions"])


class VersionCreate(BaseModel):
    label: Optional[str] = None


def _to_dict(v: ProjectVersion) -> dict:
    return {
        "id":          v.id,
        "project_id":  v.project_id,
        "version_num": v.version_num,
        "label":       v.label,
        "snapshot":    json.loads(v.snapshot) if v.snapshot else {},
        "final_path":  v.final_path,
        "thumbnail":   v.thumbnail,
        "duration":    v.duration,
        "created_at":  v.created_at.isoformat() if v.created_at else None,
    }


def _snapshot_project(p: Project, scenes: list[Scene]) -> dict:
    return {
        "name":         p.name,
        "topic":        p.topic,
        "script":       p.script,
        "narration":    p.narration,
        "skill_id":     p.skill_id,
        "voice":        p.voice,
        "num_scenes":   p.num_scenes,
        "audio_duration": p.audio_duration,
        "scenes": [
            {
                "index":  s.index,
                "prompt": s.prompt,
                "seed":   s.seed,
                "status": s.status,
            }
            for s in scenes
        ],
    }


@router.get("/")
def list_versions(project_id: str, db: Session = Depends(get_db)):
    items = (
        db.query(ProjectVersion)
        .filter_by(project_id=project_id)
        .order_by(ProjectVersion.version_num.desc())
        .all()
    )
    return [_to_dict(v) for v in items]


@router.post("/")
def create_version(
    project_id: str,
    data: VersionCreate,
    db: Session = Depends(get_db),
):
    """Snapshot the current project state."""
    p = db.query(Project).filter_by(id=project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    scenes = db.query(Scene).filter_by(project_id=project_id).order_by(Scene.index).all()
    next_num = next_version_num(db, project_id)

    # Archive final video into a versioned path
    archived_path = None
    if p.final_path and Path(p.final_path).exists():
        version_dir = Path(f"app/projects/{project_id}/versions/v{next_num}")
        version_dir.mkdir(parents=True, exist_ok=True)
        archived = version_dir / "final.mp4"
        shutil.copy2(p.final_path, archived)
        archived_path = str(archived)

    v = ProjectVersion(
        id=str(uuid.uuid4()),
        project_id=project_id,
        version_num=next_num,
        label=data.label,
        snapshot=json.dumps(_snapshot_project(p, scenes)),
        final_path=archived_path,
        duration=int(p.audio_duration) if p.audio_duration else None,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return _to_dict(v)


@router.get("/{version_id}")
def get_version(project_id: str, version_id: str, db: Session = Depends(get_db)):
    v = db.query(ProjectVersion).filter_by(id=version_id, project_id=project_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return _to_dict(v)


@router.post("/{version_id}/restore")
def restore_version(project_id: str, version_id: str, db: Session = Depends(get_db)):
    """Apply a version's snapshot back onto the live project (does not delete current scenes)."""
    v = db.query(ProjectVersion).filter_by(id=version_id, project_id=project_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    p = db.query(Project).filter_by(id=project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    # Snapshot the live state first. Restoring overwrites the project's script,
    # narration and every scene prompt/seed in place; without this the user's
    # current work is destroyed with no way back.
    current_scenes = db.query(Scene).filter_by(project_id=project_id).order_by(Scene.index).all()
    backup_num = next_version_num(db, project_id)
    backup = ProjectVersion(
        id=str(uuid.uuid4()),
        project_id=project_id,
        version_num=backup_num,
        label=f"Auto-backup before restoring v{v.version_num}",
        snapshot=json.dumps(_snapshot_project(p, current_scenes)),
        # Deliberately not pointing at the live p.final_path: delete_version unlinks
        # final_path, so sharing the path would let deleting this backup destroy the
        # project's current video. Restore does not modify the video anyway.
        final_path=None,
        duration=int(p.audio_duration) if p.audio_duration else None,
    )
    db.add(backup)
    db.flush()  # reserve the version number within this transaction

    snap = json.loads(v.snapshot)
    p.script     = snap.get("script", p.script)
    p.narration  = snap.get("narration", p.narration)
    p.skill_id   = snap.get("skill_id", p.skill_id)
    p.voice      = snap.get("voice", p.voice)
    p.num_scenes = snap.get("num_scenes", p.num_scenes)

    # Restore scene prompts and seeds (keep ids stable)
    snap_scenes = {s["index"]: s for s in snap.get("scenes", [])}
    existing_scenes = db.query(Scene).filter_by(project_id=project_id).all()
    for s in existing_scenes:
        if s.index in snap_scenes:
            s.prompt = snap_scenes[s.index]["prompt"]
            s.seed   = snap_scenes[s.index].get("seed")

    db.commit()
    return {"restored": v.version_num, "backup_version": backup_num}


@router.delete("/{version_id}")
def delete_version(project_id: str, version_id: str, db: Session = Depends(get_db)):
    v = db.query(ProjectVersion).filter_by(id=version_id, project_id=project_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    # Cleanup archived video
    if v.final_path and Path(v.final_path).exists():
        try:
            Path(v.final_path).unlink()
        except OSError:
            pass
    db.delete(v)
    db.commit()
    return {"deleted": version_id}
