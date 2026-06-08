# Contributing

Thanks for considering a contribution. This project is built and maintained by a small team, so the bar for incoming changes is:

1. **It must work end-to-end** — no half-implemented features that get added behind a flag and forgotten
2. **It must respect the local-first principle** — no cloud calls, no telemetry, no remote license checks
3. **It must not regress existing flows** — every change should leave the happy path at least as good as it was

## Setup for development

```bash
git clone https://github.com/06pratyush/ai-video-pipeline.git
cd ai-video-pipeline

# Backend
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r app/backend/requirements.txt
python -m uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 7860

# Frontend (separate terminal)
cd app/frontend
npm install
npm run dev
```

The frontend's `dev` script runs Vite + Electron concurrently. Electron picks up the backend at `localhost:7860`. If you only need the renderer, use `npm run dev:vite` and open `http://localhost:5173` in a browser.

## Code style

### TypeScript / React

- Functional components only (no class components)
- Hooks for state — `useState`, `useEffect`, Zustand for global state
- Tailwind classes for styling — keep `className` strings readable, break lines if they exceed ~120 chars
- Prefer `interface` for shapes that might be extended, `type` for unions/intersections
- Run `npm run typecheck` before pushing — no `any` types in committed code unless absolutely necessary (and commented why)

### Python

- Type hints on all function signatures: `def foo(x: int) -> str`
- `from __future__ import annotations` not needed — we target 3.10+
- Pydantic v2 models for API request/response bodies
- SQLAlchemy 2.0 style ORM (no legacy Query API)
- Print debugging is OK during development; add `logging.getLogger(__name__)` in production code paths

### Commit messages

Imperative mood, sentence case, no trailing period:

```
Phase 5: Quality layer — subtitles, music, interpolation, upscaling

- whisper_client.py: faster-whisper transcription → SRT
- musicgen_client.py: mood-to-prompt mapping
- ...
```

Reference an issue if applicable: `Fix #123: ComfyUI hang on Windows`

## Adding a Skill

Skills are pure JSON. Create `app/skills/my-skill.json`:

```json
{
  "id": "my-skill",
  "name": "My Skill",
  "description": "One-line summary shown in the picker",
  "voice": "af_sarah",
  "voice_speed": 1.0,
  "scene_pacing": "medium",
  "prompt_template": "{narration_chunk}, your style hints here",
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "subtitles": false,
  "music_mood": "ambient_score",
  "post_processing": ["color_grade_cinematic"],
  "icon": "my-skill.svg"
}
```

Available `post_processing` effects (defined in `ffmpeg_merger.py`):

- `color_grade_cinematic` — teal/orange film look
- `color_grade_documentary` — warm, natural, slight desaturation
- `color_grade_bright` — high contrast, neutral-cool
- `color_grade_vibrant` — max saturation, high contrast
- `color_grade_product` — clean, neutral
- `color_grade_news` — slight desaturation, high contrast
- `color_grade_tutorial` — clean neutral
- `letterbox` — 2.39:1 black bars
- `film_grain` — heavy noise
- `film_grain_subtle` — light noise

Available `music_mood` values map to MusicGen prompts in `musicgen_client.py`. Add new ones there if needed.

Available `voice` IDs (all Kokoro):
- `af_heart`, `af_bella`, `af_sarah`, `af_nicole` (American female)
- `am_adam`, `am_michael` (American male)
- `bf_emma` (British female)
- `bm_george` (British male)

## Adding a pipeline module

For a new processing stage (e.g. a different upscaler), create `app/backend/pipeline/your_client.py`:

```python
"""Your module — one-line description."""
from pathlib import Path

try:
    import your_dependency
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def is_available() -> bool:
    return _AVAILABLE


def your_function(input_path: str, output_path: str, ...) -> str:
    if not _AVAILABLE:
        raise ImportError("your_dependency not installed.")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    # ... do work ...
    return output_path
```

Then wire it into `generation_queue.py` at the appropriate pipeline step. Always wrap optional stages in `try/except` with a clear `print` so failures degrade gracefully — never crash the whole pipeline because an optional quality stage failed.

## Architecture conventions

### Where to put what

- **HTTP route handlers** → `app/backend/routes/`. Keep them thin — call into services
- **Business logic** → `app/backend/services/`. These are reusable across routes
- **External tool wrappers** → `app/backend/pipeline/`. One file per tool (Kokoro, Whisper, etc.)
- **Database models** → `app/backend/models/`. SQLAlchemy ORM only — no business logic
- **Frontend components** → `app/frontend/src/components/`. One file per major UI element
- **Frontend state** → `app/frontend/src/stores/`. Zustand stores — keep them small

### Migration handling

If you add a column to an existing table, add the migration to `db.py` `_run_migrations()`:

```python
migrations = [
    "ALTER TABLE queue_items ADD COLUMN render_opts TEXT",
    "ALTER TABLE my_table ADD COLUMN new_field TEXT",  # ← your addition
]
```

The migration runs every startup but is idempotent (the `try/except: pass` swallows "column already exists" errors).

For new tables, just add the import to `init_db()` — `create_all()` handles creation.

### Frontend / backend boundary

The frontend talks to the backend via:
- `fetch('http://localhost:7860/...')` for request/response
- `new WebSocket('ws://localhost:7860/generation/ws/{id}')` for progress streams

Both go through `app/frontend/src/api/backend.ts`. Add new endpoints there with their TypeScript types so the rest of the frontend is type-safe.

## Testing

We currently rely on manual testing — automated test coverage is a Phase 9 goal. Before pushing:

1. `cd app/frontend && npm run typecheck` — zero errors
2. Backend starts cleanly: `python -m uvicorn app.backend.main:app`
3. End-to-end run of a 1-scene project with default Skill
4. (If touching the pipeline) end-to-end run with all quality opts enabled

## Opening a PR

1. Branch from `main`: `git checkout -b feature/your-change`
2. Make commits per logical unit (don't squash unrelated changes into one mega-commit)
3. Update CHANGELOG.md under the `## Unreleased` heading
4. Push and open a PR against `main`
5. PR description should answer:
   - What problem does this solve?
   - What's the approach?
   - How did you test it?
   - Any breaking changes?

We review PRs within a week; expect some back-and-forth on style and design. Don't take it personally — the questions are aimed at making sure the change holds up six months from now.

## Code of conduct

Be kind, be specific, be patient. Bug reports and feature ideas are welcome; bad-faith arguments and personal attacks are not. We reserve the right to lock or close issues that don't move toward a constructive resolution.
