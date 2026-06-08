"""
Long-form mode — splits scripts longer than ~90 seconds of narration into
multiple sub-projects that are rendered separately and concatenated at the end.

This keeps VRAM bounded (each chunk is a normal Wan2.1 batch) while supporting
videos of any length.
"""
import re
from typing import Optional

# Approximate words per minute for TTS playback at speed=1.0
WORDS_PER_MINUTE = 150
# Default chunk size in words (target ~60-90 seconds per chunk)
DEFAULT_CHUNK_WORDS = 180
# Minimum chunk size — anything shorter merges into the previous chunk
MIN_CHUNK_WORDS = 60


def estimate_duration_seconds(text: str, voice_speed: float = 1.0) -> float:
    """Rough TTS playback duration in seconds."""
    words = len(text.split())
    return (words / WORDS_PER_MINUTE) * 60 / voice_speed


def needs_chunking(script: str, threshold_seconds: float = 90.0) -> bool:
    return estimate_duration_seconds(script) > threshold_seconds


def split_into_chunks(
    script: str,
    chunk_words: int = DEFAULT_CHUNK_WORDS,
    min_words: int = MIN_CHUNK_WORDS,
) -> list[str]:
    """
    Split a script at sentence boundaries into chunks of ~chunk_words each.
    Merges trailing short chunks into the previous one.
    """
    # Split on sentence enders, keep the punctuation attached
    sentences = re.findall(r'[^.!?]+[.!?]+(?:\s+|$)', script.strip())
    if not sentences:
        # No sentence terminators — treat the whole thing as one chunk
        return [script.strip()] if script.strip() else []

    chunks: list[str] = []
    current: list[str] = []
    current_count = 0

    for sent in sentences:
        sent_words = len(sent.split())
        if current_count + sent_words > chunk_words and current:
            chunks.append("".join(current).strip())
            current = [sent]
            current_count = sent_words
        else:
            current.append(sent)
            current_count += sent_words

    if current:
        chunks.append("".join(current).strip())

    # Merge trailing short chunk into previous
    if len(chunks) >= 2 and len(chunks[-1].split()) < min_words:
        chunks[-2] = chunks[-2] + " " + chunks[-1]
        chunks.pop()

    return chunks


def plan_long_form(
    script: str,
    num_scenes_per_chunk: int = 3,
    chunk_words: int = DEFAULT_CHUNK_WORDS,
) -> list[dict]:
    """
    Return a list of chunk plans, each with script + scene_count + index.
    Used by the queue to spawn N sub-projects in sequence.
    """
    chunks = split_into_chunks(script, chunk_words=chunk_words)
    plans = []
    for i, chunk in enumerate(chunks):
        # Scale scene count by chunk length (longer chunks get more scenes)
        words = len(chunk.split())
        scaled_scenes = max(1, min(num_scenes_per_chunk, words // 40))
        plans.append({
            "index":       i,
            "total":       len(chunks),
            "script":      chunk,
            "num_scenes":  scaled_scenes,
            "est_duration_sec": estimate_duration_seconds(chunk),
        })
    return plans
