# Architecture

AI Video Studio is a three-tier desktop application. This document covers the high-level layout, data flow, and the reasoning behind major choices.

## Layers

```
┌─────────────────────────────────────────────────────────────┐
│  ELECTRON FRONTEND (app/frontend/)                          │
│                                                             │
│  React 18 + Vite + Zustand + Tailwind CSS                   │
│  Single Vite build produces:                                │
│    • dist/             — renderer bundle                    │
│    • dist-electron/    — main + preload (compiled TS)       │
│                                                             │
│  Stores:                                                    │
│    • projectStore     — projects + scenes CRUD              │
│    • queueStore       — generation queue + WebSocket        │
│    • modelStore       — model registry + skills + sys status │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP REST + WebSocket
                           │ all traffic local: 127.0.0.1:7860
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PYTHON BACKEND DAEMON (app/backend/)                       │
│                                                             │
│  FastAPI + Uvicorn  •  SQLAlchemy + SQLite  •  Pydantic v2 │
│                                                             │
│  Routes:                                                    │
│    /system      — health, status, vram, cache stats         │
│    /projects    — CRUD + scenes                             │
│    /generation  — start, queue, cancel, ws progress         │
│    /models      — registry, catalog, install                │
│    /skills      — list, get                                 │
│    /templates   — CRUD, from-project, apply                 │
│    /projects/{id}/versions — snapshot, restore              │
│    /batch       — multi-project queue                       │
│                                                             │
│  Services:                                                  │
│    • ollama_manager     — subprocess + health check         │
│    • comfyui_manager    — subprocess + health check         │
│    • model_registry     — scans installed models            │
│    • generation_queue   — background thread worker          │
│    • vram_manager       — model lifecycle, smart routing    │
│    • generation_cache   — sha256-keyed scene cache          │
│    • hardware_monitor   — GPU/CPU/RAM detection             │
│                                                             │
│  Pipeline modules (refactored from the original CLI):       │
│    • gemma_client       — Ollama wrapper                    │
│    • kokoro_tts         — local TTS                         │
│    • wan_client         — ComfyUI workflow submission       │
│    • whisper_client     — faster-whisper transcription      │
│    • musicgen_client    — audiocraft soundtrack gen         │
│    • rife_client        — minterpolate / RIFE swap-in       │
│    • esrgan_client      — super2xbr / Real-ESRGAN swap-in   │
│    • ffmpeg_merger      — concat, mux, color, post-process  │
└────────────┬───────────────────┬──────────────┬─────────────┘
             ▼                   ▼              ▼
        ┌─────────┐         ┌─────────┐    ┌─────────┐
        │ Ollama  │         │ ComfyUI │    │ FFmpeg  │
        │ +Gemma  │         │ +Wan2.1 │    │ +Kokoro │
        └─────────┘         └─────────┘    └─────────┘
```

## Why Electron + Python (not pure Python or pure JS)?

**Pure Python (Gradio, Streamlit, NiceGUI) trade-offs:**
- Pros: single language, fast to ship
- Cons: hard to escape the browser metaphor; subprocess management is awkward; native file pickers and "open in folder" are clunky; window state isn't persistent

**Pure JS (TypeScript + Node-ML libs) trade-offs:**
- Pros: single language end-to-end
- Cons: every ML library lives in Python — re-implementing ComfyUI in JS is unrealistic; Kokoro, faster-whisper, MusicGen have no first-class Node bindings

**Electron + FastAPI:**
- Electron handles the UX layer (it's what Linear, Slack, VS Code, ChatGPT desktop all use — proven for productivity apps)
- Python handles ML — every model we touch has mature Python bindings
- The boundary is a local HTTP API, which means each layer is independently testable: hit `localhost:7860/projects/` with curl, hit the React app with the browser
- The frontend can be served standalone in a browser as a dev fallback when Electron isn't available

## Data flow

### Boot

1. User double-clicks the app icon (or `start.bat` / `start.sh`)
2. `start.*` checks Python 3.10+ and Node.js 18+; reports missing prereqs
3. Electron `main.ts` `app.whenReady()` fires
4. `needsSetup()` checks for `app/runtime/python/Scripts/python.exe`
5. If missing: window opens at 860×560 in setup mode → SetupScreen runs the bootstrap with JSON progress events over IPC
6. If present: `startDaemon()` spawns the FastAPI process; window opens at 1400×900
7. FastAPI `lifespan` runs `init_db()` then `daemon.startup()` which boots Ollama, scans models, starts the generation queue worker
8. Frontend connects to `/system/health` and `/system/status`; if both succeed, transitions from BootScreen → OnboardingCard → main app

### Generation

```
Frontend                    Backend                  External
────────                    ───────                  ────────
[Render tab]
   │
   POST /generation/start ──▶ enqueue() → SQLite
                                │
   ◀── 202 queued + WS subscribe┘
                                │
                                ▼
                          worker thread picks up
                                │
                                ▼
                          _run_pipeline()
                                │
                          emit "refining" ──▶ Ollama /api/generate
   ◀───── WS progress ◀─────────┘
                          emit "prompts"  ──▶ Ollama
                          emit "audio"    ──▶ Kokoro (in-process)
                          emit "music"    ──▶ MusicGen (optional)
                          unload Ollama (keep_alive=0)
                          check cache per scene
                          emit "scene_N"  ──▶ ComfyUI /prompt → Wan2.1
                          cache put
                          emit "interpolating" ──▶ FFmpeg minterpolate
                          emit "merging" ──▶ FFmpeg amix
                          emit "upscaling"     ──▶ FFmpeg super2xbr
                          emit "post_processing" ──▶ FFmpeg curves+eq
                          emit "subtitles" ──▶ faster-whisper → FFmpeg burn
                                │
                          auto-snapshot version
                                │
                          emit "done"
   ◀───── WS done + final_path ─┘
                                │
                          worker picks next queued item
```

### IPC contract

The Electron preload script (`preload.ts`) exposes a tightly scoped API to the renderer via `contextBridge`:

```typescript
window.electronAPI = {
  // Setup
  startSetup, onSetupNeeded, onSetupMessage,
  // Shell
  openPath, showInFolder, platform,
}
```

The renderer never touches Node.js directly — all native operations go through preload. This is the standard Electron security pattern: `contextIsolation: true`, `nodeIntegration: false`.

For backend communication, the renderer makes direct `fetch` calls to `http://localhost:7860` and opens a `WebSocket` to `ws://localhost:7860/generation/ws/{projectId}`. This bypasses Electron entirely — the same code works in a browser.

## VRAM management

On a 8 GB GPU, naively running Gemma 4B + Wan2.1 1.3B + Whisper Base concurrently would need ~14 GB. The lifecycle manager prevents this:

1. Pipeline starts with Gemma loaded (Ollama keeps models hot by default with `keep_alive=5m`)
2. Steps 1–2 (refine, prompts) use Gemma
3. Before scene generation, `vram_manager.prepare_for_video()` calls Ollama with `keep_alive=0` to immediately unload Gemma
4. Wan2.1 loads in its own ComfyUI process — no conflict with Ollama's freed memory
5. After scenes complete, ComfyUI keeps Wan2.1 hot. If subtitles are enabled, faster-whisper uses `int8` quantization which fits in the remaining VRAM

For projects where the preferred video model won't fit, `route_video_model()` automatically degrades from Wan2.1 14B → Wan2.1 1.3B with a progress message explaining the swap.

## Generation cache

Cache key = `sha256(prompt + seed + model_id + resolution)`.

Two main wins:
- **Iteration loop**: tweaking one scene's prompt only re-renders that scene; the others copy from cache
- **Versioning**: restoring a previous version's prompts hits the cache for all scenes, so re-rendering an old version is nearly instant

The cache is stored in SQLite (`cache_entries` table) with hit_count tracking. Cache files live wherever Wan2.1 originally wrote them — the entry holds an absolute path. If the file is later deleted manually, the next `get()` detects the stale entry and removes it.

## Auto-snapshot versioning

Every successful render automatically:
1. Copies `app/projects/{id}/final/final.mp4` to `app/projects/{id}/versions/v{N}/final.mp4`
2. Serializes the project state (script, narration, scene prompts+seeds, render_opts) as JSON
3. Inserts a `project_versions` row

Snapshots are cheap (one file copy + one SQLite row) and give the user a reliable rollback. The Version History UI shows them in reverse chronological order with full diff capability.

## File layout

```
ai-video-pipeline/
│
├── start.bat / start.sh             ─ platform launchers
├── README.md / LICENSE
├── AI_VIDEO_STUDIO_ROADMAP.md       ─ original design doc
│
├── docs/                            ─ THIS FILE + others
│
├── installer/
│   ├── bootstrap.py                 ─ first-run dependency installer
│   ├── system_check.py
│   └── catalog.json                 ─ available models metadata
│
├── app/
│   ├── backend/                     ─ FastAPI daemon
│   │   ├── main.py
│   │   ├── daemon.py
│   │   ├── db.py                    ─ SQLAlchemy + migrations
│   │   ├── db.sqlite                ─ runtime database
│   │   ├── routes/
│   │   ├── services/
│   │   ├── pipeline/
│   │   └── models/                  ─ SQLAlchemy ORM
│   │
│   ├── frontend/                    ─ Electron + React
│   │   ├── electron/
│   │   ├── src/
│   │   ├── build/                   ─ platform-specific assets
│   │   ├── package.json
│   │   └── release/                 ─ electron-builder output
│   │
│   ├── runtime/                     ─ installed at first launch
│   │   ├── python/                  ─ bundled venv
│   │   ├── comfyui/                 ─ cloned ComfyUI
│   │   ├── ffmpeg/                  ─ bundled binary
│   │   └── models/                  ─ downloaded weights
│   │
│   ├── skills/                      ─ JSON Skill presets
│   ├── projects/                    ─ user projects (per-id directories)
│   └── workflows/                   ─ ComfyUI workflow JSONs
```
