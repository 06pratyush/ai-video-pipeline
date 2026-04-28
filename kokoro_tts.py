"""
Kokoro TTS Module
Converts narration text to audio files
"""
import numpy as np
import soundfile as sf
import os
from pathlib import Path

# Import Kokoro - run from kokoro's venv OR install in same venv
try:
    from kokoro import KPipeline
except ImportError:
    raise ImportError("Kokoro not installed. Run: pip install kokoro>=0.9.4")

class KokoroTTS:
    def __init__(self, voice='af_sarah', speed=1.0, lang='a'):
        """
        voice options:
          Female: af_heart, af_bella, af_sarah, af_nicole
          Male:   am_adam, am_michael
          British: bf_emma, bm_george
        """
        print(f"[TTS] Loading Kokoro pipeline (voice: {voice})...")
        self.pipeline = KPipeline(lang_code=lang)
        self.voice = voice
        self.speed = speed
        self.sample_rate = 24000
        print("[TTS] Kokoro ready.")

    def generate(self, text: str, output_path: str) -> str:
        """
        Generate audio from text.
        Returns path to saved .wav file.
        """
        print(f"[TTS] Generating audio for {len(text)} characters...")
        
        generator = self.pipeline(text, voice=self.voice, speed=self.speed)
        
        all_samples = []
        for i, (gs, ps, audio) in enumerate(generator):
            all_samples.append(audio)
        
        if not all_samples:
            raise RuntimeError("TTS generated no audio!")
        
        full_audio = np.concatenate(all_samples)
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        sf.write(output_path, full_audio, self.sample_rate)
        
        duration = len(full_audio) / self.sample_rate
        print(f"[TTS] Audio saved: {output_path} ({duration:.1f}s)")
        return output_path, duration


def get_audio_duration(filepath: str) -> float:
    """Get duration of a WAV file in seconds."""
    data, samplerate = sf.read(filepath)
    return len(data) / samplerate