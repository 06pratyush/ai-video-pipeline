"""
Frame interpolation — bumps video from native fps to 30fps for smoothness.
Primary: FFmpeg minterpolate filter (CPU, works everywhere, no model download).
Future: Replace with RIFE via ComfyUI for GPU-accelerated quality.
"""
import subprocess
from pathlib import Path


def _run(cmd: list[str], label: str = "RIFE"):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[{label}] failed:\n{result.stderr}")
    return result


def interpolate_to_fps(
    input_path: str,
    output_path: str,
    target_fps: int = 30,
) -> str:
    """
    Interpolate video to target_fps using FFmpeg minterpolate.
    Falls back to simple fps-doubling if minterpolate is too slow.
    Returns output_path.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # minterpolate with blend mode — good quality, moderate speed
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        f"minterpolate=fps={target_fps}:mi_mode=blend",
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "copy", "-movflags", "+faststart",
        output_path,
    ]
    try:
        _run(cmd, "interpolate_minterpolate")
        return output_path
    except RuntimeError:
        # Fallback: just set fps without interpolation
        cmd_simple = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"fps={target_fps}",
            "-c:v", "libx264", "-crf", "20", "-preset", "fast",
            "-c:a", "copy", "-movflags", "+faststart",
            output_path,
        ]
        _run(cmd_simple, "interpolate_fps_set")
        return output_path
