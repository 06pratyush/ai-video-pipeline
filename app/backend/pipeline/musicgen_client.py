"""
MusicGen background music generation.
Uses Meta's audiocraft library when available; degrades gracefully when absent.
"""
from pathlib import Path
from typing import Optional

try:
    from audiocraft.models import MusicGen as _MusicGen
    from audiocraft.data.audio import audio_write as _audio_write
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_model_cache: dict[str, "_MusicGen"] = {}

# Maps skill music_mood → MusicGen text description
MOOD_PROMPTS: dict[str, str] = {
    "ambient_score":       "calm ambient documentary score, orchestral, slow, cinematic, no percussion",
    "emotional_score":     "emotional cinematic score, strings, piano, slow build, dramatic, film music",
    "upbeat":              "upbeat background music, light and energetic, positive, pop instrumental",
    "upbeat_energetic":    "high energy upbeat music, electronic, punchy beat, social media, vibrant",
    "news_music":          "news broadcast background music, corporate, neutral, modern, subtle",
    "tutorial_bg":         "calm focused background music, lo-fi, subtle, not distracting",
    "dramatic":            "dramatic orchestral score, tension, cinematic, dark, intense",
}

DEFAULT_PROMPT = "calm instrumental background music, neutral, subtle"


def is_available() -> bool:
    return _AVAILABLE


def _get_model(size: str = "small") -> "_MusicGen":
    if size not in _model_cache:
        if not _AVAILABLE:
            raise ImportError(
                "audiocraft not installed. Run: pip install audiocraft"
            )
        _model_cache[size] = _MusicGen.get_pretrained(size)
    return _model_cache[size]


def generate_music(
    mood: str,
    duration: float,
    output_path: str,
    model_size: str = "small",
) -> Optional[str]:
    """
    Generate background music matching the given mood for `duration` seconds.
    Returns output_path on success, None if audiocraft is unavailable.
    """
    if not _AVAILABLE:
        return None

    prompt = MOOD_PROMPTS.get(mood, DEFAULT_PROMPT)
    model = _get_model(model_size)
    model.set_generation_params(duration=min(duration, 30.0))  # MusicGen cap

    import torch
    descriptions = [prompt]
    with torch.no_grad():
        wav = model.generate(descriptions)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    # audio_write expects path without extension
    stem = str(Path(output_path).with_suffix(""))
    _audio_write(stem, wav[0].cpu(), model.sample_rate, strategy="loudness")

    # audio_write adds .wav extension
    written = Path(stem + ".wav")
    if written.exists() and str(written) != output_path:
        written.rename(output_path)
    return output_path
