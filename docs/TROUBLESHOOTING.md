# Troubleshooting

A reference for the symptoms most likely to come up in real use, ordered roughly by frequency.

## Setup & Boot

### Setup screen stalls on PyTorch install

Slow disk or slow network is the usual cause — PyTorch with CUDA is a 2.5 GB download. Open the log viewer at the bottom of the SetupScreen and watch the bytes/sec.

If it's been more than 20 minutes with no progress messages:
1. Click the retry button on the failed step
2. If retry doesn't work, close the app and rerun `start.bat` / `start.sh` from a terminal
3. Inspect `app/runtime/python/` — if it exists but is empty, delete the folder and run again

### "Python 3.10+ is required but was not found"

The launcher checks `python --version` on PATH. On Windows:
- Reinstall Python from python.org with "Add to PATH" checked
- Or run the bootstrap manually: `py -3.11 installer/bootstrap.py`

On Linux/macOS install via your package manager (`apt install python3.11`, `brew install python@3.11`).

### "Node.js 18+ not found" warning

You can still run the backend without Node.js — open `http://localhost:7860/docs` for the OpenAPI explorer. For the full GUI, install Node.js 20 LTS from nodejs.org.

### App opens but stays on "Starting up…" forever

The backend isn't reachable on port 7860. Check:
1. Open `http://localhost:7860/system/health` in a browser — should return `{"status":"ok"}`
2. If timeout, the daemon failed to start. Look in the system tray for a hidden console window with the traceback
3. Port 7860 might be in use. Find the conflicting process: `netstat -ano | findstr 7860` (Windows) or `lsof -i :7860` (Linux/Mac)

## Generation

### "Cannot connect to Ollama at http://localhost:11434"

The Ollama subprocess crashed or wasn't started:

1. Open the Model Browser (sidebar → ⊞ Model Browser). The Installed tab should list at least one LLM. If empty, Ollama isn't running.
2. Run `ollama serve` in a terminal — leave it open
3. Verify with `ollama list`
4. Restart the AI Video Studio backend (close and reopen the app)

### "ComfyUI workflow not found"

The pipeline needs `wan_workflow_api.json` at the project root or in `app/workflows/`. Either:

1. Copy the bundled workflow: `cp app/workflows/wan_workflow_api.json ./` from the project root
2. Or export your own from a running ComfyUI: `Ctrl+Shift+Q` to switch to API format → `Ctrl+S` → rename to `wan_workflow_api.json`

### "CUDA out of memory" mid-generation

The VRAM manager should have caught this and downgraded — check the queue progress message for "Used wan2.1-1.3b instead of wan2.1-14b". If you still see OOM:

- Close other GPU-using apps (Chrome with hardware accel uses 1–2 GB)
- In the Render tab, disable Upscaling and Interpolation (each adds GPU memory pressure)
- Reduce scene count from 8 to 3–4 — fewer parallel cache writes
- Restart the daemon to fully reset GPU state
- If on 6 GB or less, your GPU is genuinely too small for Wan2.1. Use AnimateDiff (smaller, lower quality) via a custom Skill

### Generation finishes but `final.mp4` is missing/black

Check `app/projects/{project-id}/`:

- `final/merged.mp4` exists but `final.mp4` doesn't → post-processing failed. Look at the daemon log for FFmpeg stderr
- `scenes/*.mp4` files are 0 bytes → ComfyUI returned but didn't write properly. Re-run with locked scenes disabled (regenerate everything)
- All files missing → the queue worker crashed early. Check the daemon console for a Python traceback

### Subtitles are wildly wrong

Whisper Base is a small model with limited accuracy. Options:

- Try a slower, clearer voice (Sarah, George, or Adam tend to transcribe well)
- Use a less stylized Skill — Documentary or Tutorial have cleaner pacing for Whisper
- Manually edit `app/projects/{id}/audio/subtitles.srt` and re-run only the subtitle stage (TODO: surface this in the UI)

### Background music drowns out narration

The mix ratio is hardcoded to 12% music / 100% narration. If music still feels loud:

1. Open `app/backend/pipeline/ffmpeg_merger.py`
2. Find `music_volume: float = 0.12` and reduce to `0.08` or `0.06`
3. Restart the daemon

A user-tunable music volume slider is on the Phase 9 roadmap.

## Quality

### Wan2.1 generates blurry, low-detail frames

This is mostly the 1.3B model showing its age. Things that help:

- Lengthen the prompt — Skills already prepend a template, but the LLM-generated portion can be vague. Edit scenes directly in the Scenes tab
- Enable Upscaling in the Render tab (2× super2xbr noticeably sharpens edges)
- If you have 16 GB+ VRAM, install Wan2.1 14B via the bootstrap on rerun

### Audio is faster/slower than the video

The pipeline matches audio duration as the source of truth — video is looped or trimmed to fit. If the result feels off:

- Lower the Skill's `voice_speed` (e.g. Documentary 0.95 → 0.85) for slower, more emphatic narration
- Increase scene count so you have more video footage per second of audio

### Output has black bars on a 16:9 screen

Your Skill is producing 9:16 (Social Short) or 1:1 (Product). Either change Skill or duplicate the JSON and edit `aspect_ratio`.

## Templates / Versions / Batch

### "Save as Template" doesn't appear

Make sure a project is selected in the sidebar — the button only shows for active projects.

### Restored version still shows new scenes

`restore` writes the snapshot's prompts onto existing scene rows. It doesn't delete or re-create scenes. If your snapshot had fewer scenes than the current project, the extra scenes are left untouched.

To get a clean restore, manually delete extra scenes in the Scenes tab before clicking Restore, or apply the version's template to a new project.

### Batch fails after 2 successful projects

Disk space — each project uses ~500 MB at maximum quality. Check `app/projects/` and prune old projects, or move them to external storage.

## Performance

### Generation is much slower than the docs say

Check `nvidia-smi` while a render is in progress:

- `Compute Mode: Default` — good
- `Compute Mode: E. Process` — another process has exclusive access; close it
- Power state stuck at P8 — Windows power plan throttling; switch to High Performance
- Temperature above 85°C — thermal throttling; clean fans or limit concurrent loads

### App uses 4+ GB of RAM at idle

Electron + React + FastAPI + the model registry adds up. To reduce:

- Close the Model Browser when not in use
- Background Vite dev mode if you're running from source — use the packaged version instead

### Boot takes 30+ seconds

The `/system/status` route runs `nvidia-smi` synchronously on first call. This is cached for 15 s after the first hit, so subsequent navigations are fast. To speed up first boot:

- Pre-warm the cache: open `http://localhost:7860/system/status` in a browser before clicking the app icon
- Or accept the one-time delay — it only blocks BootScreen, not the actual app

## Reporting bugs

If none of the above fixes it, file an issue at https://github.com/06pratyush/ai-video-pipeline/issues with:

1. OS + GPU model + VRAM
2. Output of `nvidia-smi` and `python --version`
3. Daemon log: `app/backend/daemon.log` if present, or copy from the console window
4. Reproduction steps — the exact script + Skill + quality settings that triggered the issue
