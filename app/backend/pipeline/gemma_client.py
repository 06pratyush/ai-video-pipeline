"""Gemma/Ollama interface — refactored from orchestrator.py call_gemma()."""
import json
import requests
from typing import Optional

OLLAMA_URL = "http://localhost:11434"


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
        response = self.call(prompt, system)
        try:
            clean = response.strip()
            if clean.startswith("```"):
                parts = clean.split("```")
                clean = parts[1] if len(parts) > 1 else clean
                if clean.lower().startswith("json"):
                    clean = clean[4:]
            prompts = json.loads(clean.strip())
            if not isinstance(prompts, list):
                raise ValueError("Response is not a list")
            return prompts
        except (json.JSONDecodeError, ValueError):
            fallback = (
                "Cinematic abstract visualization, flowing particles of light, "
                "deep blue and gold colors, slow camera movement, photorealistic, 4k"
            )
            return [fallback] * num_scenes

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
