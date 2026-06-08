"""
XTTS voice cloning — turn a short reference clip into a custom voice.
Wraps Coqui's XTTS v2 via the TTS package when available; degrades cleanly.
"""
from pathlib import Path
from typing import Optional

try:
    from TTS.api import TTS as _TTS
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_model_cache: dict[str, "_TTS"] = {}


def is_available() -> bool:
    return _AVAILABLE


def _get_model(model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2") -> "_TTS":
    if model_name not in _model_cache:
        if not _AVAILABLE:
            raise ImportError("TTS not installed. Run: pip install TTS")
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model_cache[model_name] = _TTS(model_name).to(device)
    return _model_cache[model_name]


def clone_voice(
    text: str,
    reference_wav: str,
    output_path: str,
    language: str = "en",
) -> Optional[tuple[str, float]]:
    """
    Generate speech in the voice of `reference_wav`.

    reference_wav: 6-30 seconds of clean voice audio at any sample rate.
    Returns (output_path, duration_seconds) or None if XTTS is unavailable.
    """
    if not _AVAILABLE:
        return None

    if not Path(reference_wav).exists():
        raise FileNotFoundError(f"Reference voice not found: {reference_wav}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    model = _get_model()
    model.tts_to_file(
        text=text,
        speaker_wav=reference_wav,
        language=language,
        file_path=output_path,
    )

    import soundfile as sf
    data, sr = sf.read(output_path)
    duration = len(data) / sr
    return output_path, duration


def list_cached_voices(voices_dir: str = "app/voices") -> list[dict]:
    """List user-uploaded reference voice clips."""
    p = Path(voices_dir)
    if not p.exists():
        return []
    out: list[dict] = []
    for f in sorted(p.glob("*.wav")):
        out.append({
            "id":       f.stem,
            "name":     f.stem.replace("_", " ").title(),
            "path":     str(f),
            "size_kb":  f.stat().st_size // 1024,
        })
    return out
