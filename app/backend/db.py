"""Database engine and session setup."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path

# Overridable so tests can run against a throwaway database instead of the
# user's real project data.
DB_PATH = Path(os.environ.get("AIVS_DB_PATH", Path(__file__).parent / "db.sqlite"))
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.backend.models import (  # noqa: F401
        project, scene, queue_item, cache_entry, template, project_version,
    )
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Apply additive column migrations that create_all won't handle on existing tables."""
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE queue_items ADD COLUMN render_opts TEXT",
        # cache_entries is created by create_all, but guard for existing DBs
        """CREATE TABLE IF NOT EXISTS cache_entries (
            id TEXT PRIMARY KEY,
            cache_key TEXT UNIQUE NOT NULL,
            video_path TEXT NOT NULL,
            hit_count INTEGER DEFAULT 0,
            created_at DATETIME,
            last_hit DATETIME
        )""",
        "CREATE INDEX IF NOT EXISTS ix_cache_entries_cache_key ON cache_entries(cache_key)",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # column already exists or table doesn't exist yet
