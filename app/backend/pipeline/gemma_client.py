"""Gemma/Ollama interface — refactored from orchestrator.py call_gemma()."""
import json
import requests
from typing import Optional

OLLAMA_URL = "http://localhost:11434"

FALLBACK_STYLE = ("cinematic film still, soft natural lighting, slow camera movement, "
                  "rich detail, high quality animation")


def narration_prompts(narration: str, num_scenes: int, style: Optional[str] = None) -> list[str]:
    """Scene prompts without an LLM: split the narration into num_scenes runs of whole
    sentences, so each scene still shows its own part of the story."""
    import re
    num_scenes = max(1, int(num_scenes))
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narration.strip()) if s.strip()]
    if not sentences:
        sentences = [narration.strip() or "a beautiful landscape"]
    n = len(sentences)
    groups = [sentences[i * n // num_scenes:(i + 1) * n // num_scenes] for i in range(num_scenes)]
    out, last = [], sentences[0]
    for g in groups:
        last = " ".join(g) if g else last  # fewer sentences than scenes: reuse the previous one
        out.append(f"{last.rstrip('.!?')}, {style or FALLBACK_STYLE}")
    return out


class GemmaClient:
    def __init__(self, model: str = "gemma4:e4b", ollama_url: str = OLLAMA_URL):
        self.model = model
        self.base_url = ollama_url

    def call(self, prompt: str, system: str = "", temperature: float = 0.7) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": temperature, "top_p": 0.9},
        }
        try:
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
            resp.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Cannot connect to Ollama at {self.base_url}") from e
        return resp.json()["response"]

    def refine_narration(self, raw_script: str) -> str:
        system = (
            "You are a professional video scriptwriter. "
            "Polish the given script for voice narration. "
            "Keep it natural, engaging, and clear. "
            "Remove any stage directions or visual cues - output ONLY the spoken words. "
            "Do not add headers, labels, or commentary. Just the narration text."
        )
        prompt = (
            f"Refine this script for clear, engaging voice narration:\n\n"
            f"{raw_script}\n\n"
            f"Output only the refined narration text, nothing else."
        )
        return self.call(prompt, system)

    def generate_video_prompts(
        self,
        narration: str,
        num_scenes: int = 3,
        skill_template: Optional[str] = None,
    ) -> list[str]:
        system = (
            "You are an expert at writing prompts for AI video generation models. "
            "Generate vivid, detailed, cinematic prompts. "
            "Each prompt should describe: subject, action, setting, lighting, camera angle, style. "
            "Output ONLY a JSON array of strings, one per scene. No other text."
        )
        template_note = ""
        if skill_template:
            template_note = f"\nUse this style template for each prompt: {skill_template}\n"

        prompt = (
            f"Based on this narration, generate {num_scenes} video scene prompts.\n"
            f"Each scene should visually represent a different part of the narration.{template_note}\n\n"
            f"Narration:\n{narration}\n\n"
            f"Rules:\n"
            f"- Each prompt: 40-80 words\n"
            f"- Include: cinematic style, lighting quality, camera movement\n"
            f"- No text overlays, no faces unless specifically needed\n"
            f"- Style: high quality, 4k, photorealistic\n\n"
            f'Output as JSON array: ["prompt1", "prompt2", ...]'
        )
        try:
            response = self.call(prompt, system)
        except Exception as e:  # Ollama down or no model pulled: still render, from the narration
            print(f"[GEMMA] prompt generation unavailable ({e}); using the narration as prompts")
            return narration_prompts(narration, num_scenes, skill_template)
        try:
            clean = response.strip()
            if clean.startswith("```"):
                parts = clean.split("```")
                clean = parts[1] if len(parts) > 1 else clean
                if clean.lower().startswith("json"):
                    clean = clean[4:]
            prompts = json.loads(clean.strip())
            if not isinstance(prompts, list) or not all(isinstance(p, str) for p in prompts):
                raise ValueError("Response is not a list of strings")
            return prompts
        except (json.JSONDecodeError, ValueError):
            return narration_prompts(narration, num_scenes, skill_template)

    def list_models(self) -> list[dict]:
        """Return all models installed in Ollama."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            return resp.json().get("models", [])
        except Exception:
            return []

    def health_check(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
