from sqlalchemy import Column, String, Integer, Text, DateTime
from datetime import datetime
import uuid
from app.backend.db import Base


class Template(Base):
    __tablename__ = "templates"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    skill_id    = Column(String, nullable=True)
    voice       = Column(String, default="af_sarah")
    num_scenes  = Column(Integer, default=3)
    script_seed = Column(Text, nullable=True)   # optional placeholder script
    render_opts = Column(Text, nullable=True)   # JSON: subtitles/music/interpolation/upscaling
    source_project_id = Column(String, nullable=True)  # which project this was forked from
    use_count   = Column(Integer, default=0)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
