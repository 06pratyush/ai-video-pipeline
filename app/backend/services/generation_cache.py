"""
Scene-level generation cache.
Cache key = sha256(prompt + seed + model_id + resolution).
On a cache hit the existing video file is reused — no GPU work needed.
"""
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.backend.db import SessionLocal
from app.backend.models.cache_entry import CacheEntry


def _make_key(prompt: str, seed: Optional[int], model_id: str, resolution: str) -> str:
    raw = f"{prompt}|{seed or 0}|{model_id}|{resolution}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get(
    prompt: str,
    seed: Optional[int],
    model_id: str,
    resolution: str,
) -> Optional[str]:
    """
    Return the cached video path if it exists and the file is still on disk.
    Updates hit_count and last_hit on a cache hit. Returns None on miss.
    """
    key = _make_key(prompt, seed, model_id, resolution)
    db = SessionLocal()
    try:
        entry = db.query(CacheEntry).filter_by(cache_key=key).first()
        if entry and Path(entry.video_path).exists():
            entry.hit_count += 1
            entry.last_hit = datetime.utcnow()
            db.commit()
            return entry.video_path
        if entry:
            # Stale entry — file was deleted
            db.delete(entry)
            db.commit()
        return None
    finally:
        db.close()


def put(
    prompt: str,
    seed: Optional[int],
    model_id: str,
    resolution: str,
    video_path: str,
) -> None:
    """Store a generated clip in the cache."""
    key = _make_key(prompt, seed, model_id, resolution)
    db = SessionLocal()
    try:
        existing = db.query(CacheEntry).filter_by(cache_key=key).first()
        if existing:
            existing.video_path = video_path
            existing.last_hit = datetime.utcnow()
        else:
            db.add(CacheEntry(cache_key=key, video_path=video_path))
        db.commit()
    finally:
        db.close()


def copy_cached(cached_path: str, dest_path: str) -> str:
    """Copy a cached clip to the project's scenes directory. Returns dest_path."""
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cached_path, dest_path)
    return dest_path


def stats() -> dict:
    db = SessionLocal()
    try:
        total = db.query(CacheEntry).count()
        hits  = db.query(CacheEntry).filter(CacheEntry.hit_count > 0).count()
        return {"total_entries": total, "entries_with_hits": hits}
    finally:
        db.close()


def clear() -> int:
    """Remove all cache entries. Returns number deleted."""
    db = SessionLocal()
    try:
        n = db.query(CacheEntry).delete()
        db.commit()
        return n
    finally:
        db.close()
