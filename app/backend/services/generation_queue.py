"""
Generation queue — runs pipeline jobs sequentially on a background thread.
Uses SQLite for persistence so jobs survive app restarts.
"""
import asyncio
import threading
import time
import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.backend.db import SessionLocal
from app.backend.models.project import Project
from app.backend.models.scene import Scene
from app.backend.models.queue_item import QueueItem
from app.backend.services import model_registry

# WebSocket broadcast hook — set by main.py at startup
broadcast_progress: Callable | None = None


def _emit(project_id: str, stage: str, progress: float, status: str, message: str = ""):
    if broadcast_progress:
        asyncio.run_coroutine_threadsafe(
            broadcast_progress(project_id, stage, progress, status, message),
            _event_loop,
        )


_event_loop: asyncio.AbstractEventLoop | None = None
_worker_thread: threading.Thread | None = None
_running = False


def set_event_loop(loop: asyncio.AbstractEventLoop):
    global _event_loop
    _event_loop = loop


def start_worker():
    global _worker_thread, _running
    _running = True
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()


def stop_worker():
    global _running
    _running = False


def enqueue(project_id: str) -> str:
    """Add a project's full pipeline to the queue. Returns the queue item id."""
    db: Session = SessionLocal()
    try:
        item = QueueItem(project_id=project_id, stage="full_pipeline", status="queued")
        db.add(item)
        db.commit()
        db.refresh(item)
        return item.id
    finally:
        db.close()


def cancel(queue_item_id: str):
    db: Session = SessionLocal()
    try:
        item = db.query(QueueItem).filter_by(id=queue_item_id).first()
        if item and item.status in ("queued", "running"):
            item.status = "cancelled"
            db.commit()
    finally:
        db.close()


def _worker_loop():
    while _running:
        db: Session = SessionLocal()
        try:
            item = (
                db.query(QueueItem)
                .filter_by(status="queued")
                .order_by(QueueItem.created_at)
                .first()
            )
            if item:
                item.status = "running"
                item.started_at = datetime.utcnow()
                db.commit()
                _run_pipeline(item.id, item.project_id)
            else:
                time.sleep(2)
        except Exception as e:
            print(f"[QUEUE] Worker error: {e}")
            time.sleep(5)
        finally:
            db.close()


def _run_pipeline(queue_item_id: str, project_id: str):
    db: Session = SessionLocal()
    try:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            return

        project.status = "running"
        db.commit()

        base_dir = Path("app/projects") / project_id
        audio_dir = base_dir / "audio"
        scenes_dir = base_dir / "scenes"
        final_dir = base_dir / "final"
        for d in (audio_dir, scenes_dir, final_dir):
            d.mkdir(parents=True, exist_ok=True)

        # ── Step 1: Refine narration ──────────────────────────────────
        _emit(project_id, "refining", 0.05, "running", "Refining narration with Gemma...")
        from app.backend.pipeline.gemma_client import GemmaClient
        llm_name = model_registry.get_active_llm() or "gemma4:e4b"
        gemma = GemmaClient(model=llm_name)

        narration = project.script
        try:
            narration = gemma.refine_narration(project.script)
            project.narration = narration
            db.commit()
        except Exception as e:
            print(f"[QUEUE] Gemma refine failed: {e}, using raw script")
            narration = project.script

        # ── Step 2: Generate video prompts ───────────────────────────
        _emit(project_id, "prompts", 0.1, "running", "Generating scene prompts...")
        skill_template = None
        if project.skill_id:
            skill_data = _load_skill(project.skill_id)
            if skill_data:
                skill_template = skill_data.get("prompt_template")

        prompts = gemma.generate_video_prompts(narration, project.num_scenes, skill_template)

        # Persist scene records
        for i, p in enumerate(prompts):
            existing = db.query(Scene).filter_by(project_id=project_id, index=i).first()
            if existing:
                if existing.status != "locked":
                    existing.prompt = p
                    existing.status = "pending"
            else:
                db.add(Scene(project_id=project_id, index=i, prompt=p))
        db.commit()

        # ── Step 3: Generate audio ────────────────────────────────────
        _emit(project_id, "audio", 0.2, "running", "Generating voice audio...")
        from app.backend.pipeline.kokoro_tts import KokoroTTSClient
        tts = KokoroTTSClient(voice=project.voice)
        audio_path = str(audio_dir / "narration.wav")
        audio_path, audio_duration = tts.generate(narration, audio_path)
        project.audio_duration = audio_duration
        db.commit()

        # ── Step 4: Generate video clips ─────────────────────────────
        scenes = db.query(Scene).filter_by(project_id=project_id).order_by(Scene.index).all()
        workflow_path = "wan_workflow_api.json"
        if not Path(workflow_path).exists():
            # Try app/workflows/
            alt = Path("app/workflows/wan_workflow_api.json")
            workflow_path = str(alt) if alt.exists() else workflow_path

        video_clips = []
        from app.backend.pipeline.wan_client import WanVideoClient
        try:
            wan = WanVideoClient(workflow_path)
        except FileNotFoundError:
            wan = None

        for i, scene in enumerate(scenes):
            if scene.status == "locked" and scene.video_path and Path(scene.video_path).exists():
                video_clips.append(scene.video_path)
                continue
            prog = 0.3 + (0.4 * i / max(len(scenes), 1))
            _emit(project_id, f"scene_{i+1}", prog, "running", f"Generating scene {i+1}/{len(scenes)}...")
            if wan is None:
                scene.status = "error"
                scene.error_message = "ComfyUI workflow not found"
                db.commit()
                continue
            try:
                clip_path = wan.generate(
                    prompt=scene.prompt or "",
                    output_dir=str(scenes_dir),
                    seed=scene.seed,
                )
                scene.video_path = clip_path
                scene.status = "done"
                db.commit()
                video_clips.append(clip_path)
            except Exception as e:
                scene.status = "error"
                scene.error_message = str(e)
                db.commit()
                print(f"[QUEUE] Scene {i+1} failed: {e}")

        # ── Step 5: Merge ─────────────────────────────────────────────
        if not video_clips:
            raise RuntimeError("No video clips generated")

        _emit(project_id, "merging", 0.75, "running", "Merging clips and audio...")
        from app.backend.pipeline.ffmpeg_merger import (
            concatenate_clips, merge_video_audio, convert_aspect_ratio
        )

        if len(video_clips) > 1:
            concat_path = str(scenes_dir / "concat.mp4")
            source_video = concatenate_clips(video_clips, concat_path)
        else:
            source_video = video_clips[0]

        merged_path = str(final_dir / "merged.mp4")
        merge_video_audio(source_video, audio_path, merged_path, audio_duration)

        # Apply aspect ratio / resolution if skill specifies
        skill_data = _load_skill(project.skill_id) if project.skill_id else None
        aspect = skill_data.get("aspect_ratio", "16:9") if skill_data else "16:9"
        resolution = skill_data.get("resolution", "1080p") if skill_data else "1080p"
        final_path = str(final_dir / "final.mp4")
        convert_aspect_ratio(merged_path, final_path, aspect, resolution)

        project.final_path = final_path
        project.status = "done"

        item = db.query(QueueItem).filter_by(id=queue_item_id).first()
        if item:
            item.status = "done"
            item.completed_at = datetime.utcnow()
            item.progress = 1.0
        db.commit()

        _emit(project_id, "done", 1.0, "done", "Generation complete!")

    except Exception as e:
        db.rollback()
        project = db.query(Project).filter_by(id=project_id).first()
        if project:
            project.status = "error"
            db.commit()
        item = db.query(QueueItem).filter_by(id=queue_item_id).first()
        if item:
            item.status = "error"
            item.error_message = str(e)
            db.commit()
        _emit(project_id, "error", 0.0, "error", str(e))
        print(f"[QUEUE] Pipeline failed for {project_id}: {e}")
    finally:
        db.close()


def _load_skill(skill_id: str) -> dict | None:
    skill_file = Path("app/skills") / f"{skill_id}.json"
    if skill_file.exists():
        import json
        with open(skill_file) as f:
            return json.load(f)
    return None
