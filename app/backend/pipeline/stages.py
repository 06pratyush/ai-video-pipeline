"""The render stages both surfaces share: character sheets, keyframes, clips, smoothing.

The CLI resumes by looking at files on disk; the app resumes from its database and reports
progress over a WebSocket. Neither model belongs in here, so this module knows only two
things: a :class:`Workspace` (where files go) and :class:`Hooks` (what to call as work
happens). Everything else arrives as a :class:`~app.backend.pipeline.render_spec.RenderSpec`.

Resumability is by file existence, as it has always been, plus a small JSON sidecar beside
each keyframe recording what it was made from. Bare existence is not enough once a scene's
cast can change: adding a second character to a scene must redraw its keyframe, and without
the sidecar the old one-character picture would be silently reused.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Collection, Mapping, Sequence

from app.backend.pipeline import ffmpeg_tools, image_client, render_spec
from app.backend.pipeline.render_spec import PAD_S, RenderSpec, SceneSpec, XFADE_S


class Cancelled(Exception):
    """Raised inside a stage when the caller's ``cancelled`` hook says to stop."""


@dataclass(frozen=True)
class Workspace:
    """Where a render's files live. The same layout for both surfaces."""
    root: Path

    def __post_init__(self):
        object.__setattr__(self, "root", Path(self.root))

    def sheet(self, key: str) -> Path:
        return self.root / "refs" / f"{key}.png"

    def stitch(self, keys: Sequence[str]) -> Path:
        return self.root / "refs" / ("_sheet_" + "+".join(keys) + ".png")

    def keyframe(self, i: int) -> Path:
        return self.root / "keyframes" / f"{i:02d}.png"

    def keyframe_meta(self, i: int) -> Path:
        return self.root / "keyframes" / f"{i:02d}.json"

    def clip(self, i: int) -> Path:
        return self.root / "clips" / f"{i:02d}.mp4"

    def clip_raw(self) -> Path:
        return self.root / "clips" / "raw"

    def smooth(self, i: int) -> Path:
        return self.root / "smooth" / f"{i:02d}.mp4"

    def audio(self, i: int) -> Path:
        return self.root / "audio" / f"{i:02d}.wav"

    def mkdirs(self) -> None:
        for d in ("audio", "refs", "keyframes", "clips", "smooth"):
            (self.root / d).mkdir(parents=True, exist_ok=True)


@dataclass
class Hooks:
    """Callbacks a surface supplies. Every one defaults to doing nothing."""
    log: Callable[[str], None] = lambda message: None
    progress: Callable[[str, float, str], None] = lambda stage, fraction, message: None
    cancelled: Callable[[], bool] = lambda: False
    on_artifact: Callable[[str, int, Path], None] = lambda kind, index, path: None

    def check(self) -> None:
        if self.cancelled():
            raise Cancelled()


_HOOKS = Hooks()


# --------------------------------------------------------------------------- helpers


def wanted(index: int, dest: Path, only: Collection[int] | None) -> bool:
    """Render this one? With ``only``, exactly those (redone); otherwise the missing ones."""
    return (index in only) if only else not dest.exists()


def connect(spec: RenderSpec):
    """Make sure a ComfyUI is reachable and hand back a client with the GPU to itself."""
    from app.backend.pipeline.comfy_client import ComfyClient
    if spec.backend.kind == "local":
        from app.backend.services import comfyui_manager
        if not comfyui_manager.start():
            raise RuntimeError("ComfyUI did not start (see app/runtime/comfyui/comfyui.log)")
    client = ComfyClient(spec.backend.comfyui_url)
    client.free()  # each stage starts with the whole GPU
    return client


def _fingerprint(engine: str, prompt: str, seed: int, size: tuple[int, int],
                 refs: Sequence[Path]) -> dict:
    return {
        "engine": engine,
        "prompt": prompt,
        "seed": seed,
        "size": list(size),
        "refs": [{"name": Path(r).name,
                  "mtime": round(Path(r).stat().st_mtime, 3) if Path(r).exists() else None}
                 for r in refs],
    }


def _is_stale(meta_path: Path, fingerprint: dict) -> bool:
    """True when the recorded inputs differ from what the spec now asks for."""
    try:
        return json.loads(meta_path.read_text(encoding="utf-8")) != fingerprint
    except (OSError, ValueError):
        return True  # no sidecar (or an unreadable one) means we cannot vouch for the file


def reference_keys(spec: RenderSpec, scene: SceneSpec, engine: str) -> tuple[str, ...]:
    """Which characters' sheets go into this scene's keyframe, in order."""
    if image_client.MAX_REFS.get(engine, 0) < 1:
        return ()
    return tuple(k for k in scene.cast if k in spec.characters)


# --------------------------------------------------------------------------- stages


def ensure_sheets(spec: RenderSpec, ws: Workspace, hooks: Hooks = _HOOKS,
                  *, only: Collection[str] | None = None) -> dict[str, Path]:
    """Draw each character once. Only engines that take a reference need these."""
    engine = spec.keyframe_engine
    if image_client.MAX_REFS.get(engine, 0) < 1 or not spec.characters:
        return {}
    ws.mkdirs()
    out: dict[str, Path] = {}
    client = None
    for key, char in spec.characters.items():
        dest = ws.sheet(key)
        out[key] = dest
        if dest.exists() and not (only and key in only):
            continue
        hooks.check()
        if client is None:
            connect(spec)
            client = image_client.ImageClient("schnell", spec.backend.comfyui_url)
        hooks.progress("refs", 0.0, f"Drawing the character sheet for {key}...")
        client.generate(render_spec.sheet_prompt(char, spec.style), dest, 768, 1344,
                        seed=char.seed)
        hooks.log(f"  ref {key}: {dest.name}")
        hooks.on_artifact("sheet", 0, dest)
    return out


def _sheet_for_scene(spec: RenderSpec, ws: Workspace, keys: Sequence[str],
                     sheets: Mapping[str, Path], hooks: Hooks) -> Path | None:
    """One reference image for a scene: a character's sheet, or several stitched together."""
    paths = [sheets[k] for k in keys if k in sheets and sheets[k].exists()]
    if not paths:
        return None
    if len(paths) == 1:
        return paths[0]
    dest = ws.stitch(list(keys)[:3])
    if not dest.exists():
        hooks.log(f"  sheet {'+'.join(keys)}: stitching {len(paths)} characters")
        ffmpeg_tools.stitch_horizontal(paths[:3], dest)
    return dest


def ensure_keyframes(spec: RenderSpec, ws: Workspace, hooks: Hooks = _HOOKS, *,
                     sheets: Mapping[str, Path] | None = None,
                     only: Collection[int] | None = None) -> dict[int, Path]:
    """Draw each scene's opening still. This is what Wan animates."""
    engine = spec.keyframe_engine
    if engine == "none":
        return {}
    ws.mkdirs()
    sheets = dict(sheets or {})
    if engine in image_client.NON_COMMERCIAL:
        hooks.log(f"  NOTE: the {engine} keyframe model is licensed for non-commercial use only.")
    width, height = image_client.keyframe_size(*render_spec.video_size(spec.aspect_ratio))
    clients: dict[str, image_client.ImageClient] = {}
    started = False
    out: dict[int, Path] = {}

    for sc in spec.scenes:
        dest, meta = ws.keyframe(sc.index), ws.keyframe_meta(sc.index)
        keys = reference_keys(spec, sc, engine)
        reference = _sheet_for_scene(spec, ws, keys, sheets, hooks) if keys else None
        use = engine if reference else "schnell"
        prompt = render_spec.keyframe_prompt(sc, spec, use, keys if reference else ())
        fingerprint = _fingerprint(use, prompt, sc.keyframe_seed, (width, height),
                                   [reference] if reference else [])

        # With `only`, exactly those scenes are redone and every other one is left alone,
        # even if it is missing. Without it, a scene is redrawn when its file is absent or
        # when the sidecar says it was made from different inputs.
        if only:
            if sc.index not in only:
                if dest.exists():
                    out[sc.index] = dest
                continue
        elif dest.exists() and not _is_stale(meta, fingerprint):
            out[sc.index] = dest
            continue
        hooks.check()
        if not started:
            connect(spec)
            started = True
        client = clients.get(use)
        if client is None:
            client = clients[use] = image_client.ImageClient(use, spec.backend.comfyui_url)
        hooks.progress("keyframes", (sc.index - 1) / max(len(spec.scenes), 1),
                       f"Drawing keyframe {sc.index}/{len(spec.scenes)}...")
        client.generate(prompt, dest, width, height, seed=sc.keyframe_seed,
                        references=[reference] if reference else None)
        meta.write_text(json.dumps(fingerprint, indent=1), encoding="utf-8")
        hooks.log(f"  keyframe {sc.index:02d} ({use}"
                  f"{', ' + '+'.join(keys) if reference else ''})")
        hooks.on_artifact("keyframe", sc.index, dest)
        out[sc.index] = dest
    return out


def ensure_clips(spec: RenderSpec, ws: Workspace, hooks: Hooks = _HOOKS, *,
                 keyframes: Mapping[int, Path] | None = None,
                 durations: Sequence[float] | None = None,
                 only: Collection[int] | None = None) -> dict[int, Path]:
    """Animate each keyframe into a clip just long enough for its narration line."""
    from app.backend.pipeline.wan_client import WanVideoClient, frames_for_seconds
    ws.mkdirs()
    keyframes = dict(keyframes or {})
    width, height = render_spec.video_size(spec.aspect_ratio)
    wan = None
    out: dict[int, Path] = {}

    for sc in spec.scenes:
        dest = ws.clip(sc.index)
        if not wanted(sc.index, dest, only):
            out[sc.index] = dest
            continue
        hooks.check()
        if wan is None:
            connect(spec)
            wan = WanVideoClient(comfyui_url=spec.backend.comfyui_url)

        start: Path | None = None
        if sc.continue_from_prev and sc.index > 1 and ws.clip(sc.index - 1).exists():
            start = ffmpeg_tools.last_frame(ws.clip(sc.index - 1),
                                            ws.root / "keyframes" / f"{sc.index:02d}_from_prev.png")
        if start is None:
            candidate = keyframes.get(sc.index) or ws.keyframe(sc.index)
            start = candidate if Path(candidate).exists() else None

        line = durations[sc.index - 1] if durations and len(durations) >= sc.index else 3.0
        seconds = min(line + PAD_S + XFADE_S, spec.clip.max_seconds)
        frames = frames_for_seconds(seconds)
        prompt = render_spec.clip_prompt(sc, spec, has_start_image=start is not None)

        hooks.progress("clips", (sc.index - 1) / max(len(spec.scenes), 1),
                       f"Generating scene {sc.index}/{len(spec.scenes)}...")
        path = wan.generate(prompt=prompt, output_dir=str(ws.clip_raw()), width=width,
                            height=height, num_frames=frames, steps=spec.clip.steps,
                            seed=sc.clip_seed, start_image=str(start) if start else None)
        Path(path).replace(dest)
        ws.smooth(sc.index).unlink(missing_ok=True)  # stale the moment the clip changes
        hooks.log(f"  clip {sc.index:02d}: {frames} frames"
                  f"{' from keyframe' if start else ' from text'}")
        hooks.on_artifact("clip", sc.index, dest)
        out[sc.index] = dest
    return out


def ensure_smooth(spec: RenderSpec, ws: Workspace, hooks: Hooks = _HOOKS,
                  *, only: Collection[int] | None = None) -> dict[int, Path]:
    """RIFE each clip to 48 fps, optionally sharpening with Real-ESRGAN on the way."""
    if not spec.smooth:
        return {}
    from app.backend.pipeline.smooth_client import SmoothClient
    ws.mkdirs()
    smoother = None
    out: dict[int, Path] = {}
    for sc in spec.scenes:
        src, dest = ws.clip(sc.index), ws.smooth(sc.index)
        if not src.exists():
            continue
        if not wanted(sc.index, dest, only):
            out[sc.index] = dest
            continue
        hooks.check()
        if smoother is None:
            connect(spec)
            smoother = SmoothClient(spec.backend.comfyui_url)
        hooks.progress("smooth", (sc.index - 1) / max(len(spec.scenes), 1),
                       f"Smoothing clip {sc.index}/{len(spec.scenes)} to 48 fps...")
        smoother.smooth(src, dest, src_fps=24.0, upscale=spec.upscale)
        hooks.log(f"  smooth {sc.index:02d}: 48 fps{' + ESRGAN x2' if spec.upscale else ''}")
        hooks.on_artifact("smooth", sc.index, dest)
        out[sc.index] = dest
    return out
