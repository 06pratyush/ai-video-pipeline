from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from app.backend.db import Base


class ProjectVersion(Base):
    """
    A snapshot of a Project taken whenever a successful render completes.
    Stores enough metadata to restore or diff against later versions.
    """
    __tablename__ = "project_versions"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id   = Column(String, ForeignKey("projects.id"), nullable=False)
    version_num  = Column(Integer, nullable=False)
    label        = Column(String, nullable=True)            # optional user label
    snapshot     = Column(Text, nullable=False)             # JSON: project + scenes + render_opts
    final_path   = Column(String, nullable=True)            # archived final mp4 path
    thumbnail    = Column(String, nullable=True)
    duration     = Column(Integer, nullable=True)           # seconds
    created_at   = Column(DateTime, default=datetime.utcnow)

def next_version_num(db: Session, project_id: str) -> int:
    """
    Next version number for a project, derived from the highest existing one.

    Deriving it from a row count breaks after any deletion: with v1..v3 present,
    deleting v2 makes the count 2 and the "next" number 3 — colliding with the live
    v3 and overwriting its archived video at versions/v3/final.mp4.
    """
    highest = (
        db.query(func.max(ProjectVersion.version_num))
        .filter_by(project_id=project_id)
        .scalar()
    )
    return (highest or 0) + 1
