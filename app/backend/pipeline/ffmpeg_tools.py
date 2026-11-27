"""Small FFmpeg helpers shared by the renderer, the app and the sweep harness.

These used to live at the top of ``scripts/render_story.py``, where nothing else could
reach them. Everything here builds an argument list and runs it directly: no shell, so a
character description or a file name can never become a command.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

# A stitched character sheet is scaled to this height so the pieces line up.
STITCH_HEIGHT = 1024

_nvenc: bool | None = None


def run(cmd: Sequence[str], cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    """Run a command, raising with the tail of its stderr when it fails."""
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed:\n{r.stderr[-2500:]}")
    return r


def ffprobe_duration(path: str | Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", str(path)])
    return float(out.stdout.strip())


def has_nvenc() -> bool:
    """True when FFmpeg can really encode with NVENC, not merely list it.

    The encoder is listed on machines where it cannot be opened, so this does a one-frame
    test encode. The answer is cached: the probe costs ~200 ms and cannot change mid-run.
    """
    global _nvenc
    if _nvenc is not None:
        return _nvenc
    listed = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                            capture_output=True, text=True)
    if "h264_nvenc" not in listed.stdout:
        _nvenc = False
        return _nvenc
    test = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=256x256:d=0.1",
                           "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True)
    _nvenc = test.returncode == 0
    return _nvenc


def video_codec_args(nvenc: bool, quality: int = 19) -> list[str]:
    if nvenc:
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(quality),
                "-b:v", "0", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(quality - 1),
            "-pix_fmt", "yuv420p"]


def last_frame(video: str | Path, dest: str | Path) -> Path:
    """Grab a clip's final frame, for continuing the next scene from where this one ended."""
    run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", str(video), "-frames:v", "1",
         "-update", "1", str(dest)])
    return Path(dest)


def stitch_horizontal(sources: Sequence[str | Path], dest: str | Path,
                      height: int = STITCH_HEIGHT) -> Path:
    """Lay 2-3 character sheets side by side as one image.

    FLUX Kontext conditions on a single reference, so a scene with several characters needs
    them in one picture. Doing it here rather than with a ComfyUI node keeps the result
    inspectable on disk when a keyframe comes out wrong, and testable with no ComfyUI at all.
    """
    srcs = [Path(s) for s in sources]
    if not 2 <= len(srcs) <= 3:
        raise ValueError(f"stitch_horizontal takes 2 or 3 images, got {len(srcs)}")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    ins: list[str] = []
    for s in srcs:
        ins += ["-i", str(s)]
    scales = ";".join(f"[{i}:v]scale=-2:{height}[s{i}]" for i in range(len(srcs)))
    joins = "".join(f"[s{i}]" for i in range(len(srcs)))
    graph = f"{scales};{joins}hstack=inputs={len(srcs)}[out]"
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", graph, "-map", "[out]",
         "-frames:v", "1", "-update", "1", str(dest)])
    return dest
