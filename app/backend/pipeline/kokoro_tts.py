"""Kokoro TTS pipeline wrapper — adapted from root kokoro_tts.py."""
import numpy as np
import soundfile as sf
from pathlib import Path

try:
    from kokoro import KPipeline
except ImportError:
    KPipeline = None  # deferred — will raise at generate() time if missing


VOICES = [
    "af_heart", "af_bella", "af_sarah", "af_nicole",
    "am_adam", "am_michael", "bf_emma", "bm_george",
]


class KokoroTTSClient:
    _instance = None  # module-level singleton to avoid reloading the model

    def __init__(self, voice: str = "af_sarah", speed: float = 1.0, lang: str = "a"):
        if KPipeline is None:
            raise ImportError("Kokoro not installed. Run: pip install kokoro>=0.9.4")
        self.voice = voice
        self.speed = speed
        self.sample_rate = 24000
        self._pipeline = KPipeline(lang_code=lang)

    def generate(self, text: str, output_path: str) -> tuple[str, float]:
        """Generate WAV from text. Returns (output_path, duration_seconds)."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        generator = self._pipeline(text, voice=self.voice, speed=self.speed)
        chunks = [audio for _, _, audio in generator]
        if not chunks:
            raise RuntimeError("TTS generated no audio")
        full_audio = np.concatenate(chunks)
        sf.write(output_path, full_audio, self.sample_rate)
        duration = len(full_audio) / self.sample_rate
        return output_path, duration

    @staticmethod
    def get_audio_duration(filepath: str) -> float:
        data, sr = sf.read(filepath)
        return len(data) / sr
