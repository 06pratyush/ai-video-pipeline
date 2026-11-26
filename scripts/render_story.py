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
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.backend.pipeline import story_edit as E  # noqa: E402

SIZES = {"9:16": (480, 832), "16:9": (832, 480), "1:1": (640, 640)}
FINAL = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
PAD_S = 0.35      # breath after each line
XFADE_S = 0.4     # dissolve between scenes
STAGES = ["voice", "refs", "keyframes", "clips", "smooth", "music", "edit"]
KEY_RE = re.compile(r"^[a-z0-9_-]{1,40}$")


def log(msg: str):
    print(msg, flush=True)


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed:\n{r.stderr[-2500:]}")


def has_nvenc() -> bool:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
    if "h264_nvenc" not in r.stdout:
        return False
    test = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=256x256:d=0.1",
                           "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True)
    return test.returncode == 0


def video_codec_args(nvenc: bool, quality: int = 19) -> list[str]:
    if nvenc:
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(quality),
                "-b:v", "0", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(quality - 1), "-pix_fmt", "yuv420p"]


# --------------------------------------------------------------------------- story


def load_story(path: Path) -> dict:
    story = json.loads(path.read_text(encoding="utf-8"))
    chars = story.get("characters", {})
    # v1 stories had one top-level "noah" description; treat it as a character.
    if "noah" in story and "noah" not in chars:
        chars["noah"] = {"description": story["noah"]}
    for key in chars:
        if not KEY_RE.match(key):
            raise SystemExit(f"character key {key!r} must match {KEY_RE.pattern}")
    story["characters"] = chars
    story.setdefault("consistency", "none")
    if story["consistency"] not in ("none", "schnell", "kontext"):
        raise SystemExit("consistency must be none, schnell or kontext")
    if not story.get("scenes"):
        raise SystemExit("story has no scenes")
    for i, sc in enumerate(story["scenes"], 1):
        # A scene either says something or holds a deliberate beat of silence.
        if not sc.get("narration", "").strip() and not sc.get("silence"):
            raise SystemExit(f"scene {i} has no narration: give it one, or a silence in seconds")
        if not sc.get("prompt", "").strip():
            raise SystemExit(f"scene {i} has no prompt")
    return story


def fill(text: str, story: dict) -> str:
    for key, c in story["characters"].items():
        text = text.replace("{" + key + "}", c["description"])
    return text


def cast_of(scene: dict, story: dict) -> list[str]:
    if "cast" in scene:
        return [c for c in scene["cast"] if c in story["characters"]]
    return [k for k in story["characters"] if "{" + k + "}" in scene["prompt"]]


def comfy():
    from app.backend.services import comfyui_manager
    if not comfyui_manager.start():
        raise SystemExit("ComfyUI did not start (see app/runtime/comfyui/comfyui.log)")
    from app.backend.pipeline.comfy_client import ComfyClient
    c = ComfyClient()
    c.free()  # each stage starts with the whole GPU
    return c


def wanted(i: int, dest: Path, only) -> bool:
    """Render scene i? With --only, exactly those scenes (redone); otherwise only missing ones."""
    return (i in only) if only else not dest.exists()


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


def _silence_wav(path: Path, seconds: float, sample_rate: int = 24000) -> None:
    """A silent line: a deadpan beat still needs a slot on the timeline."""
    import numpy as np
    import soundfile as sf
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.zeros(int(seconds * sample_rate), dtype="float32"), sample_rate)


def stage_voice(story, out: Path, only=None, **_):
    from app.backend.pipeline.kokoro_tts import VOICES, KokoroTTSClient
    from app.backend.pipeline import whisper_client
    audio = out / "audio"
    dur_file = audio / "durations.json"
    durs = json.loads(dur_file.read_text()) if dur_file.exists() else []
    clients: dict[tuple[str, float], KokoroTTSClient] = {}
    redone = False
    for i, sc in enumerate(story["scenes"], 1):
        wav = audio / f"{i:02d}.wav"
        if not wanted(i, wav, only) and len(durs) >= i:
            continue
        text = sc.get("narration", "").strip()
        if not text:
            dur = min(max(float(sc.get("silence", 1.5)), 0.2), 5.0)
            _silence_wav(wav, dur)
            log(f"  voice {i:02d}: {dur:.2f}s silent beat")
        else:
            # A two-hander needs two voices: a scene may name its own speaker.
            voice = sc.get("voice", story.get("voice", "bm_george"))
            if voice not in VOICES:
                raise SystemExit(f"scene {i}: unknown voice {voice!r} (have {', '.join(VOICES)})")
            speed = float(sc.get("voice_speed", story.get("voice_speed", 1.0)))
            tts = clients.get((voice, speed))
            if tts is None:
                tts = clients[(voice, speed)] = KokoroTTSClient(
                    voice=voice, speed=speed, lang="b" if voice.startswith("b") else "a")
            _, dur = tts.generate(text, str(wav))
            log(f"  voice {i:02d}: {dur:.2f}s as {voice} on {tts.device}")
        durs = durs[:i - 1] + [round(dur, 3)] + durs[i:]
        redone = True
    dur_file.write_text(json.dumps(durs))
    clients.clear()
    _free_torch()
    words_file = audio / "words.json"
    if redone or not words_file.exists():
        if not whisper_client.is_available():
            log("  WARNING: faster-whisper is not installed; captions will be timed by word "
                "length instead of by the voice (pip install faster-whisper)")
        else:
            heard = []
            for i, sc in enumerate(story["scenes"], 1):
                # Nothing is said in a silent beat, so there is nothing to time.
                heard.append([] if not sc.get("narration", "").strip()
                             else whisper_client.word_timestamps(str(audio / f"{i:02d}.wav"),
                                                                 "small.en"))
            words_file.write_text(json.dumps(heard))
            log(f"  words: {sum(len(h) for h in heard)} timed on {whisper_client._device()[0]}")
    log(f"  total narration {sum(durs):.1f}s")


def stage_refs(story, out: Path, only=None, **_):
    if story["consistency"] == "none" or not story["characters"]:
        return
    from app.backend.pipeline.image_client import ImageClient
    comfy()
    img = ImageClient("schnell")
    for key, ch in story["characters"].items():
        dest = out / "refs" / f"{key}.png"
        if dest.exists():
            continue
        prompt = (f"character reference sheet, single full-body view of {ch['description']}, "
                  f"standing, facing the camera, neutral pose, plain soft light background, "
                  f"{story['style']}")
        t0 = time.time()
        img.generate(prompt, dest, 768, 1344, seed=int(ch.get("seed", 7)))
        log(f"  ref {key}: {time.time() - t0:.0f}s")


def stage_keyframes(story, out: Path, only=None, **_):
    mode = story["consistency"]
    if mode == "none":
        return
    from app.backend.pipeline.image_client import ImageClient, keyframe_size
    comfy()
    w, h = keyframe_size(*SIZES[story.get("aspect_ratio", "9:16")])
    clients = {}
    if mode == "kontext":
        log("  NOTE: FLUX.1 Kontext dev is licensed for non-commercial use only.")
    for i, sc in enumerate(story["scenes"], 1):
        dest = out / "keyframes" / f"{i:02d}.png"
        if not wanted(i, dest, only):
            continue
        cast = cast_of(sc, story)
        scene_text = fill(sc.get("keyframe", sc["prompt"]), story)
        use = "kontext" if (mode == "kontext" and cast) else "schnell"
        client = clients.setdefault(use, ImageClient(use))
        seed = int(sc.get("keyframe_seed", 2000 + i))  # change it to re-roll one bad keyframe
        t0 = time.time()
        if use == "kontext":
            # Identity, not pose: naming the body as something to keep identical makes
            # Kontext reproduce the reference sheet's neutral standing pose in every shot.
            prompt = (f"Keep this character's face, hairstyle, skin tone and clothing exactly "
                      f"the same, but draw them in a completely new shot, freely re-posed and "
                      f"re-framed to suit it: {scene_text}. "
                      f"Vertical cinematic frame, {story['style']}")
            client.generate(prompt, dest, w, h, seed=seed,
                            reference=out / "refs" / f"{cast[0]}.png")
        else:
            client.generate(f"{scene_text}, {story['style']}", dest, w, h, seed=seed)
        log(f"  keyframe {i:02d} ({use}{', ' + cast[0] if use == 'kontext' else ''}): "
            f"{time.time() - t0:.0f}s")


def last_frame(video: Path, dest: Path) -> Path:
    run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", str(video), "-frames:v", "1",
         "-update", "1", str(dest)])
    return dest


def stage_clips(story, out: Path, only=None, steps=20, **_):
    from app.backend.pipeline.wan_client import WanVideoClient, frames_for_seconds
    durs = json.loads((out / "audio" / "durations.json").read_text())
    comfy()
    wan = WanVideoClient(str(ROOT / "app/workflows/wan22_ti2v_5b_gguf.json"))
    w, h = SIZES[story.get("aspect_ratio", "9:16")]
    for i, sc in enumerate(story["scenes"], 1):
        dest = out / "clips" / f"{i:02d}.mp4"
        if not wanted(i, dest, only):
            continue
        prompt = fill(sc["prompt"], story) + ", " + story["style"]
        start = None
        if sc.get("continue", story.get("continue_from_previous", False)) and i > 1:
            prev = out / "clips" / f"{i - 1:02d}.mp4"
            if prev.exists():
                start = last_frame(prev, out / "keyframes" / f"{i:02d}_from_prev.png")
        if start is None and (out / "keyframes" / f"{i:02d}.png").exists():
            start = out / "keyframes" / f"{i:02d}.png"
        frames = frames_for_seconds(min(durs[i - 1] + PAD_S + XFADE_S, 5.0))
        t0 = time.time()
        path = wan.generate(prompt=prompt, output_dir=str(out / "clips" / "raw"), width=w, height=h,
                            num_frames=frames, steps=steps, seed=1000 + i,
                            start_image=str(start) if start else None)
        Path(path).replace(dest)
        (out / "smooth" / f"{i:02d}.mp4").unlink(missing_ok=True)  # stale once the clip changes
        log(f"  clip {i:02d}: {frames} frames{' from keyframe' if start else ''} "
            f"in {time.time() - t0:.0f}s")


def stage_smooth(story, out: Path, only=None, **_):
    if not story.get("smooth", True):
        return
    from app.backend.pipeline.smooth_client import SmoothClient
    comfy()
    sm = SmoothClient()
    upscale = story.get("upscale", False)
    for i in range(1, len(story["scenes"]) + 1):
        src, dest = out / "clips" / f"{i:02d}.mp4", out / "smooth" / f"{i:02d}.mp4"
        if not src.exists() or not wanted(i, dest, only):
            continue
        t0 = time.time()
        sm.smooth(src, dest, src_fps=24.0, upscale=upscale)  # ESRGAN x2 adds ~7 min per clip on an RTX 4060
        log(f"  smooth {i:02d}: 48 fps{' + ESRGAN x2' if upscale else ''} in {time.time() - t0:.0f}s")


def stage_music(story, out: Path, only=None, **_):
    if not story.get("music"):
        return
    dest = out / "music.flac"
    if dest.exists():
        return
    from app.backend.pipeline.music_client import MusicClient
    durs = json.loads((out / "audio" / "durations.json").read_text())
    total = sum(d + PAD_S for d in durs)
    comfy()
    t0 = time.time()
    MusicClient().generate(story["music"], total + 2.0, dest, seed=int(story.get("music_seed", 42)))
    log(f"  music: {total + 2:.0f}s of audio in {time.time() - t0:.0f}s")


def stage_edit(story, out: Path, **_):
    durs = json.loads((out / "audio" / "durations.json").read_text())
    n = len(durs)
    fw, fh = FINAL[story.get("aspect_ratio", "9:16")]
    smooth = all((out / "smooth" / f"{i:02d}.mp4").exists() for i in range(1, n + 1))
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
        ins += ["-i", str(out / "audio" / f"{i + 1:02d}.wav")]
        graph.append(f"[{i}:a]aresample=48000,apad=whole_dur={length:.3f},"
                     f"atrim=duration={length:.3f}[a{i}]")
    graph.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[aout]")
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(graph), "-map", "[aout]",
         "-c:a", "pcm_s16le", str(out / "narration.wav")])

    # 2. One segment per scene: length fitted, scaled, slow push, never frozen.
    seg_lens = E.segment_lengths(durs, PAD_S, XFADE_S)
    segs = []
    for i in range(1, n + 1):
        clip = out / ("smooth" if smooth else "clips") / f"{i:02d}.mp4"
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
    words = E.caption_words(story["scenes"], durs, heard, PAD_S)
    cap = story.get("captions", {})
    (out / "captions.ass").write_text(
        E.build_ass(E.chunk_words(words, int(cap.get("words_per_chunk", 3))), fw, fh,
                    **{k: v for k, v in cap.items()
                       if k in ("font", "size", "margin_v", "highlight", "uppercase")}),
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
            "clips": stage_clips, "smooth": stage_smooth, "music": stage_music, "edit": stage_edit}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story")
    ap.add_argument("--stage", choices=STAGES + ["all"], default="all")
    ap.add_argument("--only", type=lambda s: [int(x) for x in s.split(",")],
                    help="scene numbers to (re)do, e.g. 3,4")
    ap.add_argument("--steps", type=int, default=20, help="Wan sampling steps")
    ap.add_argument("--out", help="output folder (default outputs/<story name>)")
    args = ap.parse_args()
    story_path = Path(args.story).resolve()
    story = load_story(story_path)
    out = Path(args.out).resolve() if args.out else ROOT / "outputs" / story_path.stem
    for d in ("audio", "refs", "keyframes", "clips", "smooth"):
        (out / d).mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for st in (STAGES if args.stage == "all" else [args.stage]):
        log(f"[{st}]")
        STAGE_FN[st](story, out, only=args.only, steps=args.steps)
    log(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
