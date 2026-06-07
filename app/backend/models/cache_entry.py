from sqlalchemy import Column, String, DateTime, Integer
from datetime import datetime
import uuid
from app.backend.db import Base


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    cache_key  = Column(String, unique=True, nullable=False, index=True)
    video_path = Column(String, nullable=False)
    hit_count  = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_hit   = Column(DateTime, nullable=True)
