from sqlalchemy import Column, String, Integer, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.backend.db import Base


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    index = Column(Integer, nullable=False)
    prompt = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending | generating | done | error | locked
    video_path = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)
    duration = Column(Float, nullable=True)
    seed = Column(Integer, nullable=True)
    model_used = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(Text, nullable=True)

    project = relationship("Project", back_populates="scenes")
