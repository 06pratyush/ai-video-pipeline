"""Whisper transcription — generates SRT subtitles from audio via faster-whisper."""
from pathlib import Path
from typing import Optional

try:
    from faster_whisper import WhisperModel as _WhisperModel
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_model_cache: dict[str, "_WhisperModel"] = {}


def is_available() -> bool:
    return _AVAILABLE


def _get_model(size: str = "base") -> "_WhisperModel":
    if size not in _model_cache:
        if not _AVAILABLE:
            raise ImportError("faster-whisper not installed. Run: pip install faster-whisper")
        _model_cache[size] = _WhisperModel(size, device="auto", compute_type="int8")
    return _model_cache[size]


def _seconds_to_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe_to_srt(
    audio_path: str,
    model_size: str = "base",
    language: Optional[str] = None,
) -> str:
    """
    Transcribe audio and return an SRT-formatted subtitle string.
    Raises ImportError if faster-whisper is not installed.
    """
    model = _get_model(model_size)
    segments, _ = model.transcribe(
        audio_path,
        language=language,
        word_timestamps=False,
        vad_filter=True,
    )
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        start = _seconds_to_srt_time(seg.start)
        end   = _seconds_to_srt_time(seg.end)
        text  = seg.text.strip()
        if text:
            lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def transcribe_to_srt_file(
    audio_path: str,
    output_srt_path: str,
    model_size: str = "base",
    language: Optional[str] = None,
) -> str:
    """Transcribe audio and write SRT file. Returns path."""
    srt_content = transcribe_to_srt(audio_path, model_size, language)
    Path(output_srt_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_srt_path).write_text(srt_content, encoding="utf-8")
    return output_srt_path
