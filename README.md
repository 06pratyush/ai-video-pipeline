<div align="center">

<img src="https://img.shields.io/badge/AI%20VIDEO%20STUDIO-1.0.0-6366f1?style=for-the-badge&labelColor=0a0a0b" alt="AI Video Studio v1.0.0" />

# 🎬 AI Video Studio

### Generate cinematic videos from text — fully local, fully autonomous, fully yours.

*Turn a script into a narrated, professionally-edited video. No cloud. No subscriptions. No API keys.  
Your machine is the only computer in the loop.*

<br>

[![Release](https://img.shields.io/github/v/release/06pratyush/ai-video-pipeline?style=flat-square&color=6366f1)](https://github.com/06pratyush/ai-video-pipeline/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Electron](https://img.shields.io/badge/electron-31-47848f?style=flat-square&logo=electron&logoColor=white)](https://www.electronjs.org/)
[![React](https://img.shields.io/badge/react-18-61dafb?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![CUDA](https://img.shields.io/badge/CUDA-12.1-76b900?style=flat-square&logo=nvidia&logoColor=white)](https://developer.nvidia.com/cuda-toolkit)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-71717a?style=flat-square)]()

<br>

[**📥 Download**](https://github.com/06pratyush/ai-video-pipeline/releases/latest) &nbsp;·&nbsp;
[**🚀 Quick Start**](#-quick-start) &nbsp;·&nbsp;
[**🎨 Skills**](#-skills) &nbsp;·&nbsp;
[**⚙️ Architecture**](#-architecture) &nbsp;·&nbsp;
[**🐛 Issues**](https://github.com/06pratyush/ai-video-pipeline/issues)

</div>

---

## ✨ Highlights

<table>
<tr>
<td width="33%" valign="top">

### 🔒 Local-First
Everything runs on your machine.  
No telemetry, no cloud calls,  
no usage tracking, ever.

</td>
<td width="33%" valign="top">

### ⚡ Five-Click Workflow
Paste script → pick Skill →  
toggle quality → hit Generate →  
download finished MP4.

</td>
<td width="33%" valign="top">

### 🎨 7 Built-in Skills
Documentary · Cinematic ·  
Social Short · Explainer ·  
Product · Tutorial · News

</td>
</tr>
<tr>
<td width="33%" valign="top">

### 🧠 Smart VRAM Routing
Auto-downgrades when GPU is full.  
Live VRAM meter in the title bar.  
Sequential model lifecycle.

</td>
<td width="33%" valign="top">

### 📚 Templates & Batch
Save reusable configs.  
Queue 10 projects overnight.  
Auto-versioning per render.

</td>
<td width="33%" valign="top">

### 🎞️ Pro Quality Layer
Whisper subtitles · MusicGen score  
30fps interpolation · 2× upscaling  
Cinematic color grading

</td>
</tr>
</table>

---

## 🎯 What it does

Write a script. Pick a Skill. Hit Generate. Five to fifteen minutes later you have a finished MP4 with narration, visuals, music, subtitles, and color grading — ready to post.

```
   ┌───────────────────┐
   │   Your script     │
   └─────────┬─────────┘
             │
   ╔═════════▼══════════════════════════════════════════════════════╗
   ║  THE PIPELINE                                                  ║
   ║  ────────────                                                  ║
   ║   📝  Gemma (Ollama)        refines narration + scene prompts  ║
   ║   🎙️  Kokoro TTS            synthesizes voice audio            ║
   ║   🎬  Wan2.1 (ComfyUI)      generates clips on your GPU        ║
   ║   🎵  MusicGen              composes background music          ║
   ║   💬  Whisper               transcribes → burned-in subtitles  ║
   ║   ⚡  minterpolate / RIFE   30fps frame interpolation          ║
   ║   📈  super2xbr / ESRGAN    2× upscale to 1080p                ║
   ║   🎨  FFmpeg                color grade, film grain, mux       ║
   ╚═════════╤══════════════════════════════════════════════════════╝
             ▼
   ┌───────────────────┐
   │   final.mp4  🎞️   │
   └───────────────────┘
```

<details>
<summary><b>📊 What runs at each stage</b></summary>

| Stage | Tool | When | Cost |
|-------|------|------|------|
| **Refine narration** | Gemma 3 / 4B via Ollama | Always | ~10s |
| **Generate scene prompts** | Gemma 3 / 4B | Always | ~10s |
| **Voice synthesis** | Kokoro TTS (8 voices) | Always | ~5s per 100 words |
| **Background music** | MusicGen Small | Optional | ~30s per scene |
| **Video clips** | Wan2.1 1.3B / 14B | Always | ~3min per scene |
| **Frame interpolation** | FFmpeg `minterpolate` | Optional | +30% render time |
| **Upscaling** | FFmpeg `super2xbr` | Optional | +20% render time |
| **Subtitles** | faster-whisper Base | Optional | ~10s per audio min |
| **Color + mux** | FFmpeg `curves` + `eq` + `concat` | Always | ~30s |

</details>

---

## 📦 Install

<table>
<tr>
<td width="50%" valign="top">

### 🪟 **Windows**
NSIS installer or portable .exe
```
AI-Video-Studio-1.0.0-x64.exe
```

### 🐧 **Linux**
AppImage (universal) or .deb
```
AI-Video-Studio-1.0.0-x64.AppImage
AI-Video-Studio-1.0.0-x64.deb
```

### 🍎 **macOS**
DMG for Apple Silicon or Intel
```
AI-Video-Studio-1.0.0-arm64.dmg
AI-Video-Studio-1.0.0-x64.dmg
```

</td>
<td width="50%" valign="top">

### ⏱️ First-launch timeline

```
00:00  ░░░░░░░░░░░░░░░░░░░░  Python + venv setup
01:30  ████░░░░░░░░░░░░░░░░  PyTorch + CUDA download
06:00  ████████░░░░░░░░░░░░  ComfyUI clone + deps
10:00  ████████████░░░░░░░░  Wan2.1 model download
14:00  ████████████████░░░░  Ollama LLM pull
17:00  ████████████████████  Ready! 🎉
```

After that, each video render takes **5–15 minutes**.

</td>
</tr>
</table>

<details>
<summary><b>🔧 Build from source instead</b></summary>

```bash
git clone https://github.com/06pratyush/ai-video-pipeline.git
cd ai-video-pipeline

# Windows
start.bat

# Linux / macOS
./start.sh
```

The launcher checks for Python 3.10+ and Node.js 18+, then runs the same bootstrap process as the installer.

</details>

---

## 💻 System Requirements

|                | 🟡 Minimum                | 🟢 Recommended            |
|----------------|----------------------------|----------------------------|
| 🎮 **GPU**     | NVIDIA · 8 GB VRAM · Wan2.1 1.3B | NVIDIA · 16 GB+ VRAM · Wan2.1 14B |
| 🧠 **RAM**     | 16 GB                      | 32 GB                      |
| 💾 **Disk**    | 30 GB free                 | 100 GB free                |
| 🖥️ **OS**      | Win 10 · Ubuntu 22.04 · macOS 12 | Win 11 · Ubuntu 24.04 · macOS 14 |
| 🐍 **Python**  | 3.10                       | 3.11                       |
| 📗 **Node.js** | 18 LTS                     | 20 LTS                     |

CPU-only mode runs but is very slow (~10× slower than CUDA). AMD GPUs aren't currently supported by Wan2.1 — track [this issue](https://github.com/Wan-AI/Wan2.1/issues) for ROCm progress.

---

## 🚀 Quick Start

After installation, the app shows a five-step onboarding card. Dismiss it and:

1. **Click + New Project** in the sidebar
2. **Paste your script** in the Script tab — anything from one sentence to several paragraphs
3. **Pick a Skill** — Documentary, Cinematic Story, Explainer, Social Short, Product Showcase, Tutorial, or News Brief. The Skill bundles voice, pacing, visual style, music mood, and post-processing into one preset.
4. **Switch to Render tab** and toggle the quality options you want (subtitles, music, frame interpolation, upscaling)
5. **Hit Generate Video** — the queue strip at the bottom shows live progress through 8 stages

When the render finishes, click `⬇ Download MP4` to save it, or `Show in folder` to open the output directory.

---

## 🎨 Skills

A Skill is a preset that determines the entire look and feel of the output. The default pack ships seven:

| Skill | Voice | Pacing | Aspect | Best For |
|-------|-------|--------|--------|----------|
| 🎥 **Documentary**     | 🇬🇧 George | 🐢 Slow   | 16:9 | Long-form narration, nature, history |
| 💡 **Explainer**       | 🇺🇸 Sarah  | 🚶 Medium | 16:9 | Concept videos, tutorials |
| 📦 **Product Showcase** | 🇺🇸 Michael | 🚶 Medium | 1:1  | Marketing, demos |
| 🎬 **Cinematic Story** | 🇬🇧 George | 🐢 Slow   | 16:9 | Storytelling, dramatic content |
| 📱 **Social Short**    | 🇺🇸 Heart  | 🏃 Fast   | 9:16 | TikTok, Reels, Shorts |
| 📚 **Tutorial**        | 🇺🇸 Nicole | 🚶 Medium | 16:9 | How-to content |
| 📰 **News Brief**      | 🇺🇸 Adam   | 🏃 Fast   | 16:9 | News updates, recaps |

Each Skill bundles a prompt template, voice + speed, scene pacing hint, music mood, and post-processing chain (color grade, film grain, letterbox). Custom Skills are JSON files in `app/skills/` — duplicate one to make your own.

> 💡 **Pro tip:** Pick a Skill that matches your target platform. Social Short auto-formats for vertical mobile with subtitles enabled; Documentary applies cinematic letterbox bars and slow pacing.

---

## ⚙️ Quality Settings

The Render tab exposes four toggles independent of the Skill:

| Toggle | Backend Module | Cost |
|--------|----------------|------|
| 💬 **Subtitles**          | faster-whisper transcription → FFmpeg subtitle burn | ~10s per minute of audio |
| 🎵 **Background Music**   | MusicGen mood-matched composition + auto-ducking mix | ~30s per scene |
| ⚡ **Frame Interpolation** | FFmpeg minterpolate (RIFE-compatible swap-in) | +30% render time |
| 📈 **Upscaling**          | FFmpeg super2xbr+lanczos (Real-ESRGAN swap-in) | +20% render time |

Skills auto-enable some toggles by default (e.g. Social Short turns on subtitles because mobile viewers watch muted).

---

## 📚 Templates, Versions, Batch

After your first successful render, three workflow accelerators become useful:

<table>
<tr>
<td width="33%" valign="top" align="center">

### 📋 Templates

Save reusable presets with skill, voice, scenes, quality settings.  
Apply with two clicks.

</td>
<td width="33%" valign="top" align="center">

### 🕘 Version History

Every render auto-snapshots script + prompts + final MP4.  
Restore any earlier version.

</td>
<td width="33%" valign="top" align="center">

### 🔁 Batch Generation

Queue 10 projects at once.  
Optionally apply one template to all.  
Renders sequentially overnight.

</td>
</tr>
</table>

---

## ⚙️ Architecture

Three-tier system designed so each layer can evolve independently:

```
╔══════════════════════════════════════════════════════════════╗
║  🖥️  ELECTRON FRONTEND      React 18 · Vite · Zustand · TW   ║
║  ──────────────────────                                      ║
║  • Project library · script editor · render panel            ║
║  • Real-time WebSocket progress · live VRAM meter            ║
║  • Model browser · template browser · batch modal            ║
╚════════════════════════════╤═════════════════════════════════╝
                             │   REST + WebSocket
                             │   http://localhost:7860
                             ▼
╔══════════════════════════════════════════════════════════════╗
║  🐍 PYTHON BACKEND DAEMON   FastAPI · SQLAlchemy · uvicorn   ║
║  ──────────────────────                                      ║
║  • Generation queue (SQLite persistence, survives restarts)  ║
║  • VRAM-aware model lifecycle, smart fallback routing        ║
║  • Scene cache (sha256 of prompt+seed+model+resolution)      ║
║  • 11 REST routes · 1 WebSocket · auto-update checker        ║
╚═══════╤═══════════════════╤══════════════════╤═══════════════╝
        ▼                   ▼                  ▼
   ┌─────────┐         ┌─────────┐         ┌─────────┐
   │ Ollama  │         │ ComfyUI │         │ FFmpeg  │
   │ Gemma   │         │ Wan2.1  │         │ Kokoro  │
   │ + LLMs  │         │ + nodes │         │ Whisper │
   └─────────┘         └─────────┘         └─────────┘
        ▲                   ▲                  ▲
        │              spawned as              │
        └────── subprocesses by daemon ────────┘
```

The frontend talks to the backend only via REST + WebSocket on `localhost:7860`. All ML work happens in Python. The Electron shell is purely a presentation layer.

<details>
<summary><b>📂 Repository layout</b></summary>

```
ai-video-pipeline/
│
├── 🚀 start.bat / start.sh       ← platform launchers
├── 📖 README.md
├── 📜 LICENSE
│
├── 📦 installer/
│   ├── bootstrap.py              ← first-run dependency installer
│   ├── system_check.py
│   └── catalog.json              ← available models metadata
│
└── 🎬 app/
    ├── backend/                  ← FastAPI daemon (Python)
    │   ├── main.py, daemon.py, db.py, version.py
    │   ├── routes/               ← 11 REST endpoints
    │   ├── services/             ← queue, cache, VRAM, registry
    │   ├── pipeline/             ← Gemma, Kokoro, Wan, Whisper, MusicGen,
    │   │                            XTTS, RIFE, ESRGAN, FFmpeg
    │   └── models/               ← SQLAlchemy ORM
    │
    ├── frontend/                 ← Electron + React + Vite
    │   ├── electron/main.ts + preload.ts
    │   └── src/components/       ← React UI
    │
    ├── runtime/                  ← created at first launch
    │   ├── python/               ← bundled venv
    │   ├── comfyui/              ← cloned ComfyUI
    │   └── models/               ← downloaded weights
    │
    ├── skills/                   ← 7 JSON Skill presets
    └── projects/                 ← user projects per-id
```

</details>

---

## 🛠️ Build from source

Build the desktop installers yourself if you don't want to use the GitHub releases:

```bash
cd app/frontend
npm install
npm run build:win     # Windows: NSIS .exe + portable .exe
npm run build:linux   # Linux: AppImage + .deb
npm run build:mac     # macOS: DMG + zip (x64 + arm64)
npm run build:all     # All three platforms (requires macOS host for proper signing)
```

Artifacts land in `app/frontend/release/`. Code signing requires the matching host OS — macOS DMGs must be built on macOS for notarization to work.

---

## 🐛 Troubleshooting

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

Open an issue on GitHub if you hit a symptom not covered above — include OS, GPU model, VRAM, and the exact reproduction steps.

---

## 🤝 Contributing

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

Run `npm run typecheck` in `app/frontend/` and ensure the backend boots with `python -m uvicorn app.backend.main:app` before opening a PR.

---

## 📜 License

[MIT](LICENSE) — use it, modify it, distribute it freely. Attribution appreciated but not required.

---

## 🙏 Acknowledgements

Built on the shoulders of these excellent open-source projects:

<table>
<tr>
<td valign="top" width="50%">

**🎬 AI Models**
- [Wan2.1](https://github.com/Wan-AI/Wan2.1) · text-to-video
- [Gemma](https://ai.google.dev/gemma) · LLM for script work
- [Kokoro TTS](https://github.com/hexgrad/kokoro) · text-to-speech
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) · transcription
- [MusicGen](https://github.com/facebookresearch/audiocraft) · music gen
- [XTTS v2](https://github.com/coqui-ai/TTS) · voice cloning

</td>
<td valign="top" width="50%">

**🏗️ Runtime & Frameworks**
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) · diffusion node runtime
- [Ollama](https://ollama.com) · local LLM serving
- [FFmpeg](https://ffmpeg.org) · multimedia framework
- [Electron](https://www.electronjs.org/) + [React](https://react.dev/) + [Vite](https://vitejs.dev/)
- [FastAPI](https://fastapi.tiangolo.com/) + [SQLAlchemy](https://www.sqlalchemy.org/)
- [Tailwind CSS](https://tailwindcss.com/) + [Zustand](https://zustand-demo.pmnd.rs/)

</td>
</tr>
</table>

---

<div align="center">

### 🎬 *Built for creators who want full control over their AI content pipeline.*

**No subscriptions · No rate limits · No data leaving your machine.**

<br>

<sub>
⭐ <a href="https://github.com/06pratyush/ai-video-pipeline/stargazers">Star this repo</a> if it's useful ·
🐛 <a href="https://github.com/06pratyush/ai-video-pipeline/issues">Report an issue</a> ·
💬 <a href="https://github.com/06pratyush/ai-video-pipeline/discussions">Discuss</a>
</sub>

<br><br>

<sub>Made with 💜 · Released under the MIT License · v1.0.0</sub>

</div>
