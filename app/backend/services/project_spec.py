"""Turn a project's database rows into a RenderSpec the shared stages understand.

This lives in ``services`` rather than ``pipeline`` because it reads the ORM models, and
``pipeline`` must stay free of them (CONTEXT RULE-02). It is the app's counterpart to
``render_story.load_story`` -> ``render_spec.story_to_spec``.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from app.backend.models.project import Project
from app.backend.models.scene import Scene
from app.backend.pipeline import image_client, render_spec
from app.backend.pipeline.render_spec import (
    BackendSpec, CharacterSpec, ClipSettings, RenderSpec, SceneSpec,
)

# A skill's scene_pacing, which until now was declared in every skill and read by nothing.
PACING_SECONDS = {"slow": 5.0, "medium": 3.5, "fast": 2.5}


def _json_or(value: Any, default):
    if not value:
        return default
    try:
        return json.loads(value) if isinstance(value, (str, bytes)) else value
    except ValueError:
        return default


def characters_of(project: Project) -> dict[str, CharacterSpec]:
    """Recurring characters declared on the project, if any. Bad keys are dropped, not fatal.

    A render must not die because someone typed an odd character name in the UI; the cost of
    dropping one is a scene drawn without its reference, which is what happens today anyway.
    """
    out: dict[str, CharacterSpec] = {}
    for key, c in (_json_or(project.characters, {}) or {}).items():
        if not render_spec.KEY_RE.match(str(key)):
            continue
        description = c.get("description") if isinstance(c, Mapping) else str(c)
        if not description:
            continue
        seed = int(c.get("seed", 7)) if isinstance(c, Mapping) else 7
        out[str(key)] = CharacterSpec(key=str(key), description=description, seed=seed)
    return out


def scene_specs(scenes: Sequence[Scene], characters: Mapping[str, CharacterSpec]
                ) -> tuple[SceneSpec, ...]:
    out = []
    for i, s in enumerate(scenes, 1):
        composition = s.prompt or s.motion_prompt or ""
        motion = s.motion_prompt or s.prompt or ""
        cast = tuple(k for k in _json_or(s.cast, []) if k in characters)
        if not cast:
            cast = tuple(k for k in characters if "{" + k + "}" in f"{composition} {motion}")
        seed = int(s.seed) if s.seed is not None else 1000 + i
        out.append(SceneSpec(
            index=i,
            narration="",            # the app narrates the whole script, not line by line
            composition=composition,
            motion=motion,
            cast=cast,
            keyframe_seed=seed + 2000,
            clip_seed=seed,
        ))
    return tuple(out)


def spec_from_project(project: Project, scenes: Sequence[Scene], skill: Mapping | None,
                      render_opts: Mapping | None = None,
                      *, free_vram_mb: int | None = None,
                      backend: BackendSpec | None = None) -> RenderSpec:
    """Build the RenderSpec for one app render."""
    skill = dict(skill or {})
    opts = dict(render_opts or {})
    characters = characters_of(project)

    requested = opts.get("consistency")
    engine = image_client.resolve_engine(requested, budget_mb=free_vram_mb)
    # Reference-based engines have nothing to reference without declared characters, and
    # pointing them at another scene's keyframe is what used to bleed whole compositions
    # from scene to scene. Without characters, draw every scene independently.
    if not characters and image_client.MAX_REFS.get(engine, 0) > 0:
        engine = image_client.resolve_engine("schnell", budget_mb=free_vram_mb)

    pacing = PACING_SECONDS.get(str(skill.get("scene_pacing", "")).lower(),
                                render_spec.MAX_CLIP_S)
    aspect = skill.get("aspect_ratio", "16:9")
    if aspect not in render_spec.SIZES:
        aspect = "16:9"

    return RenderSpec(
        title=project.name or "untitled",
        style=skill.get("style_suffix", "") or "",
        aspect_ratio=aspect,
        characters=characters,
        scenes=scene_specs(scenes, characters),
        keyframe_engine=engine,
        clip=ClipSettings(max_seconds=pacing),
        voice=(skill.get("voice") or project.voice or "af_sarah"),
        voice_speed=float(skill.get("voice_speed", 1.0) or 1.0),
        smooth=bool(opts.get("interpolation", True)),
        upscale=bool(opts.get("upscaling", False)),
        music=skill.get("music_mood") if opts.get("music") else None,
        backend=backend or BackendSpec(),
    )
