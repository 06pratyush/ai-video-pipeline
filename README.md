# AI Video Studio

> Generate cinematic videos from text — fully local, fully autonomous, fully yours.

A desktop application that turns scripts into narrated, professionally-edited videos using local AI models. No cloud, no subscriptions, no API keys. Your machine is the only computer in the loop.

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Electron](https://img.shields.io/badge/electron-31-47848f.svg)](https://www.electronjs.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

---

## What it does

Write a script. Pick a Skill. Hit Generate. Five to fifteen minutes later you have a finished MP4 with narration, visuals, music, subtitles, and color grading — ready to post.

```
Your script
   │
   ├─ Gemma (Ollama)      ── refines narration + writes scene prompts
   ├─ Kokoro TTS          ── synthesizes voice audio
   ├─ Wan2.1 (ComfyUI)    ── generates video clips on your GPU
   ├─ MusicGen            ── composes background music (optional)
   ├─ Whisper             ── transcribes for burned-in subtitles (optional)
   ├─ minterpolate / RIFE ── interpolates to smooth 30fps (optional)
   ├─ super2xbr / ESRGAN  ── upscales to 1080p (optional)
   └─ FFmpeg              ── color grade, letterbox, film grain, final mux
        │
        ▼
   final.mp4
```

---

## Install

### Option A — Download a release (recommended)

Grab the installer for your platform from the [Releases page](https://github.com/06pratyush/ai-video-pipeline/releases):

| Platform | File |
|----------|------|
| Windows  | `AI-Video-Studio-1.0.0-x64.exe` (NSIS installer) or `AI-Video-Studio-1.0.0-x64.exe` (portable) |
| Linux    | `AI-Video-Studio-1.0.0-x64.AppImage` or `.deb` |
| macOS    | `AI-Video-Studio-1.0.0-arm64.dmg` (Apple Silicon) or `x64.dmg` (Intel) |

On first launch, the app detects your hardware, downloads the right models for your GPU tier, and gets you to a working state in 10–20 minutes. After that, video generation takes ~5–15 minutes per project depending on scene count and quality settings.

### Option B — Clone and run from source

```bash
git clone https://github.com/06pratyush/ai-video-pipeline.git
cd ai-video-pipeline

# Windows
start.bat

# Linux / macOS
./start.sh
```

The launcher checks for Python 3.10+ and Node.js 18+, then runs the same bootstrap process as the installer.

---

## System Requirements

|              | Minimum                    | Recommended                |
|--------------|----------------------------|----------------------------|
| **GPU**      | NVIDIA, 8 GB VRAM (Wan2.1 1.3B) | NVIDIA, 16 GB+ VRAM (Wan2.1 14B) |
| **RAM**      | 16 GB                      | 32 GB                      |
| **Disk**     | 30 GB free                 | 100 GB free                |
| **OS**       | Windows 10, Ubuntu 22.04, macOS 12 | Windows 11, Ubuntu 24.04, macOS 14 |
| **Python**   | 3.10                       | 3.11                       |
| **Node.js**  | 18 LTS                     | 20 LTS                     |

CPU-only mode runs but is very slow (~10× slower than CUDA). AMD GPUs aren't currently supported by Wan2.1 — track [this issue](https://github.com/Wan-AI/Wan2.1/issues) for ROCm progress.

---

## Quick Start

After installation, the app shows a five-step onboarding card. Dismiss it and:

1. **Click + New Project** in the sidebar
2. **Paste your script** in the Script tab — anything from one sentence to several paragraphs
3. **Pick a Skill** — Documentary, Cinematic Story, Explainer, Social Short, Product Showcase, Tutorial, or News Brief. The Skill bundles voice, pacing, visual style, music mood, and post-processing into one preset.
4. **Switch to Render tab** and toggle the quality options you want (subtitles, music, frame interpolation, upscaling)
5. **Hit Generate Video** — the queue strip at the bottom shows live progress through 8 stages

When the render finishes, click `⬇ Download MP4` to save it, or `Show in folder` to open the output directory.

---

## Skills

A Skill is a preset that determines the entire look and feel of the output. The default pack ships seven:

| Skill | Voice | Pacing | Aspect | Best For |
|-------|-------|--------|--------|----------|
| **Documentary**     | George (British male) | Slow   | 16:9 | Long-form narration, nature, history |
| **Explainer**       | Sarah (American female) | Medium | 16:9 | Concept videos, tutorials |
| **Product Showcase** | Michael (American male) | Medium | 1:1  | Marketing, demos |
| **Cinematic Story** | George (British male) | Slow   | 16:9 | Storytelling, dramatic content |
| **Social Short**    | Heart (American female) | Fast   | 9:16 | TikTok, Reels, Shorts |
| **Tutorial**        | Nicole (American female) | Medium | 16:9 | How-to content |
| **News Brief**      | Adam (American male) | Fast   | 16:9 | News updates, recaps |

Each Skill bundles a prompt template, voice + speed, scene pacing hint, music mood, and post-processing chain (color grade, film grain, letterbox). Custom Skills are JSON files in `app/skills/` — duplicate one to make your own.

---

## Quality Settings

The Render tab exposes four toggles independent of the Skill:

| Toggle | Backend Module | Cost |
|--------|----------------|------|
| **Subtitles**          | faster-whisper transcription → FFmpeg subtitle burn | ~10s per minute of audio |
| **Background Music**   | MusicGen mood-matched composition + auto-ducking mix | ~30s per scene |
| **Frame Interpolation** | FFmpeg minterpolate (RIFE-compatible swap-in) | +30% render time |
| **Upscaling**          | FFmpeg super2xbr+lanczos (Real-ESRGAN swap-in) | +20% render time |

Skills auto-enable some toggles by default (e.g. Social Short turns on subtitles because mobile viewers watch muted).

---

## Templates, Versions, Batch

After your first successful render, three workflow accelerators become useful:

**Templates** — `Save as Template` on the Render tab captures the project's skill, voice, scene count, and quality settings as a reusable preset. Open the Templates browser from the sidebar to apply one to a new project in two clicks.

**Version History** — every successful generation is automatically snapshotted with the full script, scene prompts, and a copy of the final MP4. Click `Version History` on the Render tab to compare past renders or restore an earlier configuration.

**Batch Generation** — the Batch button in the sidebar opens a multi-row editor. Paste 10 scripts at once, optionally apply a template to all of them, and queue them up. The pipeline runs them sequentially overnight.

---

## Architecture

Three-tier system designed so each layer can evolve independently:

```
┌────────────────────────────────────────────────────────┐
│  ELECTRON FRONTEND        React + Zustand + Tailwind   │
│  ─ project library, editor, queue, model browser       │
│  ─ real-time progress via WebSocket                    │
└────────────────────────┬───────────────────────────────┘
                         │ REST + WS @ localhost:7860
                         ▼
┌────────────────────────────────────────────────────────┐
│  PYTHON BACKEND DAEMON    FastAPI + SQLAlchemy          │
│  ─ service orchestration, generation queue, cache       │
│  ─ VRAM-aware model lifecycle                          │
│  ─ scene cache (sha256 of prompt+seed+model+res)       │
└────────────┬────────────────┬──────────────┬───────────┘
             ▼                ▼              ▼
        ┌────────┐       ┌─────────┐     ┌─────────┐
        │ Ollama │       │ ComfyUI │     │ FFmpeg  │
        │ Gemma  │       │ Wan2.1  │     │ Kokoro  │
        └────────┘       └─────────┘     └─────────┘
```

Full design rationale lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The roadmap that drove the build is in [`AI_VIDEO_STUDIO_ROADMAP.md`](AI_VIDEO_STUDIO_ROADMAP.md).

---

## Build from source

Build the desktop installers yourself if you don't want to use the GitHub releases:

```bash
cd app/frontend
npm install
npm run build:win     # Windows: NSIS .exe + portable .exe
npm run build:linux   # Linux: AppImage + .deb
npm run build:mac     # macOS: DMG + zip (x64 + arm64)
npm run build:all     # All three platforms (requires macOS host for proper signing)
```

Artifacts land in `app/frontend/release/`. See [`docs/BUILDING.md`](docs/BUILDING.md) for the full procedure including code signing and notarization.

---

## Troubleshooting

**Setup screen stalls on PyTorch install**  
Slow disk + 2.5GB download. Check the log viewer at the bottom of the setup screen. If it's been more than 20 minutes, retry from the setup screen's retry button.

**"Cannot connect to Ollama" during generation**  
Ollama crashed or wasn't started. The app tries to start it automatically — open the Model Browser to verify Ollama models are listed. If empty, run `ollama serve` in a terminal.

**Backend status shows "ComfyUI: not running"**  
ComfyUI starts lazily on first generation. If it fails to start, check that `app/runtime/comfyui/` exists and contains a `main.py`. Re-run the bootstrap if not.

**"CUDA out of memory" mid-generation**  
The VRAM manager should have downgraded to a smaller model — check the queue progress message for "Used wan2.1-1.3b instead of wan2.1-14b". If still failing, close other GPU apps (Chrome with hardware accel uses 1–2 GB), or restart the daemon.

**Black bars / wrong aspect ratio in output**  
The Skill controls aspect ratio. Social Short → 9:16, all others → 16:9 by default. Change the Skill or duplicate one and edit the JSON.

**Subtitles look misaligned**  
Whisper is mis-transcribing the audio. Try regenerating audio with a different voice (some skills' default voices Whisper handles better than others).

More troubleshooting in [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

---

## Contributing

Contributions welcome — especially:

- New Skills (just add a JSON file to `app/skills/`)
- Additional FFmpeg post-processing presets in `pipeline/ffmpeg_merger.py`
- Real-ESRGAN and RIFE ComfyUI node integrations to replace the FFmpeg fallbacks
- Voice cloning via XTTS / Tortoise TTS
- AMD ROCm support for Wan2.1
- Mobile companion app for triggering renders from a phone

Process:

1. Open an issue describing the change before starting large work
2. Fork → feature branch → PR against `main`
3. Run `npm run typecheck` in `app/frontend/` and ensure the backend boots with `python -m uvicorn app.backend.main:app`
4. Include a brief test plan in the PR description

See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) for code style and architectural conventions.

---

## License

[MIT](LICENSE) — use it, modify it, distribute it freely. Attribution appreciated but not required.

---

## Acknowledgements

Built on the shoulders of:

- **[Wan2.1](https://github.com/Wan-AI/Wan2.1)** — text-to-video model
- **[Kokoro TTS](https://github.com/hexgrad/kokoro)** — local high-quality text-to-speech
- **[ComfyUI](https://github.com/comfyanonymous/ComfyUI)** — node-based runtime for diffusion models
- **[Ollama](https://ollama.com)** — frictionless local LLM serving
- **[Gemma](https://ai.google.dev/gemma)** — Google DeepMind's open language model
- **[faster-whisper](https://github.com/SYSTRAN/faster-whisper)** — CTranslate2-accelerated transcription
- **[MusicGen](https://github.com/facebookresearch/audiocraft)** — Meta's text-to-music model
- **[FFmpeg](https://ffmpeg.org)** — the indispensable multimedia framework
- **[Electron](https://www.electronjs.org/)** + **[React](https://react.dev/)** + **[Vite](https://vitejs.dev/)** + **[FastAPI](https://fastapi.tiangolo.com/)** + **[Tailwind CSS](https://tailwindcss.com/)**

---

*Built for creators who want full control over their AI content pipeline — no subscriptions, no rate limits, no data leaving your machine.*
