"""
AI Video Pipeline Orchestrator
Connects: Gemma (via Ollama) -> Kokoro TTS -> Wan2.1 (ComfyUI) -> FFmpeg

Usage:
    python orchestrator.py --script my_script.txt --topic "quantum computing"
"""

import argparse
import json
import os
import sys
import time
import subprocess
import requests
from pathlib import Path

from kokoro_tts import KokoroTTS
from wan_client import WanVideoClient
from ffmpeg_merger import merge_video_audio, convert_for_instagram, convert_for_youtube

# ─── Configuration ────────────────────────────────────────────────────────────

OLLAMA_URL  = "http://localhost:11434"
GEMMA_MODEL = "gemma4:e4b"      # Change to "gemma3" if that is what you have pulled

OUTPUT_DIR  = "outputs"
AUDIO_DIR   = f"{OUTPUT_DIR}/audio"
VIDEO_DIR   = f"{OUTPUT_DIR}/video"
FINAL_DIR   = f"{OUTPUT_DIR}/final"

# ─── Gemma / Ollama Interface ─────────────────────────────────────────────────

def call_gemma(prompt, system=""):
    """Send a prompt to Gemma via Ollama API."""
    payload = {
        "model": GEMMA_MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9
        }
    }

    print(f"[GEMMA] Sending prompt ({len(prompt)} chars)...")

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("[ERROR] Cannot connect to Ollama. Is 'ollama serve' running?")
        sys.exit(1)

    result = response.json()["response"]
    print(f"[GEMMA] Response received ({len(result)} chars)")
    return result


def refine_narration(raw_script):
    """Use Gemma to polish the narration script."""
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

    return call_gemma(prompt, system)


def generate_video_prompts(narration, num_scenes=3):
    """Use Gemma to generate detailed video prompts for each scene."""
    system = (
        "You are an expert at writing prompts for AI video generation models. "
        "Generate vivid, detailed, cinematic prompts. "
        "Each prompt should describe: subject, action, setting, lighting, camera angle, style. "
        "Output ONLY a JSON array of strings, one per scene. No other text."
    )

    prompt = (
        f"Based on this narration, generate {num_scenes} video scene prompts.\n"
        f"Each scene should visually represent a different part of the narration.\n\n"
        f"Narration:\n{narration}\n\n"
        f"Rules:\n"
        f"- Each prompt: 40-80 words\n"
        f"- Include: cinematic style, lighting quality, camera movement\n"
        f"- No text overlays, no faces unless specifically needed\n"
        f"- Style: high quality, 4k, photorealistic\n\n"
        f'Output as JSON array: ["prompt1", "prompt2", "prompt3"]'
    )

    response = call_gemma(prompt, system)

    # Parse the JSON array from Gemma's response
    try:
        clean = response.strip()
        # Strip markdown code fences if Gemma adds them
        if clean.startswith("```"):
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else clean
            if clean.lower().startswith("json"):
                clean = clean[4:]
        prompts = json.loads(clean.strip())
        if not isinstance(prompts, list):
            raise ValueError("Response is not a list")
        print(f"[GEMMA] Generated {len(prompts)} video prompts")
        return prompts

    except (json.JSONDecodeError, ValueError) as e:
        print(f"[GEMMA] JSON parse failed, using fallback. Error: {e}")
        fallback = (
            "Cinematic abstract visualization, flowing particles of light, "
            "deep blue and gold colors, slow camera movement, photorealistic, 4k"
        )
        return [fallback] * num_scenes


# ─── Folder Setup ──────────────────────────────────────────────────────────────

def create_output_folders():
    """Create all output folders if they do not exist."""
    for folder in [AUDIO_DIR, VIDEO_DIR, FINAL_DIR]:
        Path(folder).mkdir(parents=True, exist_ok=True)


# ─── Main Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(raw_script, topic,
                 voice="af_sarah",
                 num_scenes=2,
                 target="both",
                 skip_gemma_refine=False):
    """
    Full pipeline execution.

    Args:
        raw_script        : Your input narration text
        topic             : Label used for output file naming
        voice             : Kokoro voice ID
        num_scenes        : Number of video clips to generate
        target            : 'instagram', 'youtube', or 'both'
        skip_gemma_refine : If True, skip Gemma and use raw_script as-is
    """

    create_output_folders()

    timestamp  = int(time.time())
    safe_topic = topic.replace(" ", "_").lower()[:30]

    print("\n" + "=" * 60)
    print("  AI VIDEO PIPELINE STARTING")
    print("=" * 60)

    # ── Step 1: Refine Script with Gemma ──────────────────────────
    print("\n[STEP 1/5] Refining narration with Gemma...")

    if skip_gemma_refine:
        narration = raw_script
        print("[STEP 1/5] Skipped (using raw script as-is)")
    else:
        narration = refine_narration(raw_script)

    print(f"\n--- Narration Preview ---\n{narration[:300]}\n")

    # ── Step 2: Generate Video Prompts ────────────────────────────
    print("[STEP 2/5] Generating video prompts with Gemma...")
    video_prompts = generate_video_prompts(narration, num_scenes)

    for i, p in enumerate(video_prompts, 1):
        print(f"  Scene {i}: {p[:80]}...")

    # ── Step 3: Generate Audio with Kokoro ────────────────────────
    print(f"\n[STEP 3/5] Generating voice audio with Kokoro (voice: {voice})...")

    tts        = KokoroTTS(voice=voice)
    audio_path = f"{AUDIO_DIR}/{safe_topic}_{timestamp}.wav"
    audio_path, audio_duration = tts.generate(narration, audio_path)

    print(f"  Audio duration: {audio_duration:.1f} seconds")

    # ── Step 4: Generate Video Clips with Wan2.1 ──────────────────
    print(f"\n[STEP 4/5] Generating video clips with Wan2.1 (ComfyUI)...")
    print("  NOTE: ComfyUI must be running at http://localhost:8188")

    wan         = WanVideoClient("wan_workflow_api.json")
    video_clips = []

    for i, prompt in enumerate(video_prompts):
        print(f"\n  Generating scene {i + 1}/{num_scenes}...")
        clip_path = wan.generate(
            prompt=prompt,
            output_dir=VIDEO_DIR,
            width=832,
            height=480,
            num_frames=81,   # ~5 seconds at 16fps
            steps=20
        )
        video_clips.append(clip_path)

    # ── Step 5: Merge with FFmpeg ──────────────────────────────────
    print(f"\n[STEP 5/5] Merging video and audio with FFmpeg...")

    # If multiple clips, concatenate them first
    if len(video_clips) > 1:
        concat_list  = f"{VIDEO_DIR}/concat_{timestamp}.txt"
        concat_video = f"{VIDEO_DIR}/concat_{timestamp}.mp4"

        with open(concat_list, "w") as f:
            for clip in video_clips:
                f.write(f"file '{os.path.abspath(clip)}'\n")

        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", concat_list, "-c", "copy", concat_video],
            check=True,
            capture_output=True
        )
        source_video = concat_video

    else:
        source_video = video_clips[0]

    # Merge video + audio
    merged_path = f"{FINAL_DIR}/{safe_topic}_{timestamp}_merged.mp4"
    merge_video_audio(source_video, audio_path, merged_path, audio_duration)

    # Export for target platforms
    results = {}

    if target in ("instagram", "both"):
        ig_path = f"{FINAL_DIR}/{safe_topic}_{timestamp}_instagram.mp4"
        convert_for_instagram(merged_path, ig_path, format="reel")
        results["instagram"] = ig_path

    if target in ("youtube", "both"):
        yt_path = f"{FINAL_DIR}/{safe_topic}_{timestamp}_youtube.mp4"
        convert_for_youtube(merged_path, yt_path)
        results["youtube"] = yt_path

    # ── Done ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE!")
    print("=" * 60)
    print(f"\n  Topic  : {topic}")
    print(f"  Audio  : {audio_duration:.1f} seconds")
    print(f"  Scenes : {num_scenes}")
    print(f"\n  Output files:")

    for platform, path in results.items():
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"    {platform.upper()}: {path} ({size_mb:.1f} MB)")

    return results


# ─── CLI Entry Point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Video Pipeline: Script -> Voice -> Video -> Final MP4"
    )

    parser.add_argument("--script", type=str,
                        help="Path to your script .txt file")
    parser.add_argument("--text", type=str,
                        help="Direct script text (use instead of --script)")
    parser.add_argument("--topic", type=str, required=True,
                        help="Topic label for output file naming")
    parser.add_argument("--voice", type=str, default="af_sarah",
                        choices=["af_sarah", "af_bella", "af_heart", "af_nicole",
                                 "am_adam", "am_michael", "bf_emma", "bm_george"],
                        help="Kokoro voice for narration (default: af_sarah)")
    parser.add_argument("--scenes", type=int, default=2,
                        help="Number of video scenes to generate (default: 2)")
    parser.add_argument("--target", type=str, default="both",
                        choices=["instagram", "youtube", "both"],
                        help="Output platform format (default: both)")
    parser.add_argument("--no-refine", action="store_true",
                        help="Skip Gemma script refinement, use script as-is")

    args = parser.parse_args()

    # Validate: must provide either --script or --text
    if not args.script and not args.text:
        print("[ERROR] You must provide either --script <filepath> or --text <content>")
        sys.exit(1)

    # Load script text
    if args.script:
        script_file = Path(args.script)
        if not script_file.exists():
            print(f"[ERROR] Script file not found: {args.script}")
            sys.exit(1)
        script_text = script_file.read_text(encoding="utf-8")
    else:
        script_text = args.text

    if not script_text.strip():
        print("[ERROR] Script is empty. Please provide some content.")
        sys.exit(1)

    print(f"[INFO] Script loaded ({len(script_text)} characters)")
    print(f"[INFO] Topic   : {args.topic}")
    print(f"[INFO] Voice   : {args.voice}")
    print(f"[INFO] Scenes  : {args.scenes}")
    print(f"[INFO] Target  : {args.target}")

    # Run the pipeline
    run_pipeline(
        raw_script=script_text,
        topic=args.topic,
        voice=args.voice,
        num_scenes=args.scenes,
        target=args.target,
        skip_gemma_refine=args.no_refine
    )