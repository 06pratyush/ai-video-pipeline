# AI Video Studio — Full Planning & Execution Roadmap

> Evolving the AI Video Pipeline from a CLI tool into a professional, zero-friction desktop application — fully local, fully autonomous, fully yours.

---

## Table of Contents

1. [Vision & Design Philosophy](#1-vision--design-philosophy)
2. [Current State Analysis](#2-current-state-analysis)
3. [The New Architecture](#3-the-new-architecture)
4. [First-Run Experience](#4-first-run-experience)
5. [The Onboarding Card](#5-the-onboarding-card)
6. [The Main Interface](#6-the-main-interface)
7. [The Skills System](#7-the-skills-system)
8. [Capabilities Expansion](#8-capabilities-expansion)
9. [Model Management Layer](#9-model-management-layer)
10. [Optimization Engine](#10-optimization-engine)
11. [Quality & Output Pipeline](#11-quality--output-pipeline)
12. [Project & Template System](#12-project--template-system)
13. [Technical Stack](#13-technical-stack)
14. [File Structure](#14-file-structure)
15. [Implementation Roadmap](#15-implementation-roadmap)
16. [Risks & Mitigations](#16-risks--mitigations)
17. [Future Extensions](#17-future-extensions)

---

## 1. Vision & Design Philosophy

The current pipeline works — but it forces the user to behave like a developer. They juggle three terminals, edit Python files to fix model names, hand-export workflow JSONs from ComfyUI, decipher cryptic CUDA errors, and pray the venv activates correctly. That's the wrong abstraction for a creative tool.

**The new vision:** the user clones the repo, double-clicks one icon, and within five minutes is watching their first AI-generated video render. Everything in between — dependency installs, model downloads, service orchestration, error recovery, GPU optimization — happens silently. The terminal is dead. Long live the interface.

### Design Principles

**Invisible Complexity** — every technical decision the current CLI exposes must be hidden by default, with a power-user mode for those who want to dive deep. The default user should never see the words "ComfyUI," "VRAM," or "venv."

**Local-First, Always** — no cloud calls. No telemetry. No license servers. The user's machine is the only computer in the loop. This is non-negotiable and is the project's core differentiator.

**Progressive Disclosure** — show the basic interface first. Reveal advanced controls only when the user signals they want them. A novice should feel empowered; an expert should feel unconstrained.

**Honest Feedback** — when something takes 8 minutes, show a real-time progress bar with stage indicators, not a spinner. When something fails, show what failed and how to fix it in plain language, not a Python traceback.

**Aesthetic of Capability** — the interface should signal seriousness. Inspired by Linear's discipline and Raycast's keyboard-first interaction, with the dense information layout of professional tools like DaVinci Resolve. Dark theme by default. Monospace where it earns its place. Generous whitespace.

---

## 2. Current State Analysis

### What Exists Today

The current build (`orchestrator.py`, `wan_client.py`, `kokoro_tts.py`, `ffmpeg_merger.py`) is a working CLI pipeline that does the core technical job correctly. The architecture is clean — each module handles one concern and exposes a clear function-level API. That's good. We keep all of it.

### What's Missing

**No installer.** The user manually creates venvs, installs PyTorch with the right CUDA version, downloads model weights with `huggingface-cli`, sets up Ollama, configures ComfyUI, exports workflow JSONs, edits Python files. This is a multi-hour setup that filters out 95% of potential users.

**No service orchestration.** The user has to remember to start `ollama serve` and `ComfyUI/main.py` in separate terminals before running the pipeline. If they forget, they get a connection error. If a service crashes mid-generation, nothing recovers.

**No model awareness.** The pipeline hardcodes `GEMMA_MODEL = "gemma2"` in Python. If the user has `gemma3:4b` installed instead, it crashes with a 404 error and no useful message.

**No GUI.** Every interaction is a CLI command with seven flags. There's no preview, no project history, no way to tweak a single scene without re-running the entire pipeline.

**Limited capabilities.** Only one video model (Wan2.1), one TTS engine (Kokoro), no subtitles, no background music, no upscaling, no frame interpolation, no transitions, no batch processing.

**No error recovery.** Any failure aborts the entire run. If scene 3 of 5 fails, you start over from scratch and burn another 25 minutes of GPU time.

### What We Keep

The four Python modules become the **backend service layer** of the new app. They're solid, modular, and testable. We don't rewrite them — we wrap them with an orchestration daemon and an Electron frontend.

---

## 3. The New Architecture

The app is a three-tier system: a native desktop shell (Electron), a Python backend daemon (FastAPI), and the existing pipeline modules as the execution layer.

```
┌─────────────────────────────────────────────────────────┐
│  ELECTRON FRONTEND                                      │
│  React + Zustand + TailwindCSS                          │
│  - Onboarding card, project view, generation queue      │
│  - Real-time previews via WebSocket                     │
│  - No business logic, only presentation                 │
└──────────────────────┬──────────────────────────────────┘
                       │  IPC (REST + WebSocket)
                       │  localhost:7860
                       ▼
┌─────────────────────────────────────────────────────────┐
│  PYTHON BACKEND DAEMON (FastAPI + uvicorn)              │
│  - Service orchestration (starts/stops Ollama, ComfyUI) │
│  - Model discovery and registry                         │
│  - Generation queue with persistence (SQLite)           │
│  - Hardware detection and capability matching           │
│  - Progress streaming to frontend                       │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
   │ Ollama  │    │ComfyUI/ │    │ Kokoro  │    │ FFmpeg  │
   │ subproc │    │ Wan2.1  │    │  TTS    │    │ subproc │
   │         │    │ subproc │    │         │    │         │
   └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

### Why This Architecture

**Electron** is the right choice because Kaka already builds in this stack (SpockChat, Chronicle, ScoobyBench, ContextCore — all Electron-based). The team-of-one productivity gain is real. Electron + React + Vite is a known quantity.

**FastAPI** for the backend matches Kaka's other projects (Crucible, ContextCore). Async by default, type-safe with Pydantic, easy WebSocket support for progress streaming, auto-generated OpenAPI docs for debugging.

**Subprocess orchestration** keeps Ollama and ComfyUI as external services rather than embedding them. This is critical — they're heavy processes with their own update cycles, and embedding them would create dependency hell. The daemon spawns them on app start and shuts them down cleanly on exit.

**SQLite** for persistence — single-file database, zero-config, ships with Python. Stores project history, generation queue, model registry, user preferences.

---

## 4. First-Run Experience

When the user clones the repo and double-clicks the launcher (`start.bat` on Windows, `start.sh` on Linux/Mac), here's what happens:

### Phase 1 — Boot Check (5 seconds)

A minimal native window opens immediately showing "AI Video Studio is starting..." with a progress indicator. Behind the scenes, the launcher script checks:

- Is Python 3.10+ installed? (If not, opens browser to python.org with a clear message)
- Is Node.js 18+ installed? (If not, prompts the user — needed for Electron)
- Is Git installed? (Required for fetching custom nodes)
- Is FFmpeg on PATH? (If not, auto-downloads the binary to a local `bin/` folder)

### Phase 2 — Dependency Bootstrap (1-15 minutes, only first time)

The boot screen transitions to a setup screen with live log output (collapsible). The launcher:

1. Creates an isolated Python virtual environment in `app/runtime/python/`
2. Installs all backend dependencies via pip (FastAPI, uvicorn, kokoro, soundfile, websocket-client, requests, sqlalchemy, huggingface-hub, psutil, GPUtil)
3. Installs the frontend dependencies via `npm install` in `app/frontend/`
4. Detects GPU via `nvidia-smi` → records VRAM tier (8GB / 12GB / 16GB+ / 24GB+)
5. Detects existing Ollama installation
6. Detects existing ComfyUI installation
7. If ComfyUI is missing, prompts: "ComfyUI is required for video generation. Install automatically? (3.2 GB)"
8. If accepted, clones ComfyUI to `app/runtime/comfyui/`, installs its requirements
9. Downloads the recommended Wan2.1 model variant for the detected VRAM tier

Each step shows real-time status. If anything fails, a clear error card appears with a retry button and a "Copy diagnostic info" option.

### Phase 3 — Service Boot (10 seconds)

Once dependencies are ready, the daemon starts. It:

1. Boots Ollama as a subprocess (if not already running)
2. Boots ComfyUI in API mode as a subprocess (headless, no browser)
3. Starts the FastAPI daemon on `localhost:7860`
4. Performs health checks on all three services
5. Loads the model registry (scans Ollama and ComfyUI for installed models)

The Electron frontend connects to the daemon and transitions to the onboarding card.

---

## 5. The Onboarding Card

Before showing the full interface, a centered card appears with the 5-step quickstart. Designed in the Linear/Raycast aesthetic — clean typography, restrained color, no animation gimmicks.

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   Welcome to AI Video Studio                                │
│                                                             │
│   Generate cinematic videos from text — fully on your       │
│   machine. Here's how it works:                             │
│                                                             │
│   ①  Write or paste your script                             │
│      Any narration text, 2-5 sentences works best           │
│                                                             │
│   ②  Pick a Skill                                           │
│      Documentary, Explainer, Product, Cinematic, Short      │
│                                                             │
│   ③  Choose a voice                                         │
│      8 voices across American and British accents           │
│                                                             │
│   ④  Hit Generate                                           │
│      Sit back — we'll handle scenes, voice, and final cut   │
│                                                             │
│   ⑤  Download and share                                     │
│      MP4 ready for Instagram, YouTube, TikTok, or anywhere  │
│                                                             │
│                                                             │
│   System Status:                                            │
│   ✓ Gemma 3 (4B)   detected and ready                       │
│   ✓ Wan2.1 (1.3B)  detected and ready                       │
│   ✓ Kokoro TTS     ready                                    │
│   ✓ GPU: 8.2 GB VRAM available                              │
│                                                             │
│   [ Don't show again ]                    [ Let's start ▸ ] │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

This card serves a triple purpose: it teaches the workflow in 30 seconds, it confirms the system is configured correctly, and it builds confidence that something professional is about to happen.

---

## 6. The Main Interface

After dismissing the onboarding card, the user lands in the main workspace. Three primary areas, keyboard-first navigation:

### Left Sidebar — Project Library

A list of past projects with thumbnails. Click to reopen. Right-click to duplicate, rename, delete, export. A search bar at the top. A "+ New Project" button anchored at the bottom.

### Center — Editor

This is where work happens. Tabbed view at the top: **Script** | **Scenes** | **Audio** | **Render**.

**Script tab:** A large text editor with markdown support. A "Refine with Gemma" button polishes the text. A "Generate Scenes" button asks Gemma to break it into N visual prompts. Scene count slider (1-8). Word count and estimated final duration displayed live.

**Scenes tab:** A grid of scene cards. Each card shows the prompt text, a preview thumbnail (when rendered), and quick actions: edit prompt, regenerate, lock, delete. The user can drag to reorder. Adding a scene is a single click. Each scene has its own per-scene settings (model choice, duration, seed) accessible via a "..." menu.

**Audio tab:** Voice selector dropdown with playback samples. Speed slider. Optional background music generator (MusicGen integration) with mood presets — cinematic, upbeat, calm, dramatic. Optional sound effects library. Volume mixing for narration vs music.

**Render tab:** Aspect ratio chooser (9:16 reels, 1:1 square, 16:9 widescreen, 4:5 portrait). Resolution toggle (720p, 1080p, 4K via upscaling). Subtitle toggle (auto-generated via Whisper). Watermark/branding upload. The big "Render Final Video" button.

### Right Sidebar — Inspector

Context-sensitive panel showing details of whatever is selected. Click a scene → shows its model, seed, generation settings. Click the project → shows total estimated render time, disk usage, output formats queued.

### Bottom — Generation Queue

A persistent strip across the bottom showing all active and queued generations. Each item displays: project name, stage (Refining → Audio → Scene 1/3 → Scene 2/3 → Merging), progress bar, ETA. Items can be paused, reordered, or cancelled. This is the user's window into the heavy lifting.

---

## 7. The Skills System

This is the biggest user-facing feature. Inspired by ContextCore's preset architecture, Skills are pre-tuned configurations that bundle a prompt template, visual style, voice choice, pacing, music mood, and output format into a one-click experience.

### Initial Skill Pack

**Documentary** — Slow-paced, third-person narration. British male voice (`bm_george`). Cinematic visual prompts emphasizing scale, time, natural light. Wide aspect ratios. Optional subtle background score. Output: 16:9 1080p.

**Explainer** — Conversational, energetic narration. American female voice (`af_sarah`). Visual prompts emphasizing clarity, motion, abstract visualizations of concepts. Punchy pacing — shorter scenes, faster cuts. Output: 16:9 1080p with auto-subtitles.

**Product Showcase** — Confident, polished narration. American male voice (`am_michael`). Visual prompts emphasizing product hero shots, dramatic lighting, slow camera moves. Output: 1:1 or 9:16 1080p.

**Cinematic Story** — Dramatic, paced narration. Choice of voice. Visual prompts emphasizing atmospheric scenes, golden hour, film grain aesthetics. Optional emotional score. Output: 16:9 1080p with cinematic letterboxing.

**Social Short** — Fast, hook-driven narration. Voice with energy (`af_heart`). Visual prompts emphasizing bold colors, motion, quick scene changes. Output: 9:16 1080×1920, optimized for Reels and TikTok.

**Tutorial** — Clear, instructional narration. Voice with clarity (`af_nicole`). Visual prompts emphasizing step-by-step demonstrations, clean backgrounds, focus on the subject. Output: 16:9 1080p with prominent subtitles.

**News Brief** — Authoritative, fast-paced narration. Voice with gravitas (`am_adam`). Visual prompts emphasizing photojournalistic style, current-events imagery. Output: 16:9 1080p.

### Skill Architecture

Each Skill is a JSON file in `app/skills/`. The format:

```json
{
  "id": "documentary",
  "name": "Documentary",
  "description": "Slow, cinematic, third-person",
  "voice": "bm_george",
  "voice_speed": 0.95,
  "scene_pacing": "slow",
  "prompt_template": "{narration_chunk}, cinematic documentary style, natural lighting, wide composition, slow camera movement, photorealistic, 4k",
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "subtitles": false,
  "music_mood": "ambient_score",
  "post_processing": ["color_grade_documentary", "film_grain_subtle"],
  "icon": "documentary.svg"
}
```

The user can create custom Skills by duplicating an existing one and tweaking parameters. Power users can share Skill JSONs via a community marketplace (future).

---

## 8. Capabilities Expansion

The current pipeline only does text → video → narration. The new app expands this dramatically. Each capability is implemented as a backend module and exposed via the appropriate Skill or manual control.

### Multi-Model Video Generation

Support multiple video backends, chosen automatically based on the user's VRAM tier or manually overridden:

- **Wan2.1 (1.3B)** — primary, 8GB VRAM, balanced quality/speed
- **Wan2.1 (14B)** — premium, 16GB+ VRAM, best quality
- **LTX-Video** — fast mode, 8GB VRAM, 4x faster than Wan2.1
- **CogVideoX-5B** — alternative style, 12GB VRAM
- **AnimateDiff** — looping short clips, 6GB VRAM, perfect for backgrounds

The model registry exposes capabilities (max resolution, max frames, style profile) and the daemon routes generation requests to whichever model best fits the Skill and current GPU state.

### Frame Interpolation

After Wan2.1 generates a 16fps clip, the backend optionally runs **RIFE** (Real-Time Intermediate Flow Estimation) to interpolate to 30fps or 60fps. This eliminates the slightly choppy feel of native AI video. RIFE is lightweight and adds only 5-15% to total generation time.

### Upscaling

For final output, **Real-ESRGAN** upscales the generated 480p or 720p video to 1080p or 4K. Implemented as a ComfyUI custom node so it runs in the same GPU pipeline without context switching. Optional and toggle-able per render.

### Auto-Subtitles via Whisper

The Kokoro-generated audio is fed back into **Whisper** (locally, via faster-whisper) for transcription with word-level timestamps. The transcript is converted to SRT and burned into the video using FFmpeg's subtitle filter with proper typography. Configurable position, font, size, color, background style.

### Background Music Generation

**MusicGen** (Meta's local music generation model) generates a custom soundtrack matching the chosen Skill's mood. The user can also import their own MP3/WAV. FFmpeg handles ducking — automatically lowering music volume when narration is present. Tail-out fades at end of video.

### Sound Effects Library

A bundled library of royalty-free sound effects (whooshes, transitions, ambient layers) that can be auto-placed at scene transitions. Selection driven by Skill preset.

### Multi-Voice Narration

Future capability — splitting narration across multiple Kokoro voices for dialogue or multi-character storytelling. The script editor parses lines like `[Voice: am_adam] Welcome back...` and routes each segment to the right voice.

### B-Roll Mixing

For longer videos, the user can upload reference images or video clips that get mixed into the AI-generated scenes. Useful for product demos where actual product footage is essential. FFmpeg handles the cross-fading.

### Scene Transitions

Beyond simple cuts, the app supports: fade, dissolve, wipe, slide, and AI-generated morphing transitions (using AnimateDiff between scene endpoints). Per-Skill defaults with manual override.

### Color Grading

Post-processing LUTs (Look-Up Tables) applied per Skill — cinematic teal-and-orange for Cinematic Story, warm natural tones for Documentary, vibrant high-contrast for Social Short. Implemented as FFmpeg filter chains.

### Watermarking and Branding

The user uploads a logo image and chooses position (corners, centered, fade in/out). Optional outro card with custom text. Per-project or app-wide defaults.

### Batch Generation

Queue 10 different scripts and let the app run overnight. Each project goes through the full pipeline sequentially. Email/notification when complete (local notifications only).

---

## 9. Model Management Layer

The Model Manager is a dedicated screen accessible from the sidebar. It shows every AI model the app knows about — installed, available, recommended for the user's hardware.

### Auto-Detection

On startup, the daemon:

1. Queries Ollama's `/api/tags` endpoint to list installed LLMs
2. Scans `ComfyUI/models/` directory for video, image, and upscaling models
3. Detects Kokoro voice models in the Python package
4. Detects RIFE, Real-ESRGAN, MusicGen, Whisper if installed
5. Builds an in-memory registry tagged with capabilities and VRAM requirements

### The Model Browser

A two-pane view: left lists installed models with green status indicators, right shows available downloads from a curated catalog. Each downloadable model shows:

- Name and version
- Size on disk
- VRAM requirement
- Quality tier (Fast / Balanced / Premium)
- Compatible Skills

One-click download with progress tracking. The catalog is a JSON file in the repo, not a server — it ships with the app, updated via git pulls.

### Smart Routing

When a generation request comes in, the daemon's routing logic considers:

- Current free VRAM (queries `nvidia-smi` live)
- Skill's preferred model
- User's explicit override
- Recently used models (warm cache preference)

If the preferred model won't fit, the routing logic gracefully degrades to a smaller variant rather than failing. The user gets a notification: "Used Wan2.1 1.3B instead of 14B due to memory pressure."

---

## 10. Optimization Engine

Hidden behind the interface is an optimization layer that keeps everything responsive on consumer hardware.

### VRAM-Aware Model Lifecycle

Only one heavy model lives in VRAM at a time. The daemon explicitly unloads Gemma before loading Wan2.1, and unloads Wan2.1 before running Real-ESRGAN. This sequential approach means an 8GB GPU can run a pipeline that would otherwise demand 20GB if everything stayed resident.

### Generation Queue with Persistence

The queue lives in SQLite. If the app crashes or the computer is rebooted mid-batch, the queue resumes on next launch from where it left off. Each scene's intermediate outputs are saved to disk, so a 5-scene generation that fails on scene 4 only retries scene 4.

### Caching

Identical prompts with identical seeds produce identical results. The cache key is `(prompt + seed + model + resolution)` hashed. On a cache hit, no GPU work is done. This is invaluable when the user is tweaking one scene at a time — only the changed scene re-renders.

### Progressive Preview

While Wan2.1 is sampling, the backend streams intermediate latent decodes every few steps. The frontend shows a blurry-but-improving preview in real time, so the user gets feedback that something is happening rather than staring at a progress bar.

### Lazy Service Boot

Ollama starts immediately (small footprint). ComfyUI starts only when the first video generation is requested (heavier boot). This shaves seconds off app launch time for users who might just be browsing past projects.

### Background Generation

The user can start a render and continue working on a different project. The queue handles serialization on the GPU side, the UI handles parallel project editing on the frontend side.

---

## 11. Quality & Output Pipeline

Generated raw clips don't look professional. The post-processing pipeline is what transforms AI output into shareable content.

The flow for every final render:

1. **Raw scene generation** — Wan2.1 produces 480p or 720p clips at 16fps
2. **Frame interpolation** — RIFE bumps to 30fps for smoothness
3. **Upscaling** — Real-ESRGAN bumps to 1080p or 4K
4. **Color grading** — FFmpeg LUT applied per Skill
5. **Scene concatenation** — clips joined with chosen transition style
6. **Audio merge** — narration mixed over background music with ducking
7. **Subtitle burn** — Whisper-generated SRT overlaid
8. **Watermark/branding** — logo and outro card applied
9. **Format conversion** — encoded for target platform with proper aspect ratio padding
10. **Quality validation** — output checked for duration mismatch, audio sync, file integrity

Each stage is a discrete FFmpeg or model call. If a stage fails, the daemon retries with conservative settings before bubbling up an error.

---

## 12. Project & Template System

Every generation is a Project. Projects persist as folders inside `app/projects/<project-id>/` containing:

- `project.json` — script, scenes, settings, Skill choice
- `audio/` — generated narration WAVs
- `scenes/` — generated MP4 clips per scene
- `previews/` — thumbnail images
- `final/` — rendered output MP4s
- `metadata.json` — generation timings, model versions used, seeds

Projects are versioned. Every render creates a snapshot, so the user can go back to any earlier version. Diff view shows what changed between versions.

### Templates

A Template is a Project saved without the actual content — just the structural and stylistic choices. Users can create templates from successful projects, share them with team members, or download community templates. Templates accelerate repeated workflows ("my standard YouTube intro," "weekly product highlight").

---

## 13. Technical Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Desktop shell | Electron 28+ | Cross-platform, Kaka's known stack |
| Frontend framework | React 18 + Vite | Fast HMR, mature ecosystem |
| State management | Zustand | Minimal, no boilerplate |
| Styling | Tailwind CSS + shadcn/ui | Linear/Raycast-style aesthetics |
| Backend | FastAPI + uvicorn | Async, type-safe, WebSocket native |
| Backend language | Python 3.11 | Already required for ML libraries |
| Database | SQLite via SQLAlchemy | Single file, zero config |
| IPC | REST + WebSocket | REST for commands, WS for progress |
| LLM serving | Ollama | Already integrated |
| Video models | ComfyUI subprocess | Already integrated |
| TTS | Kokoro (in-process) | Already integrated |
| Transcription | faster-whisper | Local, fast, GPU-accelerated |
| Music | MusicGen (via Audiocraft) | Local, Meta-released |
| Upscaling | Real-ESRGAN | ComfyUI node available |
| Interpolation | RIFE | ComfyUI node available |
| Video processing | FFmpeg static binary | Bundled with app |
| Packaging | electron-builder | Cross-platform installers |

---

## 14. File Structure

```
ai-video-studio/
│
├── start.bat                          # Windows launcher
├── start.sh                           # Linux/Mac launcher
├── installer/
│   ├── bootstrap.py                   # First-run dependency installer
│   ├── system_check.py                # Hardware and software detection
│   └── catalog.json                   # Available models catalog
│
├── app/
│   ├── frontend/                      # Electron + React app
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── electron/
│   │   │   ├── main.ts                # Electron main process
│   │   │   └── preload.ts             # IPC bridge
│   │   └── src/
│   │       ├── App.tsx
│   │       ├── components/
│   │       │   ├── OnboardingCard.tsx
│   │       │   ├── ProjectLibrary.tsx
│   │       │   ├── ScriptEditor.tsx
│   │       │   ├── ScenesGrid.tsx
│   │       │   ├── AudioPanel.tsx
│   │       │   ├── RenderPanel.tsx
│   │       │   ├── GenerationQueue.tsx
│   │       │   ├── ModelBrowser.tsx
│   │       │   └── SkillPicker.tsx
│   │       ├── stores/
│   │       │   ├── projectStore.ts
│   │       │   ├── queueStore.ts
│   │       │   └── modelStore.ts
│   │       └── api/
│   │           └── backend.ts         # FastAPI client
│   │
│   ├── backend/                       # Python daemon
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── daemon.py                  # Service orchestrator
│   │   ├── routes/
│   │   │   ├── projects.py
│   │   │   ├── generation.py
│   │   │   ├── models.py
│   │   │   ├── skills.py
│   │   │   └── system.py
│   │   ├── services/
│   │   │   ├── ollama_manager.py      # Spawns and monitors Ollama
│   │   │   ├── comfyui_manager.py     # Spawns and monitors ComfyUI
│   │   │   ├── model_registry.py
│   │   │   ├── generation_queue.py
│   │   │   └── hardware_monitor.py
│   │   ├── pipeline/                  # The existing modules, refactored
│   │   │   ├── gemma_client.py        # Was: call_gemma()
│   │   │   ├── kokoro_tts.py          # Kept as-is
│   │   │   ├── wan_client.py          # Kept as-is
│   │   │   ├── whisper_client.py      # NEW: subtitles
│   │   │   ├── musicgen_client.py     # NEW: background music
│   │   │   ├── rife_client.py         # NEW: interpolation
│   │   │   ├── esrgan_client.py       # NEW: upscaling
│   │   │   └── ffmpeg_merger.py       # Extended from existing
│   │   ├── models/                    # SQLAlchemy ORM
│   │   │   ├── project.py
│   │   │   ├── scene.py
│   │   │   └── queue_item.py
│   │   └── db.sqlite                  # Runtime database
│   │
│   ├── runtime/                       # Installed at first launch
│   │   ├── python/                    # Bundled venv
│   │   ├── comfyui/                   # Bundled ComfyUI install
│   │   ├── ffmpeg/                    # Bundled FFmpeg binary
│   │   └── models/                    # Downloaded model weights
│   │
│   ├── skills/                        # Built-in Skill presets
│   │   ├── documentary.json
│   │   ├── explainer.json
│   │   ├── product.json
│   │   ├── cinematic.json
│   │   ├── short.json
│   │   ├── tutorial.json
│   │   └── news.json
│   │
│   ├── projects/                      # User's saved projects
│   └── workflows/                     # Generated ComfyUI workflow JSONs
│
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── SKILLS.md
│   └── CONTRIBUTING.md
│
└── LICENSE
```

---

## 15. Implementation Roadmap

A phased approach. Each phase produces a shippable milestone.

### Phase 1 — Backend Foundation (Week 1-2)

Build the FastAPI daemon. Wrap the existing four pipeline modules as service classes. Add SQLite persistence for projects and queue. Implement Ollama and ComfyUI subprocess management. Build the REST API. Test exhaustively with curl and a CLI client. **Deliverable:** a daemon that exposes the existing pipeline via HTTP.

### Phase 2 — Frontend Shell (Week 3-4)

Build the Electron + React shell. Implement the boot screen, onboarding card, and a minimal project editor. Connect to the daemon via REST and WebSocket. No advanced features yet — just script input, generate button, and result viewer. **Deliverable:** end-to-end flow from script to MP4 via GUI, replicating current CLI functionality.

### Phase 3 — Installer & Bootstrap (Week 5)

Build `start.bat` and `start.sh` with full dependency installation logic. System check, Python venv creation, pip install, ComfyUI auto-install, Wan2.1 weight download, model registry population. Handle failures gracefully with retry UX. **Deliverable:** clone-and-run experience working on a fresh Windows machine.

### Phase 4 — Skills System (Week 6)

Implement Skill JSON schema, build the first 7 Skill presets, integrate Skill selection into the editor, route Skill parameters through the pipeline. **Deliverable:** one-click Skill-driven generation producing visibly different outputs per Skill.

### Phase 5 — Quality Layer (Week 7-8)

Integrate Whisper for subtitles, MusicGen for soundtracks, RIFE for interpolation, Real-ESRGAN for upscaling. Build the post-processing chain in `ffmpeg_merger.py`. Test on multiple GPUs. **Deliverable:** professional-quality output from previously-amateur raw clips.

### Phase 6 — Optimization & Polish (Week 9-10)

Implement VRAM-aware model lifecycle, generation queue persistence, caching, progressive preview. Polish UI animations, keyboard shortcuts, error messages. Build the model browser. **Deliverable:** smooth, responsive experience even under memory pressure.

### Phase 7 — Templates, Batch, Sharing (Week 11)

Implement template save/load, batch generation queue, project versioning, export/import. **Deliverable:** power-user workflows enabled.

### Phase 8 — Packaging & Release (Week 12)

Build electron-builder installers for Windows (.exe), Linux (.AppImage, .deb), and Mac (.dmg). Write comprehensive README and ARCHITECTURE docs. Cut v1.0 release. **Deliverable:** downloadable installers on GitHub Releases.

---

## 16. Risks & Mitigations

**Risk: ComfyUI breaking changes.** ComfyUI's API and node structure evolves rapidly. *Mitigation:* pin to a known-good commit hash in the installer, document upgrade procedure separately.

**Risk: Model file sizes.** Total model assets exceed 30GB if everything is installed. *Mitigation:* progressive download — only fetch what the chosen Skill requires, fetch more on demand. Show a clear disk usage breakdown.

**Risk: GPU compatibility.** Not every user has an NVIDIA GPU with the right CUDA version. *Mitigation:* detect early in `system_check.py`, offer CPU fallback mode (slow but functional) for LTX-Video which has decent CPU performance.

**Risk: Electron app size.** Electron itself adds ~150MB before any AI code. *Mitigation:* accept this cost — the user is already downloading 30GB of model weights, the framework overhead is negligible.

**Risk: Generation time expectations.** Users may expect 10-second renders and get 15-minute renders. *Mitigation:* the onboarding card explicitly mentions render times. The queue UI shows accurate ETAs based on hardware benchmarking done at install time.

**Risk: Output quality variance.** Even good prompts sometimes produce bad clips. *Mitigation:* the regenerate-single-scene flow makes iteration cheap. A "lock good scenes" feature means only bad scenes re-roll.

**Risk: Maintaining all the integrations.** Whisper, MusicGen, RIFE, ESRGAN — that's a lot of ML dependencies. *Mitigation:* each lives behind a clean interface; if one breaks, the rest continue. Skills that depend on a broken module gracefully degrade.

---

## 17. Future Extensions

Once v1.0 ships, the natural growth directions:

**Real-time camera input.** Use webcam footage as conditioning input for Wan2.1's image-to-video mode. Imagine recording a 5-second clip of yourself and having the AI extend it into a stylized scene.

**Voice cloning.** Integrate a local voice-cloning model (Tortoise TTS, XTTS) so users can train on their own voice for personal narration without sounding robotic.

**Mobile companion.** A small mobile app that lets the user write scripts and trigger generations on their desktop remotely. Useful for capturing ideas on the go.

**Plugin system.** Third-party developers can write Skills, post-processing filters, model integrations as plugins distributed via a community marketplace.

**Multi-GPU support.** For users with dual GPUs, parallelize scene generation across cards. Render time drops by 50%+ for multi-scene videos.

**Live collaborative editing.** Two creators editing the same script and shared scene library in real time, like Linear for AI video. Maybe a future Hallucinated Lab differentiator.

**Direct platform publishing.** Once a video renders, one-click upload to YouTube, Instagram, TikTok via their APIs (this is the one place where the local-first principle would relax — for explicit publishing actions only, with clear user consent).

**Long-form mode.** Currently the system is optimized for 30-90 second clips. A long-form mode could handle 10-minute videos by chunking the script intelligently and managing memory aggressively across scene batches.

---

## Closing Notes

This roadmap evolves the existing pipeline without throwing it away. The four Python modules (`orchestrator.py`, `wan_client.py`, `kokoro_tts.py`, `ffmpeg_merger.py`) become the trunk of the new backend. Everything else is grown around them — the daemon, the frontend, the Skills, the optimization layer, the quality stack.

The most important shift isn't technical — it's experiential. Today's pipeline asks the user to think like an engineer. Tomorrow's app asks them only to think like a creator. The engineering is still there, just hidden, doing its job silently. That's the bar we're aiming for.

When the v1.0 installer ships, the goal is this: a creator on Instagram who's never written a line of code clones the repo, double-clicks the launcher, waits ten minutes while their machine sets itself up, and finishes the evening with five professional-quality AI videos ready to post. No tutorials. No troubleshooting. No terminal. Just a script in, video out.

That's the product.
