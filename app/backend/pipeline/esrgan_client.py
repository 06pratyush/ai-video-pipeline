"""
Video upscaling — scales generated clips to higher resolution.
Primary: FFmpeg super2xbr + lanczos for 2x upscale (CPU, works everywhere).
Future: Replace with Real-ESRGAN ComfyUI node for GPU-accelerated quality.
"""
import subprocess
from pathlib import Path


def _run(cmd: list[str], label: str = "ESRGAN"):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[{label}] failed:\n{result.stderr}")
    return result


def upscale(
    input_path: str,
    output_path: str,
    target_width: int = 1920,
    target_height: int = 1080,
) -> str:
    """
    Upscale video to target resolution using FFmpeg super2xbr + lanczos.
    Returns output_path.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # super2xbr is FFmpeg's edge-preserving upscaler — better than plain bicubic
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        f"super2xbr,scale={target_width}:{target_height}:flags=lanczos",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "copy", "-movflags", "+faststart",
        output_path,
    ]
    try:
        _run(cmd, "upscale_super2xbr")
        return output_path
    except RuntimeError:
        # Fallback: plain lanczos scale
        cmd_simple = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"scale={target_width}:{target_height}:flags=lanczos",
            "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-c:a", "copy", "-movflags", "+faststart",
            output_path,
        ]
        _run(cmd_simple, "upscale_lanczos")
        return output_path


def upscale_2x(input_path: str, output_path: str) -> str:
    """Convenience: 2x upscale to 1920×1080."""
    return upscale(input_path, output_path, 1920, 1080)
