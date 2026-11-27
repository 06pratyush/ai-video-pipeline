"""Tests for the render path the CLI and the desktop app now share.

    venv311\\Scripts\\python.exe app\\backend\\tests\\test_shared_render.py

Same shape as test_v2_pipeline.py: plain functions, bare asserts, no pytest needed. No
GPU, no ComfyUI, no models — the image client is replaced by a stub that writes a file.
"""
import ast
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
# A throwaway database, set before anything imports app.backend.db.
os.environ.setdefault("AIVS_DB_PATH", str(Path(tempfile.mkdtemp()) / "shared.db"))

from app.backend.pipeline import render_spec as RS  # noqa: E402
from app.backend.pipeline import stages as ST  # noqa: E402

SAMPLE = ROOT / "stories" / "noahs_ark.json"


# ----------------------------------------------------------------------------- helpers


class _FakeImage:
    """Stands in for ImageClient: records the call and writes a byte to the destination."""
    calls: list[dict] = []

    def __init__(self, mode="schnell", comfyui_url=None, session=None):
        self.mode = mode

    def generate(self, prompt, dest, width=768, height=1344, seed=0, steps=None,
                 references=None, timeout_s=0):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x89PNG")
        refs = references if isinstance(references, (list, tuple)) else (
            [references] if references else [])
        _FakeImage.calls.append({"mode": self.mode, "prompt": prompt, "dest": dest,
                                 "seed": seed, "refs": [str(r) for r in refs]})
        return dest


@contextmanager
def _no_gpu(stitch=True):
    """Swap out everything that would need ComfyUI or ffmpeg."""
    real_client = ST.image_client.ImageClient
    real_comfy = ST.connect
    real_stitch = ST.ffmpeg_tools.stitch_horizontal
    ST.image_client.ImageClient = _FakeImage
    ST.connect = lambda spec: None
    if stitch:
        def _fake_stitch(sources, dest, height=0):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b"\x89PNG")
            return Path(dest)
        ST.ffmpeg_tools.stitch_horizontal = _fake_stitch
    _FakeImage.calls = []
    try:
        yield _FakeImage.calls
    finally:
        ST.image_client.ImageClient = real_client
        ST.connect = real_comfy
        ST.ffmpeg_tools.stitch_horizontal = real_stitch


def _story(**over):
    story = {
        "style": "pixar style",
        "aspect_ratio": "9:16",
        "consistency": "kontext",
        "characters": {"ann": {"description": "ANN THE SAILOR", "seed": 1},
                       "boat": {"description": "BOAT THE VESSEL", "seed": 2}},
        "scenes": [
            {"narration": "one", "prompt": "{ann} on a dock", "motion": "she waves, slow push-in",
             "cast": ["ann"]},
            {"narration": "two", "prompt": "{ann} beside {boat}", "motion": "the sail lifts",
             "cast": ["ann", "boat"]},
        ],
    }
    story.update(over)
    return story


def _ws():
    ws = ST.Workspace(Path(tempfile.mkdtemp()))
    ws.mkdirs()
    return ws


_db_ready = False


def _models():
    """Register every ORM class. Project alone cannot map: it relates to three others."""
    global _db_ready
    if not _db_ready:
        from app.backend.db import init_db
        init_db()
        _db_ready = True
    from app.backend.models.project import Project
    from app.backend.models.scene import Scene
    return Project, Scene


# ----------------------------------------------------------------------------- prompts


def test_clip_prompt_drops_style_when_a_keyframe_leads():
    """Wan image-to-video takes motion and camera; the still already carries the style."""
    spec = RS.story_to_spec(_story())
    sc = spec.scene(1)
    with_key = RS.clip_prompt(sc, spec, has_start_image=True)
    without = RS.clip_prompt(sc, spec, has_start_image=False)
    assert "she waves" in with_key and "she waves" in without
    assert spec.style not in with_key, with_key
    # With no keyframe it really is text-to-video, so the style still belongs in the prompt.
    assert spec.style in without, without


def test_clip_prompt_fills_characters_and_leaves_no_placeholder():
    story = _story()
    story["scenes"][0]["motion"] = "{ann} waves, slow push-in"
    spec = RS.story_to_spec(story)
    out = RS.clip_prompt(spec.scene(1), spec, has_start_image=True)
    assert "{" not in out and "ANN THE SAILOR" in out


def test_keyframe_prompt_names_each_reference_by_position():
    spec = RS.story_to_spec(_story())
    one = RS.keyframe_prompt(spec.scene(1), spec, "kontext", ("ann",))
    two = RS.keyframe_prompt(spec.scene(2), spec, "kontext", ("ann", "boat"))
    assert "this exact character" in one
    assert "Left: ANN THE SAILOR" in two and "Right: BOAT THE VESSEL" in two
    assert "do not blend them together" in two


# ----------------------------------------------------------------------------- stages


def test_keyframe_uses_every_cast_member():
    """A two-character scene must reference both. Passing only cast[0] was the bug."""
    spec = RS.story_to_spec(_story())
    ws = _ws()
    with _no_gpu() as calls:
        sheets = ST.ensure_sheets(spec, ws)
        ST.ensure_keyframes(spec, ws, sheets=sheets)
    assert set(sheets) == {"ann", "boat"}, sheets
    keyframes = [c for c in calls if c["dest"].parent.name == "keyframes"]
    assert len(keyframes) == 2
    # Scene 2 has two characters; both descriptions must reach the prompt.
    assert "ANN THE SAILOR" in keyframes[1]["prompt"]
    assert "BOAT THE VESSEL" in keyframes[1]["prompt"], keyframes[1]["prompt"]
    # Kontext conditions on one image, so the two sheets arrive stitched into one.
    assert len(keyframes[1]["refs"]) == 1
    assert "ann+boat" in keyframes[1]["refs"][0]


def test_keyframes_only_ever_reference_character_sheets():
    """Never another scene's keyframe: that bled whole compositions between shots."""
    spec = RS.story_to_spec(_story())
    ws = _ws()
    with _no_gpu() as calls:
        ST.ensure_keyframes(spec, ws, sheets=ST.ensure_sheets(spec, ws))
    for call in calls:
        for ref in call["refs"]:
            assert Path(ref).parent.name == "refs", f"keyframe referenced {ref}"
    # And the variable that used to carry that reference is gone from both surfaces.
    for rel in ("app/backend/pipeline/stages.py",
                "app/backend/services/generation_queue.py"):
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert not {n for n in names if "first_key" in n}, rel


def test_keyframe_sidecar_invalidates_when_the_cast_changes():
    """Bare file existence would silently reuse a one-character keyframe."""
    ws = _ws()
    story = _story()
    with _no_gpu() as calls:
        spec = RS.story_to_spec(story)
        ST.ensure_keyframes(spec, ws, sheets=ST.ensure_sheets(spec, ws))
        first = len([c for c in calls if c["dest"].parent.name == "keyframes"])
        # Nothing changed: a second run must render nothing at all.
        ST.ensure_keyframes(spec, ws, sheets=ST.ensure_sheets(spec, ws))
        assert len([c for c in calls if c["dest"].parent.name == "keyframes"]) == first
        # Scene 1 gains a character: its keyframe is now stale and must be redrawn.
        story["scenes"][0]["cast"] = ["ann", "boat"]
        changed = RS.story_to_spec(story)
        ST.ensure_keyframes(changed, ws, sheets=ST.ensure_sheets(changed, ws))
        redone = [c for c in calls if c["dest"].name == "01.png"]
    assert len(redone) == 2, f"scene 1 was not redrawn after its cast changed: {len(redone)}"


def test_only_redoes_exactly_the_named_scenes():
    """--only 2 must not quietly render scene 1 as well just because it is missing."""
    spec = RS.story_to_spec(_story())
    ws = _ws()
    with _no_gpu() as calls:
        ST.ensure_keyframes(spec, ws, sheets=ST.ensure_sheets(spec, ws), only={2})
        drawn = [c["dest"].name for c in calls if c["dest"].parent.name == "keyframes"]
    assert drawn == ["02.png"], drawn
    assert not ws.keyframe(1).exists()


def test_sheets_are_skipped_for_engines_that_cannot_use_them():
    """FLUX schnell takes no reference, so drawing character sheets for it is wasted time."""
    spec = RS.story_to_spec(_story(consistency="schnell"))
    ws = _ws()
    with _no_gpu() as calls:
        assert ST.ensure_sheets(spec, ws) == {}
    assert calls == []


def test_engine_none_renders_no_keyframes():
    spec = RS.story_to_spec(_story(consistency="none"))
    ws = _ws()
    with _no_gpu() as calls:
        assert ST.ensure_keyframes(spec, ws, sheets={}) == {}
    assert calls == []


def test_cancel_hook_aborts_before_any_file_is_written():
    spec = RS.story_to_spec(_story())
    ws = _ws()
    hooks = ST.Hooks(cancelled=lambda: True)
    with _no_gpu() as calls:
        try:
            ST.ensure_keyframes(spec, ws, hooks, sheets={"ann": ws.sheet("ann")})
            raise AssertionError("a cancelled render kept going")
        except ST.Cancelled:
            pass
    assert calls == []
    assert not ws.keyframe(1).exists()


def test_hooks_default_to_no_ops():
    spec = RS.story_to_spec(_story(consistency="none"))
    ws = _ws()
    with _no_gpu():
        ST.ensure_keyframes(spec, ws)        # no hooks argument at all
        ST.ensure_smooth(spec, ws)


def test_workspace_paths_are_two_digit_and_stable():
    ws = ST.Workspace(Path("/tmp/x"))
    assert ws.keyframe(3).name == "03.png" and ws.clip(12).name == "12.mp4"
    assert ws.keyframe_meta(3).name == "03.json"
    assert ws.stitch(["ann", "boat"]).name == "_sheet_ann+boat.png"
    assert ws.sheet("ann").parent.name == "refs"


# ----------------------------------------------------------------------------- the spec


def test_story_to_spec_round_trips_the_sample_story():
    spec = RS.story_to_spec(json.loads(SAMPLE.read_text(encoding="utf-8")))
    assert len(spec.scenes) >= 10 and spec.characters
    for sc in spec.scenes:
        assert sc.narration and sc.composition and sc.motion
        assert "{" not in RS.fill(sc.motion, spec.characters), sc.motion
        assert all(k in spec.characters for k in sc.cast), sc.cast
    assert any(len(sc.cast) > 1 for sc in spec.scenes), "no multi-character scene to exercise"


def test_story_to_spec_rejects_bad_input():
    bad = [
        _story(characters={"../../x": {"description": "y"}}),   # a key that is a path
        _story(consistency="magic"),                            # unknown engine
        _story(scenes=[]),                                      # nothing to render
        _story(aspect_ratio="4:3"),                             # unsupported ratio
        _story(scenes=[{"narration": "a"}]),                    # no prompt and no motion
        _story(scenes=[{"narration": "a", "prompt": "b", "cast": ["nobody"]}]),
    ]
    for story in bad:
        try:
            RS.story_to_spec(story)
            raise AssertionError(f"accepted a bad story: {story}")
        except RS.SpecError:
            pass


def test_story_without_motion_still_renders_and_keeps_its_prompt():
    """Stories written before the composition/motion split must keep working."""
    story = _story()
    for sc in story["scenes"]:
        sc.pop("motion")
    spec = RS.story_to_spec(story)
    assert spec.scene(1).motion == spec.scene(1).composition == "{ann} on a dock"


def test_resolve_engine_degrades_instead_of_failing():
    from app.backend.pipeline import image_client as IC
    empty = Path(tempfile.mkdtemp())
    assert IC.resolve_engine("kontext", models_dir=empty) == "none"
    assert IC.resolve_engine(None, models_dir=empty) == "none"
    assert IC.resolve_engine("none", models_dir=empty) == "none"
    # With the files present, an explicit request is honoured and auto stays commercial-safe.
    for name in IC.REQUIRED_FILES["kontext"] + IC.REQUIRED_FILES["schnell"]:
        p = empty / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    assert IC.resolve_engine("kontext", models_dir=empty) == "kontext"
    assert IC.resolve_engine(None, models_dir=empty) == "schnell", "auto picked a non-commercial model"
    # A budget too small for the asked-for engine falls back rather than dying.
    assert IC.resolve_engine("kontext", models_dir=empty, budget_mb=6200) == "schnell"
    assert IC.resolve_engine("kontext", models_dir=empty, budget_mb=1) == "none"


def test_spec_from_project_without_characters_uses_no_references():
    """The app's default path draws every scene on its own, referencing nothing."""
    from app.backend.services import project_spec
    Project, Scene = _models()

    project = Project(name="p", topic="t", voice="af_sarah")
    scenes = [Scene(project_id="p", index=i, prompt=f"scene {i}") for i in range(2)]
    skill = {"aspect_ratio": "9:16", "style_suffix": "neon", "scene_pacing": "fast"}
    spec = project_spec.spec_from_project(project, scenes, skill, {"consistency": "kontext"})
    assert spec.keyframe_engine in ("schnell", "none"), spec.keyframe_engine
    assert all(sc.cast == () for sc in spec.scenes)
    assert spec.clip.max_seconds == 2.5, "scene_pacing was declared but never consumed"
    assert spec.style == "neon" and spec.aspect_ratio == "9:16"


def test_spec_from_project_reads_declared_characters():
    from app.backend.services import project_spec
    Project, Scene = _models()

    project = Project(name="p", topic="t",
                      characters=json.dumps({"ann": {"description": "ANN", "seed": 3},
                                             "../bad": {"description": "no"}}))
    scenes = [Scene(project_id="p", index=0, prompt="{ann} waits",
                    motion_prompt="she turns, slow push-in")]
    spec = project_spec.spec_from_project(project, scenes, {}, {})
    assert set(spec.characters) == {"ann"}, "a path-like character key was accepted"
    assert spec.scenes[0].cast == ("ann",)
    assert spec.scenes[0].motion == "she turns, slow push-in"
    assert spec.scenes[0].composition == "{ann} waits"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as e:  # noqa: BLE001
            failed.append(name)
            print(f"  FAIL  {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - len(failed)} passed, {len(failed)} failed")
    raise SystemExit(1 if failed else 0)
