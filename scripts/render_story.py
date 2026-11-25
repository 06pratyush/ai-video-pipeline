"""Render a story file (stories/*.json) into a narrated, captioned short, fully locally.

Uses the pipeline's own modules: Kokoro for the voice, WanVideoClient (ComfyUI +
Wan2.2 TI2V-5B GGUF) for the clips, FFmpeg for the edit. Each scene has its own
narration line, so every clip is timed to the words spoken over it.

    venv311\\Scripts\\python.exe scripts\\render_story.py stories\\noahs_ark.json            # everything
    venv311\\Scripts\\python.exe scripts\\render_story.py stories\\noahs_ark.json --stage voice
    venv311\\Scripts\\python.exe scripts\\render_story.py stories\\noahs_ark.json --stage clips --only 1
    venv311\\Scripts\\python.exe scripts\\render_story.py stories\\noahs_ark.json --stage edit

Finished clips are kept, so a rerun only renders what is missing (delete a clip to redo it).
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SIZES = {"9:16": (480, 832), "16:9": (832, 480), "1:1": (640, 640)}
FINAL = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
PAD_S = 0.35  # breath after each line


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed:\n{r.stderr[-2000:]}")


def stage_voice(story, out: Path):
    from app.backend.pipeline.kokoro_tts import KokoroTTSClient
    tts = KokoroTTSClient(voice=story.get("voice", "bm_george"),
                          speed=float(story.get("voice_speed", 1.0)),
                          lang="b" if story.get("voice", "").startswith("b") else "a")
    timings = []
    for i, sc in enumerate(story["scenes"], 1):
        wav = out / "audio" / f"{i:02d}.wav"
        _, dur = tts.generate(sc["narration"], str(wav))
        timings.append(round(dur, 3))
        print(f"  voice {i:02d}: {dur:.2f}s  {sc['narration']}")
    (out / "audio" / "durations.json").write_text(json.dumps(timings))
    print(f"  total narration {sum(timings):.1f}s")


def stage_clips(story, out: Path, only=None, steps=20):
    from app.backend.pipeline.wan_client import WanVideoClient, frames_for_seconds
    from app.backend.services import comfyui_manager
    durs = json.loads((out / "audio" / "durations.json").read_text())
    if not comfyui_manager.start():
        raise SystemExit("ComfyUI did not start (see app/runtime/comfyui/comfyui.log)")
    wan = WanVideoClient(str(ROOT / "app/workflows/wan22_ti2v_5b_gguf.json"))
    w, h = SIZES[story.get("aspect_ratio", "9:16")]
    for i, sc in enumerate(story["scenes"], 1):
        if only and i not in only:
            continue
        dest = out / "clips" / f"{i:02d}.mp4"
        if dest.exists():
            print(f"  clip {i:02d}: kept")
            continue
        prompt = sc["prompt"].replace("{noah}", story.get("noah", "")) + ", " + story["style"]
        frames = frames_for_seconds(min(durs[i - 1] + PAD_S, 5.0))
        t0 = time.time()
        path = wan.generate(prompt=prompt, output_dir=str(out / "clips" / "raw"),
                            width=w, height=h, num_frames=frames, steps=steps, seed=1000 + i)
        Path(path).replace(dest)
        print(f"  clip {i:02d}: {frames} frames in {time.time() - t0:.0f}s")


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_captions(story, durs, path: Path):
    """Two to four words per caption, timed in proportion to word count within each line."""
    lines, t, n = [], 0.0, 1
    for sc, d in zip(story["scenes"], durs):
        words = sc["narration"].split()
        chunks = [words[k:k + 3] for k in range(0, len(words), 3)]
        if len(chunks) > 1 and len(chunks[-1]) == 1:
            chunks[-2] += chunks.pop()
        start = t
        for ch in chunks:
            end = start + d * len(ch) / len(words)
            lines.append(f"{n}\n{srt_time(start)} --> {srt_time(end)}\n{' '.join(ch)}\n")
            n, start = n + 1, end
        t += d + PAD_S
    path.write_text("\n".join(lines), encoding="utf-8")


def stage_edit(story, out: Path):
    durs = json.loads((out / "audio" / "durations.json").read_text())
    fw, fh = FINAL[story.get("aspect_ratio", "9:16")]
    seg_dir = out / "segments"
    seg_dir.mkdir(exist_ok=True)
    segs = []
    for i, d in enumerate(durs, 1):
        clip, wav, seg = out / "clips" / f"{i:02d}.mp4", out / "audio" / f"{i:02d}.wav", seg_dir / f"{i:02d}.mp4"
        length = d + PAD_S
        # Slow the clip slightly if the line runs longer than it, then hold the last frame.
        slow = max(1.0, min(length / ffprobe_duration(clip), 1.25))
        vf = (f"setpts={slow:.4f}*PTS,fps=24,scale={fw}:{fh}:flags=lanczos,"
              f"tpad=stop_mode=clone:stop_duration=5,trim=duration={length:.3f},"
              f"fade=in:st=0:d=0.25,fade=out:st={length - 0.25:.3f}:d=0.25,setsar=1")
        run(["ffmpeg", "-y", "-i", str(clip), "-i", str(wav), "-filter_complex",
             f"[0:v]{vf}[v];[1:a]apad=whole_dur={length:.3f},aresample=48000[a]",
             "-map", "[v]", "-map", "[a]", "-t", f"{length:.3f}",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", str(seg)])
        segs.append(seg)
    (seg_dir / "list.txt").write_text("".join(f"file '{s.name}'\n" for s in segs))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "../concat.mp4"],
        cwd=seg_dir)

    write_captions(story, durs, out / "captions.srt")
    style = ("FontName=Arial Black,FontSize=13,Bold=1,PrimaryColour=&H00FFFFFF,"
             "OutlineColour=&H00000000,BorderStyle=1,Outline=2.2,Shadow=0,Alignment=2,MarginV=70")
    grade = "eq=contrast=1.05:saturation=1.12,unsharp=5:5:0.4"
    run(["ffmpeg", "-y", "-i", "concat.mp4", "-vf",
         f"{grade},subtitles=captions.srt:force_style='{style}'",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-movflags", "+faststart", "final.mp4"], cwd=out)
    print(f"  final: {out / 'final.mp4'} ({ffprobe_duration(out / 'final.mp4'):.1f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("--stage", choices=["voice", "clips", "edit", "all"], default="all")
    ap.add_argument("--only", type=lambda s: [int(x) for x in s.split(",")])
    ap.add_argument("--steps", type=int, default=20)
    args = ap.parse_args()
    story_path = Path(args.story).resolve()
    story = json.loads(story_path.read_text(encoding="utf-8"))
    out = ROOT / "outputs" / story_path.stem
    for d in ("audio", "clips"):
        (out / d).mkdir(parents=True, exist_ok=True)
    if args.stage in ("voice", "all"):
        stage_voice(story, out)
    if args.stage in ("clips", "all"):
        stage_clips(story, out, args.only, args.steps)
    if args.stage in ("edit", "all"):
        stage_edit(story, out)


if __name__ == "__main__":
    main()
