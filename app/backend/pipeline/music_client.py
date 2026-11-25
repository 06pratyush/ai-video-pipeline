"""Background music on the GPU with ACE-Step v1 3.5B (Apache-2.0) in ComfyUI.

One instrumental bed per film, as long as the film, from a mood/style prompt. Replaces
MusicGen as the default: MusicGen's weights are CC-BY-NC (no monetised videos) and
audiocraft is hard to install on Windows. ``musicgen_client`` remains as a fallback.
"""
from __future__ import annotations

from pathlib import Path

from app.backend.pipeline.comfy_client import (
    AUDIO_EXT, COMFYUI_URL, ComfyClient, load_workflow, require_nodes, set_inputs,
)

WORKFLOW = "ace_step_music.json"

# Same moods the skills already use for MusicGen, phrased as ACE-Step style tags.
MOOD_TAGS: dict[str, str] = {
    "ambient_score": "ambient, cinematic, orchestral, soft strings, slow, calm, instrumental",
    "emotional_score": "cinematic, emotional, strings, piano, slow build, film score, instrumental",
    "upbeat": "upbeat, light pop, acoustic guitar, claps, positive, instrumental",
    "upbeat_energetic": "energetic, electronic, punchy drums, bright synth, instrumental",
    "news_music": "corporate, news, pulsing synth, modern, neutral, instrumental",
    "tutorial_bg": "lo-fi, chill, soft keys, mellow beat, instrumental",
    "dramatic": "epic, orchestral, dramatic, choir, taiko drums, dark, cinematic, instrumental",
}


def build_workflow(template: dict, tags: str, seconds: float, seed: int = 0, steps: int = 50) -> dict:
    return set_inputs(template, {
        "positive": {"tags": tags, "lyrics": "[inst]"},
        "latent": {"seconds": round(max(5.0, min(float(seconds), 600.0)), 1)},
        "sampler": {"seed": int(seed), "steps": int(steps)},
    })


class MusicClient:
    def __init__(self, comfyui_url: str = COMFYUI_URL):
        self.comfy = ComfyClient(comfyui_url)
        self.template = load_workflow(WORKFLOW)
        require_nodes(self.template, "positive", "latent", "sampler", "save", name=WORKFLOW)

    def generate(self, tags_or_mood: str, seconds: float, dest: str | Path, seed: int = 0,
                 steps: int = 50, timeout_s: float = 1800) -> Path:
        tags = MOOD_TAGS.get(tags_or_mood, tags_or_mood)
        wf = build_workflow(self.template, tags, seconds, seed, steps)
        return self.comfy.run(wf, dest, AUDIO_EXT, timeout_s)
