from sqlalchemy import Column, String, Integer, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.backend.db import Base


class QueueItem(Base):
    __tablename__ = "queue_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    stage = Column(String, nullable=False)  # refining | audio | scene_N | merging | done
    status = Column(String, default="queued")  # queued | running | done | error | cancelled
    priority = Column(Integer, default=0)
    progress = Column(Float, default=0.0)
    eta_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    render_opts = Column(Text, nullable=True)  # JSON: {subtitles, music, interpolation, upscaling}
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="queue_items")
