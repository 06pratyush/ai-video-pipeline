"""What to render, as plain data, plus the pure functions that turn it into prompts.

Both surfaces build a :class:`RenderSpec` and hand it to :mod:`app.backend.pipeline.stages`:
the CLI from a story file (:func:`story_to_spec`), the app from its database rows
(``app.backend.services.project_spec``). Nothing here touches the disk, the database, the
GPU or the network, so every decision below is testable without any of them.

The split that matters is on a scene: ``composition`` is what the keyframe *shows* and
``motion`` is what Wan *animates*. v1 had only one prompt because it was text-to-video;
v2 draws a keyframe first, so the two jobs want different words. See :func:`clip_prompt`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Mapping, Sequence

from app.backend.pipeline.comfy_client import COMFYUI_URL

# Render size per aspect ratio, and the size the finished film is scaled to.
SIZES = {"9:16": (480, 832), "16:9": (832, 480), "1:1": (640, 640)}
FINAL = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}

PAD_S = 0.35      # breath after each narration line
XFADE_S = 0.4     # dissolve between scenes
MAX_CLIP_S = 5.0  # Wan2.2 TI2V-5B is trained for clips up to about this long

# A character key becomes a filename (refs/<key>.png), so it may not become a path.
KEY_RE = re.compile(r"^[a-z0-9_-]{1,40}$")

ENGINES = ("none", "schnell", "kontext", "qwen")
TRANSITIONS = ("cut", "dissolve")


class SpecError(ValueError):
    """A story or project cannot be turned into a RenderSpec. The message is for a human."""


@dataclass(frozen=True)
class CharacterSpec:
    key: str
    description: str
    seed: int = 7


@dataclass(frozen=True)
class SceneSpec:
    index: int                       # 1-based; matches the NN in every filename
    narration: str
    composition: str                 # what the keyframe shows
    motion: str                      # what Wan animates: motion and camera, not scenery
    cast: tuple[str, ...] = ()
    keyframe_seed: int = 0
    clip_seed: int = 0
    camera: str | None = None        # free text today; a real trajectory in a later PR
    keyframe_end: str | None = None  # reserved for first-last-frame rendering
    continue_from_prev: bool = False
    transition: str = "dissolve"     # how the NEXT scene arrives: "cut" or "dissolve"


@dataclass(frozen=True)
class ClipSettings:
    """Everything the sweep harness varies. Defaults are exactly today's workflow values."""
    shift: float = 8.0
    cfg: float = 5.0
    steps: int = 20
    sampler: str = "uni_pc"
    scheduler: str = "simple"
    max_seconds: float = MAX_CLIP_S
    negative: str | None = None      # None keeps the workflow's own negative prompt


@dataclass(frozen=True)
class BackendSpec:
    """Which ComfyUI does the work. Local unless something explicitly opts out."""
    kind: str = "local"
    comfyui_url: str = COMFYUI_URL
    label: str = "This computer"


@dataclass(frozen=True)
class RenderSpec:
    title: str
    style: str
    aspect_ratio: str
    characters: Mapping[str, CharacterSpec]
    scenes: tuple[SceneSpec, ...]
    keyframe_engine: str = "none"
    clip: ClipSettings = field(default_factory=ClipSettings)
    voice: str = "af_sarah"
    voice_speed: float = 1.0
    smooth: bool = True
    upscale: bool = False
    music: str | None = None
    music_seed: int = 42
    backend: BackendSpec = field(default_factory=BackendSpec)

    def scene(self, index: int) -> SceneSpec:
        for sc in self.scenes:
            if sc.index == index:
                return sc
        raise KeyError(f"no scene {index}")

    def with_backend(self, backend: BackendSpec) -> "RenderSpec":
        return replace(self, backend=backend)


# --------------------------------------------------------------------------- sizes


def video_size(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio not in SIZES:
        raise SpecError(f"aspect_ratio must be one of {sorted(SIZES)}, not {aspect_ratio!r}")
    return SIZES[aspect_ratio]


def final_size(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio not in FINAL:
        raise SpecError(f"aspect_ratio must be one of {sorted(FINAL)}, not {aspect_ratio!r}")
    return FINAL[aspect_ratio]


# --------------------------------------------------------------------------- text


def fill(text: str, characters: Mapping[str, CharacterSpec]) -> str:
    """Replace ``{key}`` with that character's description."""
    for key, c in characters.items():
        text = text.replace("{" + key + "}", c.description)
    return text


def cast_of(scene: Mapping, characters: Mapping[str, CharacterSpec]) -> tuple[str, ...]:
    """The characters in a scene: its explicit ``cast``, else whoever it interpolates.

    Unknown names in an explicit cast are an error rather than a silent drop — a typo in a
    cast list used to mean a character quietly went missing from the keyframe.
    """
    if "cast" in scene:
        unknown = [c for c in scene["cast"] if c not in characters]
        if unknown:
            raise SpecError(f"scene cast names unknown character(s): {', '.join(unknown)}")
        return tuple(scene["cast"])
    text = f"{scene.get('prompt', '')} {scene.get('keyframe', '')} {scene.get('motion', '')}"
    return tuple(k for k in characters if "{" + k + "}" in text)


def sheet_prompt(char: CharacterSpec, style: str) -> str:
    """The character sheet: one full-body view, drawn once, reused by every scene."""
    return (f"character reference sheet, single full-body view of {char.description}, "
            f"standing, facing the camera, neutral pose, plain soft light background, {style}")


def keyframe_prompt(sc: SceneSpec, spec: RenderSpec, engine: str,
                    ref_keys: Sequence[str] = ()) -> str:
    """The still that opens a scene. With references, name each one so they stay distinct."""
    scene_text = fill(sc.composition, spec.characters)
    if not ref_keys:
        return f"{scene_text}, {spec.style}"
    if len(ref_keys) == 1:
        return (f"Place this exact character, keeping the face, hair, beard, body and clothing "
                f"identical, into a new scene: {scene_text}. Cinematic frame, {spec.style}")
    # Several characters arrive as one sheet (stitched for Kontext, side by side for Qwen).
    # Naming them by position is what stops the model blending them into one person.
    places = ("Left", "Right") if len(ref_keys) == 2 else ("Left", "Middle", "Right")
    who = ". ".join(f"{place}: {spec.characters[k].description}"
                    for place, k in zip(places, ref_keys))
    return (f"The reference image is a character sheet showing {len(ref_keys)} characters side "
            f"by side. {who}. Place all {len(ref_keys)} into one new scene, keeping each one's "
            f"face, hair, build and clothing exactly as shown, and do not blend them together. "
            f"Scene: {scene_text}. Cinematic frame, {spec.style}")


def clip_prompt(sc: SceneSpec, spec: RenderSpec, *, has_start_image: bool) -> str:
    """What Wan is told.

    With a keyframe this is image-to-video: the picture already carries the subject and the
    look, so the prompt supplies motion and camera only. Appending the style again (which v2
    inherited from v1's text-to-video path) competes with the image for control of the frame.

    Without a keyframe it really is text-to-video, and the style belongs in the prompt.
    """
    motion = fill(sc.motion, spec.characters)
    if has_start_image:
        return ", ".join(p for p in (motion, sc.camera) if p)
    return ", ".join(p for p in (motion, sc.camera, spec.style) if p)


# --------------------------------------------------------------------------- story files


def _character_specs(story: Mapping) -> dict[str, CharacterSpec]:
    raw = dict(story.get("characters") or {})
    # v1 story files carried a single top-level "noah" description.
    if "noah" in story and "noah" not in raw and isinstance(story["noah"], str):
        raw["noah"] = {"description": story["noah"]}
    out: dict[str, CharacterSpec] = {}
    for key, c in raw.items():
        if not KEY_RE.match(key):
            raise SpecError(f"character key {key!r} must match {KEY_RE.pattern}")
        description = c["description"] if isinstance(c, Mapping) else str(c)
        seed = int(c.get("seed", 7)) if isinstance(c, Mapping) else 7
        out[key] = CharacterSpec(key=key, description=description, seed=seed)
    return out


def story_to_spec(story: Mapping) -> RenderSpec:
    """Validate a story file and turn it into a RenderSpec. Raises :class:`SpecError`."""
    characters = _character_specs(story)

    engine = story.get("consistency", "none")
    if engine not in ENGINES:
        raise SpecError(f"consistency must be one of {', '.join(ENGINES)}, not {engine!r}")

    aspect = story.get("aspect_ratio", "9:16")
    video_size(aspect)  # raises on an unknown ratio before anything expensive starts

    raw_scenes = story.get("scenes") or []
    if not raw_scenes:
        raise SpecError("story has no scenes")

    scenes = []
    for i, sc in enumerate(raw_scenes, 1):
        if not sc.get("narration"):
            raise SpecError(f"scene {i} has no narration")
        if not sc.get("prompt") and not sc.get("motion"):
            raise SpecError(f"scene {i} has neither a prompt nor a motion description")
        transition = sc.get("transition", "dissolve")
        if transition not in TRANSITIONS:
            raise SpecError(f"scene {i} transition must be one of {', '.join(TRANSITIONS)}")
        scenes.append(SceneSpec(
            index=i,
            narration=sc["narration"],
            composition=sc.get("keyframe") or sc.get("prompt") or sc["motion"],
            # Stories written before the split have only "prompt"; it stays the motion source
            # so their behaviour is unchanged apart from losing the appended style suffix.
            motion=sc.get("motion") or sc["prompt"],
            cast=cast_of(sc, characters),
            keyframe_seed=int(sc.get("keyframe_seed", 2000 + i)),
            clip_seed=int(sc.get("seed", 1000 + i)),
            camera=sc.get("camera"),
            keyframe_end=sc.get("keyframe_end"),
            continue_from_prev=bool(sc.get("continue",
                                           story.get("continue_from_previous", False))),
            transition=transition,
        ))

    clip = ClipSettings(**{k: v for k, v in (story.get("clip") or {}).items()
                          if k in ClipSettings.__dataclass_fields__})
    voice = story.get("voice", "bm_george")
    return RenderSpec(
        title=story.get("title", "untitled"),
        style=story.get("style", ""),
        aspect_ratio=aspect,
        characters=characters,
        scenes=tuple(scenes),
        keyframe_engine=engine,
        clip=clip,
        voice=voice,
        voice_speed=float(story.get("voice_speed", 1.0)),
        smooth=bool(story.get("smooth", True)),
        upscale=bool(story.get("upscale", False)),
        music=story.get("music"),
        music_seed=int(story.get("music_seed", 42)),
    )
