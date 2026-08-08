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


def enqueue(project_id: str, render_opts: dict | None = None) -> str:
    """Add a project's full pipeline to the queue. Returns the queue item id."""
    import json as _json
    db: Session = SessionLocal()
    try:
        item = QueueItem(
            project_id=project_id,
            stage="full_pipeline",
            status="queued",
            render_opts=_json.dumps(render_opts or {}),
        )
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


class _Cancelled(Exception):
    """Raised inside the pipeline to unwind cleanly when the user cancels a running job."""


def _is_cancelled(queue_item_id: str) -> bool:
    """
    Check for an out-of-band cancellation using a fresh session.

    The pipeline's own session holds an open SQLite read transaction, so it would
    keep seeing its original snapshot and never observe a cancel committed by the
    request thread. A short-lived session gets a current read.
    """
    probe: Session = SessionLocal()
    try:
        row = probe.query(QueueItem).filter_by(id=queue_item_id).first()
        return row is not None and row.status == "cancelled"
    finally:
        probe.close()


def _abort_if_cancelled(queue_item_id: str):
    if _is_cancelled(queue_item_id):
        raise _Cancelled()


def recover_orphaned_items() -> int:
    """
    Re-queue jobs left in 'running' by an unclean shutdown (crash, kill, power loss).

    The worker only ever selects items with status 'queued', so without this an
    interrupted job is stranded forever: it never resumes and never reports failure.
    Returns the number of items recovered.
    """
    db: Session = SessionLocal()
    try:
        stale = db.query(QueueItem).filter_by(status="running").all()
        for item in stale:
            item.status = "queued"
            item.started_at = None
            item.progress = 0.0
            proj = db.query(Project).filter_by(id=item.project_id).first()
            if proj and proj.status == "running":
                proj.status = "queued"
        if stale:
            db.commit()
        return len(stale)
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
    import json as _json
    db: Session = SessionLocal()
    try:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            # Mark terminal before bailing out. A bare return would leave the item
            # in 'running' forever, since the worker only ever picks up 'queued'.
            item = db.query(QueueItem).filter_by(id=queue_item_id).first()
            if item:
                item.status = "error"
                item.error_message = f"Project {project_id} no longer exists"
                item.completed_at = datetime.utcnow()
                db.commit()
            return

        # Load render opts from queue item
        item_for_opts = db.query(QueueItem).filter_by(id=queue_item_id).first()
        raw_opts = item_for_opts.render_opts if item_for_opts else None
        render_opts: dict = _json.loads(raw_opts) if raw_opts else {}

        project.status = "running"
        db.commit()

        base_dir = Path("app/projects") / project_id
        audio_dir = base_dir / "audio"
        scenes_dir = base_dir / "scenes"
        final_dir = base_dir / "final"
        for d in (audio_dir, scenes_dir, final_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Projects are created with an empty script (the user writes it in the editor).
        # Fail fast and clearly, rather than feeding "" to the LLM and TTS and dying
        # several expensive minutes later with an unrelated-looking error.
        if not (project.script or "").strip():
            raise RuntimeError(
                "This project has no script yet. Add a script before generating."
            )

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

        # ── Load skill early — used across all steps ──────────────────
        skill_data = _load_skill(project.skill_id) if project.skill_id else None

        # ── Step 2: Generate video prompts ───────────────────────────
        _emit(project_id, "prompts", 0.1, "running", "Generating scene prompts...")
        skill_template = skill_data.get("prompt_template") if skill_data else None

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
        # Skill voice takes precedence; fall back to project voice, then default
        effective_voice = (
            (skill_data.get("voice") if skill_data else None)
            or project.voice
            or "af_sarah"
        )
        effective_speed = float(skill_data.get("voice_speed", 1.0)) if skill_data else 1.0
        tts = KokoroTTSClient(voice=effective_voice, speed=effective_speed)
        audio_path = str(audio_dir / "narration.wav")
        audio_path, audio_duration = tts.generate(narration, audio_path)
        project.audio_duration = audio_duration
        db.commit()

        # ── Step 3b: Generate background music (optional) ─────────────
        music_path: str | None = None
        want_music = render_opts.get("music", False)
        if not want_music and skill_data:
            # Also auto-enable if skill has a music_mood set
            want_music = bool(skill_data.get("music_mood"))
        if want_music:
            _emit(project_id, "music", 0.22, "running", "Generating background music...")
            try:
                from app.backend.pipeline.musicgen_client import generate_music, is_available
                if is_available():
                    mood = (skill_data.get("music_mood") if skill_data else None) or "ambient_score"
                    music_out = str(audio_dir / "background_music.wav")
                    music_path = generate_music(mood, audio_duration, music_out)
                else:
                    print("[QUEUE] MusicGen not available, skipping background music")
            except Exception as e:
                print(f"[QUEUE] Music generation failed (non-fatal): {e}")

        # ── Step 4: Generate video clips ─────────────────────────────
        # Unload LLM from VRAM before loading video model
        from app.backend.services import vram_manager, generation_cache
        vram_manager.prepare_for_video(llm_name)
        free_vram = vram_manager.get_free_vram_mb()

        skill_resolution = (skill_data.get("resolution", "1080p") if skill_data else "1080p")

        scenes = db.query(Scene).filter_by(project_id=project_id).order_by(Scene.index).all()
        workflow_path = "wan_workflow_api.json"
        if not Path(workflow_path).exists():
            alt = Path("app/workflows/wan_workflow_api.json")
            workflow_path = str(alt) if alt.exists() else workflow_path

        video_clips = []
        from app.backend.pipeline.wan_client import WanVideoClient
        try:
            wan = WanVideoClient(workflow_path)
        except FileNotFoundError:
            wan = None

        # Smart model routing based on free VRAM
        model_id, routing_warning = vram_manager.route_video_model("wan2.1-1.3b", free_vram)
        if routing_warning:
            _emit(project_id, f"scene_0", 0.29, "running", f"Note: {routing_warning}")

        for i, scene in enumerate(scenes):
            # Cancellation is checked per scene: scene generation is the long pole,
            # so this is the granularity at which a cancel can actually take effect.
            _abort_if_cancelled(queue_item_id)

            if scene.status == "locked" and scene.video_path and Path(scene.video_path).exists():
                video_clips.append(scene.video_path)
                continue

            prog = 0.3 + (0.4 * i / max(len(scenes), 1))

            # ── Cache check ───────────────────────────────────────────
            cache_hit = generation_cache.get(
                scene.prompt or "", scene.seed, model_id, skill_resolution
            )
            if cache_hit:
                dest = str(scenes_dir / f"scene_{i:02d}_cached.mp4")
                clip_path = generation_cache.copy_cached(cache_hit, dest)
                scene.video_path = clip_path
                scene.status = "done"
                db.commit()
                video_clips.append(clip_path)
                _emit(project_id, f"scene_{i+1}", prog, "running",
                      f"Scene {i+1}/{len(scenes)} — loaded from cache")
                continue

            _emit(project_id, f"scene_{i+1}", prog, "running",
                  f"Generating scene {i+1}/{len(scenes)}...")
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
                # Store in cache for future runs
                generation_cache.put(
                    scene.prompt or "", scene.seed, model_id, skill_resolution, clip_path
                )
            except Exception as e:
                scene.status = "error"
                scene.error_message = str(e)
                db.commit()
                print(f"[QUEUE] Scene {i+1} failed: {e}")

        # ── Step 5: Merge clips ───────────────────────────────────────
        _abort_if_cancelled(queue_item_id)

        if not video_clips:
            raise RuntimeError("No video clips generated")

        _emit(project_id, "merging", 0.72, "running", "Merging clips...")
        from app.backend.pipeline.ffmpeg_merger import (
            concatenate_clips, merge_video_audio, merge_with_background_music,
            convert_aspect_ratio, apply_post_processing_chain, add_subtitles,
        )
        import shutil

        if len(video_clips) > 1:
            concat_path = str(scenes_dir / "concat.mp4")
            source_video = concatenate_clips(video_clips, concat_path)
        else:
            source_video = video_clips[0]

        # ── Step 5b: Frame interpolation (optional) ───────────────────
        want_interp = render_opts.get("interpolation", False)
        if want_interp:
            _emit(project_id, "interpolating", 0.76, "running", "Interpolating to 30fps...")
            try:
                from app.backend.pipeline.rife_client import interpolate_to_fps
                interp_path = str(scenes_dir / "interpolated.mp4")
                source_video = interpolate_to_fps(source_video, interp_path, 30)
            except Exception as e:
                print(f"[QUEUE] Interpolation failed (non-fatal): {e}")

        # ── Step 5c: Merge video + audio (with optional music) ────────
        _emit(project_id, "merging", 0.79, "running", "Merging audio...")
        merged_path = str(final_dir / "merged.mp4")
        if music_path and Path(music_path).exists():
            merge_with_background_music(source_video, audio_path, music_path, merged_path, audio_duration)
        else:
            merge_video_audio(source_video, audio_path, merged_path, audio_duration)

        # ── Step 5d: Upscaling (optional) ─────────────────────────────
        want_upscale = render_opts.get("upscaling", False)
        if want_upscale:
            _emit(project_id, "upscaling", 0.82, "running", "Upscaling to 1080p...")
            try:
                from app.backend.pipeline.esrgan_client import upscale_2x
                upscaled_path = str(final_dir / "upscaled.mp4")
                merged_path = upscale_2x(merged_path, upscaled_path)
            except Exception as e:
                print(f"[QUEUE] Upscaling failed (non-fatal): {e}")

        # ── Step 5e: Aspect ratio + resolution ────────────────────────
        aspect = skill_data.get("aspect_ratio", "16:9") if skill_data else "16:9"
        resolution = skill_data.get("resolution", "1080p") if skill_data else "1080p"
        aspect_path = str(final_dir / "aspect.mp4")
        convert_aspect_ratio(merged_path, aspect_path, aspect, resolution)

        # ── Step 5f: Post-processing chain (color grade, etc.) ────────
        post_effects: list[str] = skill_data.get("post_processing", []) if skill_data else []
        pp_path = str(final_dir / "postprocessed.mp4")
        if post_effects:
            _emit(project_id, "post_processing", 0.88, "running", "Applying post-processing...")
            apply_post_processing_chain(aspect_path, pp_path, post_effects)
        else:
            shutil.copy2(aspect_path, pp_path)

        # ── Step 5g: Subtitles (optional) ─────────────────────────────
        want_subtitles = render_opts.get("subtitles", False)
        if not want_subtitles and skill_data:
            want_subtitles = skill_data.get("subtitles", False)

        final_path = str(final_dir / "final.mp4")
        if want_subtitles:
            _emit(project_id, "subtitles", 0.93, "running", "Generating subtitles...")
            try:
                from app.backend.pipeline.whisper_client import transcribe_to_srt_file, is_available
                if is_available():
                    srt_path = str(audio_dir / "subtitles.srt")
                    transcribe_to_srt_file(audio_path, srt_path)
                    add_subtitles(pp_path, srt_path, final_path)
                else:
                    print("[QUEUE] faster-whisper not available, skipping subtitles")
                    shutil.copy2(pp_path, final_path)
            except Exception as e:
                print(f"[QUEUE] Subtitle generation failed (non-fatal): {e}")
                shutil.copy2(pp_path, final_path)
        else:
            shutil.copy2(pp_path, final_path)

        # Re-check before writing the terminal state: a cancel landing during the
        # merge/post-process stage would otherwise be silently overwritten by 'done'.
        _abort_if_cancelled(queue_item_id)

        project.final_path = final_path
        project.status = "done"

        item = db.query(QueueItem).filter_by(id=queue_item_id).first()
        if item:
            item.status = "done"
            item.completed_at = datetime.utcnow()
            item.progress = 1.0
        db.commit()

        # ── Auto-snapshot version on successful render ────────────────
        try:
            from app.backend.models.project_version import ProjectVersion
            from pathlib import Path as _Path
            import shutil as _shutil, uuid as _uuid

            next_num = db.query(ProjectVersion).filter_by(project_id=project_id).count() + 1
            archived_path = None
            if _Path(final_path).exists():
                version_dir = _Path(f"app/projects/{project_id}/versions/v{next_num}")
                version_dir.mkdir(parents=True, exist_ok=True)
                archived = version_dir / "final.mp4"
                _shutil.copy2(final_path, archived)
                archived_path = str(archived)

            snap_scenes = db.query(Scene).filter_by(project_id=project_id).order_by(Scene.index).all()
            snapshot = {
                "name":         project.name,
                "topic":        project.topic,
                "script":       project.script,
                "narration":    project.narration,
                "skill_id":     project.skill_id,
                "voice":        project.voice,
                "num_scenes":   project.num_scenes,
                "audio_duration": project.audio_duration,
                "render_opts":  render_opts,
                "scenes": [
                    {"index": s.index, "prompt": s.prompt, "seed": s.seed, "status": s.status}
                    for s in snap_scenes
                ],
            }
            v = ProjectVersion(
                id=str(_uuid.uuid4()),
                project_id=project_id,
                version_num=next_num,
                label=f"Auto v{next_num}",
                snapshot=_json.dumps(snapshot),
                final_path=archived_path,
                duration=int(project.audio_duration) if project.audio_duration else None,
            )
            db.add(v)
            db.commit()
        except Exception as e:
            print(f"[QUEUE] Auto-snapshot failed (non-fatal): {e}")

        _emit(project_id, "done", 1.0, "done", "Generation complete!")

    except _Cancelled:
        # User-initiated stop — a terminal state, not a failure.
        db.rollback()
        project = db.query(Project).filter_by(id=project_id).first()
        if project:
            project.status = "cancelled"
        item = db.query(QueueItem).filter_by(id=queue_item_id).first()
        if item:
            item.status = "cancelled"
            item.completed_at = datetime.utcnow()
        db.commit()
        _emit(project_id, "cancelled", 0.0, "cancelled", "Generation cancelled")
        print(f"[QUEUE] Pipeline cancelled for {project_id}")

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
            item.completed_at = datetime.utcnow()  # terminal states must be timestamped
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
