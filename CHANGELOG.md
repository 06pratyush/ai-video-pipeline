# Changelog

All notable changes to AI Video Studio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — Phase 9 extensions

### Added
- **Auto-update banner** — checks GitHub Releases every 6 hours, shows a dismissible
  banner with platform-specific download link when a newer version exists
- **Skill export / import** — Export button in the ScriptEditor downloads the active
  skill as `{id}.skill.json`; Import accepts any uploaded Skill JSON, validates required
  fields, auto-assigns a fresh id on collision. Foundation for a community marketplace
- **Voice cloning** — XTTS v2 pipeline module (`xtts_client.py`) with reference-clip
  speech synthesis; `/voices/` route for upload/list/delete; degrades cleanly when
  TTS package isn't installed
- **Long-form mode** — script chunker splits long narration at sentence boundaries
  into 60–90 second sub-projects; `/longform/preview` shows the split plan; `/longform/create`
  queues all chunks as a batch. New modal in the sidebar with live preview
- **/updates/check** and **/version** endpoints with platform-specific asset detection

### Changed
- Backend `VERSION` constant moved to `app/backend/version.py` to break circular imports
- ProjectLibrary footer reorganized as a 2×2 grid (Templates, Batch, Long-form, Models)



First public release. Eight phases of work, from CLI prototype to packaged desktop app.

### Added

#### Phase 1 — Backend Foundation
- FastAPI daemon on `localhost:7860` with WebSocket progress streaming
- SQLAlchemy + SQLite persistence for projects, scenes, queue items
- Service managers for Ollama and ComfyUI subprocess orchestration
- Hardware detection (GPU/VRAM tier, CPU, RAM)
- Generation queue worker with background-thread execution and persistence
- REST routes: `/system`, `/projects`, `/generation`, `/models`, `/skills`

#### Phase 2 — Frontend Shell
- Electron 31 + React 18 + Vite + Zustand + Tailwind CSS
- Boot screen with daemon health check
- Onboarding card with system status verification
- Project library sidebar with search and delete confirmations
- Script / Scenes / Render tabbed editor
- Generation queue strip with live WebSocket progress
- Custom dark color palette (Linear/Raycast aesthetic)

#### Phase 3 — Installer & Bootstrap
- `installer/bootstrap.py` with JSON-line progress protocol
- 11-step install pipeline (Python check, GPU detect, venv, PyTorch, deps,
  FFmpeg, Ollama, LLM pull, ComfyUI, Wan2.1 model, frontend)
- `SetupScreen.tsx` with step list, progress bar, log viewer, retry button
- VRAM-tier-aware model selection (1.3B for <16GB, 14B for 16GB+)
- Headless bootstrap fallback when Node.js is missing
- Cross-platform `start.bat` and `start.sh`

#### Phase 4 — Skills System
- 7 built-in Skills: Documentary, Explainer, Product, Cinematic, Short, Tutorial, News
- Skill JSON schema with voice, pacing, prompt template, aspect ratio, post-processing
- SkillPicker UI with quality badges (voice, fx count, CC indicator)
- ScriptEditor auto-applies skill voice with "set by skill" indicator
- FFmpeg color grading (7 named presets), letterbox, film grain effects
- Pipeline routes skill voice + speed through Kokoro TTS

#### Phase 5 — Quality Layer
- `whisper_client.py` — faster-whisper transcription to styled SRT
- `musicgen_client.py` — MusicGen with mood-to-prompt mapping
- `rife_client.py` — FFmpeg minterpolate (RIFE-compatible swap-in)
- `esrgan_client.py` — super2xbr + lanczos upscale (ESRGAN swap-in)
- `merge_with_background_music()` — auto-ducking narration over music
- RenderPanel Quality Settings with 4 toggles and skill auto-defaults
- Render options persisted in queue items; graceful degradation on missing deps

#### Phase 6 — Optimization & Polish
- `vram_manager.py` — Ollama keep_alive=0 unload, smart model routing on memory pressure
- `generation_cache.py` — sha256-keyed scene cache with hit_count tracking
- 15-second hardware status cache (eliminates 8s nvidia-smi delay per request)
- `/system/vram` fast endpoint for live VRAM polling
- Live VRAM bar in title bar (turns red above 85% usage)
- Model Browser overlay with Installed + Available tabs
- Cache stats widget with clear button
- One-click Ollama install for catalog models

#### Phase 7 — Templates, Batch, Versioning
- Template ORM + `/templates/` CRUD route
- Template Browser modal with use_count chips and apply dialog
- Batch generation: queue N projects from one form with optional template
- Project versioning: auto-snapshot on successful render to
  `app/projects/{id}/versions/v{N}/final.mp4`
- Version History modal with restore action and details accordion

#### Phase 8 — Packaging & Release
- Full `electron-builder` config for Windows (NSIS + portable), Linux (AppImage + .deb), macOS (DMG + zip, x64 + arm64)
- Code signing entitlements for macOS
- Build resources documentation
- Comprehensive docs: README, ARCHITECTURE, BUILDING, TROUBLESHOOTING, CONTRIBUTING, SKILLS
- MIT LICENSE
- GitHub Actions workflow for tagged releases

### Architecture

- Three-tier: Electron frontend → FastAPI daemon → external subprocesses (Ollama, ComfyUI, FFmpeg)
- Local-only: all traffic on 127.0.0.1, no cloud calls, no telemetry
- Modular pipeline: each stage (Gemma, Kokoro, Wan, Whisper, MusicGen, RIFE, ESRGAN, FFmpeg) is a standalone module behind a clean interface; one breaking doesn't cascade

### Known Limitations

- NVIDIA-only — Wan2.1 requires CUDA; AMD ROCm support pending upstream
- Whisper Base may mis-transcribe stylized voices; manual SRT editing is the workaround
- MusicGen capped at 30s segments — long videos loop the same composition
- Cross-platform code-signed builds require building on each native host

### Roadmap (post-1.0)

- Skill marketplace + community-submitted Skills
- Voice cloning (XTTS, Tortoise) for personal narration
- Mobile companion for remote triggering
- Multi-GPU rendering for 50%+ speedup
- Long-form mode (10-minute videos via intelligent chunking)
- Plugin system for third-party processing modules
