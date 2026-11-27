"""Render a story file (stories/*.json) into a finished short, fully locally, on the GPU.

AI Video Studio v2 stages (each one skips work whose output already exists):

    voice      Kokoro (GPU) speaks each line; faster-whisper (GPU) times every word
    refs       FLUX schnell draws each recurring character once (the character sheet)
    keyframes  FLUX Kontext (or schnell) draws each scene's first frame with that character
    clips      Wan2.2 TI2V-5B animates each keyframe (image-to-video)
    smooth     RIFE 24->48 fps + Real-ESRGAN x2 (GPU, in ComfyUI)
    music      ACE-Step 3.5B scores the whole film (GPU, in ComfyUI)
    edit       crossfades, slow camera push, word-highlight captions, music ducked under voice

    venv311\\Scripts\\python.exe scripts\\render_story.py stories\\noahs_ark.json
    venv311\\Scripts\\python.exe scripts\\render_story.py stories\\noahs_ark.json --stage keyframes --only 3,4

Delete a file under outputs/<story>/ to redo just that piece, or use --only to redo scenes.

The refs, keyframes, clips and smooth stages live in ``app/backend/pipeline/stages.py`` so
the desktop app runs exactly the same code; this file is the command line around them.
"""
import argparse
import json
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.backend.pipeline import ffmpeg_tools as FT  # noqa: E402
from app.backend.pipeline import render_spec as RS  # noqa: E402
from app.backend.pipeline import stages as ST  # noqa: E402
from app.backend.pipeline import story_edit as E  # noqa: E402

# Kept as module names because other code and the tests import them from here.
SIZES, FINAL = RS.SIZES, RS.FINAL
PAD_S, XFADE_S = RS.PAD_S, RS.XFADE_S
KEY_RE = RS.KEY_RE
run, ffprobe_duration = FT.run, FT.ffprobe_duration
has_nvenc, video_codec_args = FT.has_nvenc, FT.video_codec_args

STAGES = ["voice", "refs", "keyframes", "clips", "smooth", "music", "edit"]


def log(msg: str):
    print(msg, flush=True)


# --------------------------------------------------------------------------- story


def load_story(path: Path) -> dict:
    """Read and validate a story file, returning the raw dict.

    Validation is :func:`render_spec.story_to_spec`, so the command line and the app agree
    on what a valid story is; its ValueError becomes the SystemExit a CLI should give.
    """
    story = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        spec = RS.story_to_spec(story)
    except RS.SpecError as e:
        raise SystemExit(str(e))
    # v1 stories kept one top-level character; surface it the way callers expect.
    story["characters"] = {k: {"description": c.description, "seed": c.seed}
                           for k, c in spec.characters.items()}
    story.setdefault("consistency", "none")
    return story


def fill(text: str, story: dict) -> str:
    """Replace ``{key}`` with that character's description (story-dict form)."""
    for key, c in (story.get("characters") or {}).items():
        description = c["description"] if isinstance(c, dict) else getattr(c, "description", c)
        text = text.replace("{" + key + "}", description)
    return text


def spec_for(story: dict, steps: int | None = None) -> RS.RenderSpec:
    spec = RS.story_to_spec(story)
    if steps:
        spec = replace(spec, clip=replace(spec.clip, steps=steps))
    return spec


def hooks() -> ST.Hooks:
    return ST.Hooks(log=log)


def _free_torch():
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


# --------------------------------------------------------------------------- stages


def stage_voice(spec: RS.RenderSpec, ws: ST.Workspace, only=None, **_):
    from app.backend.pipeline import whisper_client
    from app.backend.pipeline.kokoro_tts import KokoroTTSClient
    audio = ws.root / "audio"
    dur_file = audio / "durations.json"
    durs = json.loads(dur_file.read_text()) if dur_file.exists() else []
    tts, redone = None, False
    for sc in spec.scenes:
        wav = ws.audio(sc.index)
        if not ST.wanted(sc.index, wav, only) and len(durs) >= sc.index:
            continue
        tts = tts or KokoroTTSClient(voice=spec.voice, speed=spec.voice_speed,
                                     lang="b" if spec.voice.startswith("b") else "a")
        _, dur = tts.generate(sc.narration, str(wav))
        durs = durs[:sc.index - 1] + [round(dur, 3)] + durs[sc.index:]
        redone = True
        log(f"  voice {sc.index:02d}: {dur:.2f}s on {tts.device}")
    dur_file.write_text(json.dumps(durs))
    tts = None
    _free_torch()
    words_file = audio / "words.json"
    if redone or not words_file.exists():
        if not whisper_client.is_available():
            log("  WARNING: faster-whisper is not installed; captions will be timed by word "
                "length instead of by the voice (pip install faster-whisper)")
        else:
            heard = [whisper_client.word_timestamps(str(ws.audio(sc.index)), "small.en")
                     for sc in spec.scenes]
            words_file.write_text(json.dumps(heard))
            log(f"  words: {sum(len(h) for h in heard)} timed on {whisper_client._device()[0]}")
    log(f"  total narration {sum(durs):.1f}s")


def stage_refs(spec: RS.RenderSpec, ws: ST.Workspace, only=None, **_):
    ST.ensure_sheets(spec, ws, hooks())


def stage_keyframes(spec: RS.RenderSpec, ws: ST.Workspace, only=None, **_):
    sheets = ST.ensure_sheets(spec, ws, hooks())
    ST.ensure_keyframes(spec, ws, hooks(), sheets=sheets, only=only)


def stage_clips(spec: RS.RenderSpec, ws: ST.Workspace, only=None, **_):
    durs = json.loads((ws.root / "audio" / "durations.json").read_text())
    keyframes = {sc.index: ws.keyframe(sc.index) for sc in spec.scenes
                 if ws.keyframe(sc.index).exists()}
    ST.ensure_clips(spec, ws, hooks(), keyframes=keyframes, durations=durs, only=only)


def stage_smooth(spec: RS.RenderSpec, ws: ST.Workspace, only=None, **_):
    ST.ensure_smooth(spec, ws, hooks(), only=only)


def stage_music(spec: RS.RenderSpec, ws: ST.Workspace, only=None, **_):
    if not spec.music:
        return
    dest = ws.root / "music.flac"
    if dest.exists():
        return
    from app.backend.pipeline.music_client import MusicClient
    durs = json.loads((ws.root / "audio" / "durations.json").read_text())
    total = sum(d + PAD_S for d in durs)
    ST.connect(spec)
    t0 = time.time()
    MusicClient(spec.backend.comfyui_url).generate(spec.music, total + 2.0, dest,
                                                   seed=spec.music_seed)
    log(f"  music: {total + 2:.0f}s of audio in {time.time() - t0:.0f}s")


def stage_edit(spec: RS.RenderSpec, ws: ST.Workspace, **_):
    out = ws.root
    durs = json.loads((out / "audio" / "durations.json").read_text())
    n = len(durs)
    fw, fh = RS.final_size(spec.aspect_ratio)
    smooth = all(ws.smooth(i).exists() for i in range(1, n + 1))
    fps = 48 if smooth else 24
    nvenc = has_nvenc()
    log(f"  edit: {n} scenes, {fps} fps, encoder {'NVENC (GPU)' if nvenc else 'libx264'}")
    seg_dir = out / "segments"
    if seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir()

    # 1. Narration track: each line padded to its slot on the timeline.
    ins, graph = [], []
    for i, (_, length) in enumerate(E.slots(durs, PAD_S)):
        ins += ["-i", str(ws.audio(i + 1))]
        graph.append(f"[{i}:a]aresample=48000,apad=whole_dur={length:.3f},"
                     f"atrim=duration={length:.3f}[a{i}]")
    graph.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[aout]")
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(graph), "-map", "[aout]",
         "-c:a", "pcm_s16le", str(out / "narration.wav")])

    # 2. One segment per scene: length fitted, scaled, slow push, never frozen.
    seg_lens = E.segment_lengths(durs, PAD_S, XFADE_S)
    segs = []
    for i in range(1, n + 1):
        clip = ws.smooth(i) if smooth else ws.clip(i)
        seg = seg_dir / f"{i:02d}.mp4"
        vf = E.segment_filter(ffprobe_duration(clip), seg_lens[i - 1], fw, fh, fps)
        run(["ffmpeg", "-y", "-i", str(clip), "-vf", vf, "-an", "-t", f"{seg_lens[i - 1]:.3f}",
             *video_codec_args(nvenc, 17), str(seg)])
        segs.append(seg)

    # 3. Dissolves between scenes, each one landing on the next line's first word.
    graph, label = E.xfade_graph(n, E.xfade_offsets(durs, PAD_S), XFADE_S)
    ins = [a for s in segs for a in ("-i", str(s))]
    run(["ffmpeg", "-y", *ins, "-filter_complex", graph, "-map", label,
         *video_codec_args(nvenc, 17), str(out / "picture.mp4")])

    # 4. Captions: the script's words on whisper's timings, the active word highlighted.
    words_file = out / "audio" / "words.json"
    heard = json.loads(words_file.read_text()) if words_file.exists() else [[] for _ in durs]
    words = []
    for (start, _), sc, d, h in zip(E.slots(durs, PAD_S), spec.scenes, durs, heard):
        words += E.align_words(sc.narration, h, start, d)
    (out / "captions.ass").write_text(E.build_ass(E.chunk_words(words, 3), fw, fh),
                                      encoding="utf-8")
    (out / "captions_words.json").write_text(json.dumps(words, indent=1))

    # 5. Final: grade + captions; voice + ducked music; loudness -14 LUFS.
    total = round(sum(d + PAD_S for d in durs), 3)
    vf = "eq=contrast=1.04:saturation=1.08,subtitles=captions.ass"
    cmd = ["ffmpeg", "-y", "-i", "picture.mp4", "-i", "narration.wav"]
    if (out / "music.flac").exists():
        cmd += ["-i", "music.flac", "-filter_complex",
                f"[0:v]{vf}[vout];" + E.mix_filter(total, voice="[1:a]", music="[2:a]"),
                "-map", "[vout]", "-map", "[aout]"]
    else:
        cmd += ["-vf", vf, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-map", "0:v", "-map", "1:a"]
    cmd += [*video_codec_args(nvenc, 19), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", "-t", f"{total:.3f}", "final.mp4"]
    run(cmd, cwd=out)
    log(f"  final: {out / 'final.mp4'} ({ffprobe_duration(out / 'final.mp4'):.1f}s)")


STAGE_FN = {"voice": stage_voice, "refs": stage_refs, "keyframes": stage_keyframes,
            "clips": stage_clips, "smooth": stage_smooth, "music": stage_music,
            "edit": stage_edit}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story")
    ap.add_argument("--stage", choices=STAGES + ["all"], default="all")
    ap.add_argument("--only", type=lambda s: [int(x) for x in s.split(",")],
                    help="scene numbers to (re)do, e.g. 3,4")
    ap.add_argument("--steps", type=int, default=None, help="Wan sampling steps")
    ap.add_argument("--out", help="output folder (default outputs/<story name>)")
    args = ap.parse_args()
    story_path = Path(args.story).resolve()
    story = load_story(story_path)
    spec = spec_for(story, args.steps)
    root = Path(args.out).resolve() if args.out else ROOT / "outputs" / story_path.stem
    ws = ST.Workspace(root)
    ws.mkdirs()
    t0 = time.time()
    for st in (STAGES if args.stage == "all" else [args.stage]):
        log(f"[{st}]")
        STAGE_FN[st](spec, ws, only=args.only)
    log(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
