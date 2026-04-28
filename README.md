# AI Video Pipeline

> Generate fully narrated AI videos from a text script — locally, for free, with no cloud dependency.

Give it a script. It refines the narration with **Gemma**, synthesizes a voice with **Kokoro TTS**, generates cinematic video clips with **Wan2.1**, and stitches everything into a platform-ready MP4 using **FFmpeg** — all running on your own machine.

---

## Demo Output

```
Input  : "Artificial intelligence is reshaping how we create content..."
Output : outputs/final/ai_introduction_instagram.mp4  (24.7 MB, 30 sec)
         outputs/final/ai_introduction_youtube.mp4    (48.2 MB, 30 sec)
```

---

## How It Works

```
Your Script (.txt)
      │
      ▼
 [Gemma via Ollama]       ← refines narration, generates scene-by-scene video prompts
      │
      ▼
 [Kokoro TTS]             ← converts narration to natural-sounding voice audio (.wav)
      │
      ▼
 [Wan2.1 via ComfyUI]     ← generates video clips from prompts (runs on your GPU)
      │
      ▼
 [FFmpeg]                 ← merges video + audio, exports for Instagram / YouTube
      │
      ▼
 Final MP4
```

---

## Features

- **Fully local** — no API keys, no cloud services, no usage fees
- **Gemma-powered scriptwriting** — automatically refines your raw notes into clean narration and generates detailed cinematic prompts per scene
- **Natural voice synthesis** — Kokoro TTS with 8 voice options (American/British, male/female)
- **AI video generation** — Wan2.1 produces high-quality short clips from text prompts
- **Platform-ready export** — automatic formatting for Instagram Reels (1080×1920) and YouTube (1920×1080)
- **Fully scriptable** — single command runs the entire pipeline end to end
- **Modular design** — each component (TTS, video, merge) is an independent module you can swap out

---

## Prerequisites

Before installing this project, you need three external tools set up:

| Tool | Purpose | Install |
|------|---------|---------|
| **Ollama** | Runs Gemma locally | https://ollama.com |
| **ComfyUI + Wan2.1** | Runs the video generation model | https://github.com/comfyanonymous/ComfyUI |
| **FFmpeg** | Merges video and audio | https://ffmpeg.org/download.html |
| **espeak-ng** | Required by Kokoro TTS | https://github.com/espeak-ng/espeak-ng/releases |

**GPU:** NVIDIA GPU with 8GB+ VRAM required for Wan2.1.  
**Python:** 3.11 recommended.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-video-pipeline.git
cd ai-video-pipeline
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv311
venv311\Scripts\activate

# Linux / Mac
python -m venv venv311
source venv311/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install requests
pip install kokoro>=0.9.4
pip install soundfile
pip install numpy
pip install websocket-client
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

> Note: For PyTorch, select the correct CUDA version for your GPU at https://pytorch.org/get-started/locally/

### 4. Pull Your Gemma Model via Ollama

```bash
ollama pull gemma3
# or whichever model you want to use
```

### 5. Set Up ComfyUI + Wan2.1

Follow the detailed setup guide in [`docs/comfyui_setup.md`](docs/comfyui_setup.md) — covers model download, custom node installation, and workflow export.

### 6. Export Your ComfyUI Workflow

1. Open `http://localhost:8188` in your browser
2. Load your Wan2.1 workflow
3. Press `Ctrl + Shift + Q` to switch to API format
4. Press `Ctrl + S` to save
5. Rename the downloaded file to `wan_workflow_api.json`
6. Place it in the root of this project folder

> This file is machine-specific and is excluded from version control via `.gitignore`.

---

## Configuration

Open `orchestrator.py` and update these values at the top to match your setup:

```python
OLLAMA_URL  = "http://localhost:11434"   # Ollama address (default)
GEMMA_MODEL = "gemma3"                   # Must match your ollama list output
```

To check your exact model name:
```bash
ollama list
```

---

## Usage

### Start Required Services

You need three terminals running before using the pipeline.

**Terminal 1 — Ollama:**
```bash
ollama serve
```

**Terminal 2 — ComfyUI:**
```bash
cd path/to/ComfyUI
venv\Scripts\activate        # Windows
python main.py --listen 0.0.0.0 --port 8188
```

**Terminal 3 — Pipeline:**
```bash
cd ai-video-pipeline
venv311\Scripts\activate     # Windows
```

### Run the Pipeline

**Basic usage:**
```bash
python orchestrator.py --script scripts/ai_intro.txt --topic "AI Introduction"
```

**Full options:**
```bash
python orchestrator.py \
  --script scripts/ai_intro.txt \
  --topic "AI Introduction" \
  --voice af_sarah \
  --scenes 2 \
  --target instagram
```

**All in one line (Windows PowerShell):**
```powershell
python orchestrator.py --script scripts\ai_intro.txt --topic "AI Introduction" --voice af_sarah --scenes 2 --target instagram
```

### All Options

| Flag | Default | Description |
|------|---------|-------------|
| `--script` | — | Path to your `.txt` script file |
| `--text` | — | Inline script text (alternative to `--script`) |
| `--topic` | required | Label used for output file naming |
| `--voice` | `af_sarah` | Kokoro voice ID (see voice table below) |
| `--scenes` | `2` | Number of video clips to generate |
| `--target` | `both` | Output format: `instagram`, `youtube`, or `both` |
| `--no-refine` | off | Skip Gemma refinement, use script as-is |

### Voice Options

| Voice ID | Gender | Accent | Best For |
|----------|--------|--------|----------|
| `af_sarah` | Female | American | General, conversational |
| `af_bella` | Female | American | Warm, friendly |
| `af_heart` | Female | American | Energetic, upbeat |
| `af_nicole` | Female | American | Professional |
| `am_adam` | Male | American | Authoritative |
| `am_michael` | Male | American | Deep, documentary |
| `bf_emma` | Female | British | Formal, educational |
| `bm_george` | Male | British | Narration, serious |

---

## Folder Structure

```
ai-video-pipeline/
│
├── orchestrator.py          # Main pipeline script — runs everything
├── kokoro_tts.py            # Kokoro TTS module — text to audio
├── wan_client.py            # ComfyUI API client — submits video jobs
├── ffmpeg_merger.py         # FFmpeg module — merges video + audio
│
├── wan_workflow_api.json    # Your ComfyUI workflow (machine-specific, not in git)
├── requirements.txt         # Python dependencies
├── .gitignore               # Excludes outputs, venvs, workflow JSON
│
├── scripts/                 # Put your input .txt script files here
│     └── ai_intro.txt
│
├── outputs/
│     ├── audio/             # Generated .wav voice files
│     ├── video/             # Raw Wan2.1 video clips
│     └── final/             # Merged, platform-ready MP4 files
│
├── venv311/                 # Python virtual environment (not in git)
└── docs/                    # Setup guides and documentation
```

---

## Requirements

Full `requirements.txt`:

```
requests>=2.31.0
kokoro>=0.9.4
soundfile>=0.12.1
numpy>=1.24.0
websocket-client>=1.6.0
torch>=2.1.0
torchvision>=0.16.0
torchaudio>=2.1.0
```

**System requirements:**

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU VRAM | 8 GB | 16 GB+ |
| RAM | 16 GB | 32 GB |
| Disk space | 60 GB | 100 GB |
| Python | 3.10 | 3.11 |
| OS | Windows 10 / Ubuntu 20.04 | Windows 11 / Ubuntu 22.04 |

---

## Expected Output Timeline

| Step | What Runs | Time |
|------|-----------|------|
| Script refinement | Gemma via Ollama | ~10 sec |
| Prompt generation | Gemma via Ollama | ~10 sec |
| Voice synthesis | Kokoro TTS | ~5 sec |
| Video clip (per scene) | Wan2.1 via ComfyUI | ~8 min |
| Merge + export | FFmpeg | ~30 sec |
| **Total (2 scenes)** | | **~17 min** |

---

## Troubleshooting

**`[ERROR] Cannot connect to Ollama`**
→ Run `ollama serve` in a separate terminal first.

**`500 Internal Server Error` from Ollama**
→ Wrong model name. Run `ollama list` and update `GEMMA_MODEL` in `orchestrator.py`.

**`FileNotFoundError: wan_workflow_api.json`**
→ Export the workflow from ComfyUI browser interface (`Ctrl+Shift+Q` → Save) and place it in the project root.

**`CUDA out of memory`**
→ Reduce `num_frames` to `49` in `orchestrator.py`, or use `--scenes 1`.

**Kokoro import error**
→ Make sure `espeak-ng` is installed system-wide and `venv311` is activated.

---

## Contributing

Contributions are welcome. Here is how to get involved:

1. **Fork** the repository on GitHub
2. **Create a branch** for your feature:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** and commit with clear messages:
   ```bash
   git commit -m "Add: subtitle generation via Whisper"
   ```
4. **Push** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
5. **Open a Pull Request** on GitHub with a description of what you changed and why

**Good first contributions:**
- Adding new FFmpeg export formats (TikTok, Twitter)
- Whisper integration for auto-subtitles
- Web UI wrapper using Gradio or Streamlit
- Support for AnimateDiff or LTX-Video as alternative video backends
- Prompt template library for different content niches

Please open an **Issue** before starting large changes so we can discuss the approach first.

---

## License

This project is licensed under the **MIT License** — see [`LICENSE`](LICENSE) for full terms.

In short: use it, modify it, distribute it freely. Attribution appreciated but not required.

---

## Acknowledgements

This project stands on the shoulders of several outstanding open-source efforts:

- **[Wan2.1](https://github.com/Wan-AI/Wan2.1)** by Wan-AI — the video generation model at the core of this pipeline
- **[Kokoro TTS](https://github.com/hexgrad/kokoro)** by hexgrad — lightweight, high-quality local text-to-speech
- **[ComfyUI](https://github.com/comfyanonymous/ComfyUI)** by comfyanonymous — the node-based interface that makes running local video models practical
- **[Ollama](https://ollama.com)** — frictionless local LLM serving that makes Gemma accessible via a simple API
- **[Gemma](https://ai.google.dev/gemma)** by Google DeepMind — the language model powering script refinement and prompt generation
- **[FFmpeg](https://ffmpeg.org)** — the indispensable open-source multimedia framework handling all video/audio processing

---

*Built for creators who want full control over their AI content pipeline — no subscriptions, no rate limits, no data leaving your machine.*
