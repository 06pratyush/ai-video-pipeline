"""FFmpeg post-processing — extended from root ffmpeg_merger.py."""
import subprocess
import os
from pathlib import Path


def _run(cmd: list[str], label: str = "FFmpeg"):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[{label}] failed:\n{result.stderr}")
    return result


def merge_video_audio(
    video_path: str, audio_path: str, output_path: str, audio_duration: float | None = None
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    if audio_duration:
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", video_path,
            "-i", audio_path,
            "-t", str(audio_duration),
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path, "-i", audio_path,
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest",
            output_path,
        ]
    _run(cmd, "merge_video_audio")
    return output_path


def concatenate_clips(clip_paths: list[str], output_path: str) -> str:
    """Concatenate multiple video clips into one."""
    import tempfile
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
        list_file = f.name
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", output_path,
    ]
    _run(cmd, "concatenate")
    os.unlink(list_file)
    return output_path


def apply_lut(input_path: str, output_path: str, lut_path: str) -> str:
    """Apply a .cube LUT for color grading."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"lut3d={lut_path}",
        "-c:a", "copy", output_path,
    ]
    _run(cmd, "apply_lut")
    return output_path


def add_subtitles(input_path: str, srt_path: str, output_path: str) -> str:
    """Burn SRT subtitles into video."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"subtitles={srt_path}",
        "-c:a", "copy", output_path,
    ]
    _run(cmd, "subtitles")
    return output_path


def convert_for_instagram(input_path: str, output_path: str, format: str = "reel") -> str:
    w, h = (1080, 1920) if format == "reel" else (1080, 1080)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264", "-crf", "23", "-preset", "slow",
        "-c:a", "aac", "-b:a", "192k",
        "-r", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        output_path,
    ]
    _run(cmd, "instagram")
    return output_path


def convert_for_youtube(input_path: str, output_path: str) -> str:
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264", "-crf", "18", "-preset", "slow",
        "-c:a", "aac", "-b:a", "320k",
        "-r", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        output_path,
    ]
    _run(cmd, "youtube")
    return output_path


def convert_aspect_ratio(
    input_path: str, output_path: str,
    aspect: str = "16:9", resolution: str = "1080p"
) -> str:
    res_map = {"720p": (1280, 720), "1080p": (1920, 1080), "4K": (3840, 2160)}
    aspect_map = {
        "16:9": (1920, 1080), "9:16": (1080, 1920),
        "1:1": (1080, 1080), "4:5": (1080, 1350),
    }
    if aspect in aspect_map:
        w, h = aspect_map[aspect]
        if resolution in res_map:
            scale_w, scale_h = res_map[resolution]
            if aspect == "9:16":
                w, h = scale_h, scale_w * (16 // 9)
    else:
        w, h = (1920, 1080)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "copy", "-movflags", "+faststart",
        output_path,
    ]
    _run(cmd, "convert_aspect")
    return output_path
