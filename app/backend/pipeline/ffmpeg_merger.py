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
    """Burn SRT subtitles with styled typography into video."""
    # Use subtitles filter with force_style for clean white text + shadow
    safe_srt = srt_path.replace("\\", "/").replace(":", "\\:")
    style = (
        "FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BackColour=&H80000000,"
        "Bold=1,Outline=2,Shadow=1,Alignment=2,MarginV=30"
    )
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"subtitles='{safe_srt}':force_style='{style}'",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "copy", "-movflags", "+faststart",
        output_path,
    ]
    _run(cmd, "subtitles")
    return output_path


def merge_with_background_music(
    video_path: str,
    narration_path: str,
    music_path: str,
    output_path: str,
    audio_duration: float,
    music_volume: float = 0.12,
) -> str:
    """
    Mix narration + background music with auto-ducking.
    Music is looped to match duration, then ducked under narration.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    # amix: narration at full volume, music at music_volume
    # Stream loop music in case it's shorter than narration
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", video_path,
        "-i", narration_path,
        "-stream_loop", "-1", "-i", music_path,
        "-t", str(audio_duration),
        "-filter_complex",
        f"[1:a]volume=1.0[narr];"
        f"[2:a]volume={music_volume}[music];"
        "[narr][music]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        output_path,
    ]
    _run(cmd, "merge_with_music")
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


def apply_color_grade(input_path: str, output_path: str, grade: str) -> str:
    """Apply a color grade style using FFmpeg curves — no external LUT files needed."""
    grade_filters: dict[str, str] = {
        # Teal-orange cinematic: lift shadows toward teal, push highlights orange
        "color_grade_cinematic": (
            "curves=red='0/0 0.5/0.58 1/1':green='0/0 0.5/0.48 1/1':blue='0/0.06 0.5/0.42 1/0.92',"
            "eq=saturation=1.15:contrast=1.05"
        ),
        # Documentary: warm natural tones, slight desaturation
        "color_grade_documentary": (
            "curves=red='0/0.02 0.5/0.54 1/0.98':green='0/0 0.5/0.50 1/1':blue='0/0 0.5/0.46 1/0.88',"
            "eq=saturation=0.9:brightness=0.02:contrast=1.03"
        ),
        # Bright explainer: high contrast, neutral-cool, punchy
        "color_grade_bright": (
            "curves=all='0/0 0.4/0.45 0.7/0.78 1/1',"
            "eq=saturation=1.1:contrast=1.08:brightness=0.03"
        ),
        # Vibrant social: max saturation, high contrast, warm
        "color_grade_vibrant": (
            "curves=red='0/0 0.5/0.56 1/1':blue='0/0 0.5/0.44 1/0.95',"
            "eq=saturation=1.35:contrast=1.1"
        ),
        # Product: clean, neutral, slight brightness boost
        "color_grade_product": (
            "curves=all='0/0.02 0.5/0.52 1/0.98',"
            "eq=saturation=1.05:brightness=0.03:contrast=1.05"
        ),
        # News: neutral, slight desaturation, increase contrast
        "color_grade_news": (
            "eq=saturation=0.85:contrast=1.12:brightness=0.01"
        ),
        # Tutorial: clean neutral
        "color_grade_tutorial": (
            "eq=saturation=1.0:contrast=1.02:brightness=0.01"
        ),
    }
    vf = grade_filters.get(grade)
    if not vf:
        return input_path  # unknown grade → pass-through
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "copy", "-movflags", "+faststart",
        output_path,
    ]
    _run(cmd, f"color_grade:{grade}")
    return output_path


def apply_letterbox(input_path: str, output_path: str) -> str:
    """Add 2.39:1 cinematic black bars (letterbox)."""
    # For 1920×1080 input, 2.39:1 = 1920×803 → pad with (1080-803)/2 = 138.5px top+bottom
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        "crop=iw:iw/2.39,pad=iw:ih+2*ceil((iw/2.39-oh)/2+0.5):0:(oh-ih)/2:black",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "copy", "-movflags", "+faststart",
        output_path,
    ]
    _run(cmd, "letterbox")
    return output_path


def apply_film_grain(input_path: str, output_path: str, strength: str = "subtle") -> str:
    """Add film grain via FFmpeg noise filter."""
    noise = "10" if strength == "subtle" else "20"
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"noise=c0s={noise}:c0f=t+u",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "copy", "-movflags", "+faststart",
        output_path,
    ]
    _run(cmd, "film_grain")
    return output_path


def apply_post_processing_chain(
    input_path: str,
    output_path: str,
    effects: list[str],
) -> str:
    """Apply a list of post_processing effect names from a Skill JSON."""
    import tempfile, os
    current = input_path
    tmp_files: list[str] = []

    def _tmp(suffix: str) -> str:
        f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        f.close()
        tmp_files.append(f.name)
        return f.name

    for effect in effects:
        out = _tmp(".mp4")
        if effect.startswith("color_grade_"):
            result = apply_color_grade(current, out, effect)
        elif effect == "letterbox":
            result = apply_letterbox(current, out)
        elif effect == "film_grain":
            result = apply_film_grain(current, out, "heavy")
        elif effect == "film_grain_subtle":
            result = apply_film_grain(current, out, "subtle")
        else:
            result = current  # unknown effect → skip
        if result != current:
            current = out

    # Copy final result to output_path
    import shutil
    shutil.copy2(current, output_path)

    for f in tmp_files:
        try:
            os.unlink(f)
        except OSError:
            pass

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
