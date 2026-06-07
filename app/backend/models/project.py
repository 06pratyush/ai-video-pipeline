from sqlalchemy import Column, String, Integer, Text, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.backend.db import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    script = Column(Text, nullable=True)
    narration = Column(Text, nullable=True)
    skill_id = Column(String, nullable=True)
    voice = Column(String, default="af_sarah")
    num_scenes = Column(Integer, default=3)
    status = Column(String, default="idle")  # idle | queued | running | done | error
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    audio_duration = Column(Float, nullable=True)
    final_path = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)

    scenes = relationship("Scene", back_populates="project", cascade="all, delete-orphan")
    queue_items = relationship("QueueItem", back_populates="project", cascade="all, delete-orphan")
