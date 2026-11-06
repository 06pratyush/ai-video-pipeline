# Contributing to AI Video Studio

Thanks for considering a contribution. AI Video Studio is a local-first, open-source AI video
generator, maintained by a very small team — so this guide is deliberately specific about what gets
merged and why. Reading the two short sections below before you write code will save you the most
time.

**The bar for any incoming change:**

1. **It must work end-to-end.** No half-implemented features parked behind a flag and forgotten.
2. **It must respect the local-first principle.** No cloud calls, no telemetry, no remote licence
   checks, no phoning home. This is the one rule with no exceptions.
3. **It must not regress existing flows.** Every change should leave the happy path at least as
   good as it was.

**Contents**

- [Ways to contribute](#ways-to-contribute)
- [The one rule that fails CI](#the-one-rule-that-fails-ci)
- [Setup for development](#setup-for-development)
- [Code style](#code-style)
- [Adding a Skill](#adding-a-skill)
- [Adding a pipeline module](#adding-a-pipeline-module)
- [Architecture conventions](#architecture-conventions)
- [Testing](#testing)
- [Raising a pull request](#raising-a-pull-request)
- [What happens next](#what-happens-next)

Once your pull request is open, everything about how it is reviewed, approved and merged is
documented in **[REVIEW_AND_MERGE.md](REVIEW_AND_MERGE.md)** — what blocks a merge, how review
comments are prioritised, and how long you should expect to wait.

---

## Ways to contribute

You do not need to write Python to be useful here. Roughly easiest first:

| Contribution | Skill needed | Where |
|---|---|---|
| **Report a bug** | None — just a reproduction | [New issue](https://github.com/06pratyush/ai-video-pipeline/issues/new/choose) |
| **Improve the docs** | Writing | `README.md`, this file |
| **Add a Skill** (style preset) | JSON only | `app/skills/` — see [Adding a Skill](#adding-a-skill) |
| **Add a colour grade** | FFmpeg filters | `pipeline/ffmpeg_merger.py` |
| **Add a voice or music mood** | Python, small | `pipeline/kokoro_tts.py`, `pipeline/musicgen_client.py` |
| **Write tests** | Python, pytest | `app/backend/tests/` — coverage is a Phase 9 goal |
| **Add a pipeline module** | Python + the tool | `app/backend/pipeline/` — see [Adding a pipeline module](#adding-a-pipeline-module) |
| **Real-ESRGAN / RIFE nodes** | ComfyUI internals | Replace the FFmpeg fallbacks with native nodes |
| **AMD ROCm support** | CUDA/ROCm porting | A working Wan2.1 path for non-NVIDIA GPUs |

Issues labelled [`good first issue`](https://github.com/06pratyush/ai-video-pipeline/labels/good%20first%20issue)
are scoped so you do not need to understand the whole pipeline to finish them.
[`help wanted`](https://github.com/06pratyush/ai-video-pipeline/labels/help%20wanted) marks work
that is wanted but unclaimed.

**Open an issue before starting anything large.** A design disagreement costs one comment at the
issue stage and a full rewrite at the pull request stage. For a typo or a one-line fix, go straight
to the pull request.

---

## The one rule that fails CI

`CONTEXT.md` is this project's persistent memory: the stack, the architectural rules, the known
shortcomings, and an append-only log of every change that reached `main`. It is the file the next
reader — human or AI agent — trusts, so it is never allowed to go stale.

**Every pull request into `main` must append an entry to section 5 of `CONTEXT.md`.** This is not a
convention; it is enforced by
[`.github/workflows/enforce-context-sync.yml`](.github/workflows/enforce-context-sync.yml), which
fails your pull request if `CONTEXT.md` is unchanged or changed by fewer than three lines. Touching
the file to go green does not work — that is the exact failure mode the gate exists to catch.

Append a block in this shape at the end of section 5:

```markdown
- **Timestamp:** 2026-11-06T14:30:00Z
- **Trigger Event:** Pull Request
- **Author/Agent:** your-github-handle
- **Target Subsystem:** `app/backend/pipeline/` (the files you actually touched)
- **Intent:** One or two sentences: what this change is for, and why now.
- **Bugs Discovered:** What was broken, or "None."
- **Fixes Applied:** What you changed to fix it, or "N/A."
- **Verification:** How you know it works — the commands you ran and what they printed. If you
  could not verify something, say so plainly; an honest gap is useful and a false claim is not.
- **Context Modifications:** New files, new dependencies, schema changes, or "None."

---
```

If your change closes or introduces a known shortcoming, update section 4
(`CURRENT SYSTEM GAPS`) in the same commit. Removing a `[GAP-nn]` you have genuinely fixed is one of
the most welcome things you can put in a pull request.

---

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

## Raising a pull request

### Before you push

```bash
cd app/frontend && npm run typecheck          # must be clean, zero errors
python -m uvicorn app.backend.main:app        # must boot without a traceback
python -m pytest app/backend/tests/           # needs httpx (a test-only dependency)
```

Then run one real 1-scene render with the default Skill. If you touched the pipeline, run a second
with every quality toggle enabled. No CI can do this for you — the models are local — so this manual
pass is the only thing standing between a change and a broken release.

### The mechanics

1. **Fork** the repository, unless you have write access.

2. **Branch from `main`** with a conventional prefix, so the branch name says what it is:

   | Prefix | For |
   |---|---|
   | `feat/` | A new capability |
   | `fix/` | A bug fix |
   | `docs/` | Documentation only |
   | `refactor/` | No behaviour change |
   | `test/` | Tests only |
   | `chore/` | Build, CI, dependencies, tooling |
   | `perf/` | Performance work |

   ```bash
   git checkout -b fix/comfyui-hang-on-windows
   ```

3. **Commit in logical units.** One commit per coherent change — do not squash four unrelated fixes
   into one, and do not spread one fix across six "wip" commits. Messages use imperative mood,
   sentence case, no trailing period, with a body explaining *why* when the subject cannot:

   ```
   Fix ComfyUI hang when VRAM is exhausted mid-render

   The lazy-start path waited on a ready probe that never returns once
   the CUDA allocator has failed, so the worker thread blocked forever
   and the queue item stayed in `running`. Bound the probe and treat a
   timeout as a terminal error, which [RULE-05] requires.

   Fixes #123
   ```

   Link issues with `Fixes #123` or `Closes #123` so the issue closes on merge.

4. **State a changelog line** in the pull request description, under the right
   [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) heading (`Added`, `Changed`, `Fixed`,
   `Removed`). One line, written for a user rather than a reviewer. The changelog itself is
   maintained outside the repository, so the merging maintainer transfers your line into it — which
   means if you do not write one, nobody can.

5. **Append your `CONTEXT.md` entry** — see
   [The one rule that fails CI](#the-one-rule-that-fails-ci). This is the step people forget.

6. **Push and open the pull request against `main`.** The
   [pull request template](.github/PULL_REQUEST_TEMPLATE.md) loads automatically; fill it in rather
   than deleting it. Reviewers read it before they read your diff, and a filled template is the
   difference between a one-pass review and four rounds of questions.

7. **Mark it a draft** if it is not ready for review. A draft says "I want early feedback on the
   approach"; a ready pull request says "I believe this is mergeable." Both are welcome — just say
   which one you mean.

### Keep it reviewable

A 200-line pull request gets a careful review. A 2,000-line pull request gets a shallow one, which
is worse for you. If your change is large, split it:

- Mechanical refactors go in their own pull request, merged first.
- A new pipeline module and the code that calls it can be two pull requests.
- Generated files, lockfile churn and formatting-only changes belong in separate commits at minimum,
  and preferably separate pull requests, so the real diff stays visible.

---

## What happens next

Review, approval and merge are covered in full in **[REVIEW_AND_MERGE.md](REVIEW_AND_MERGE.md)**.
The short version:

- A maintainer makes a first pass within **5 working days**. If nothing has happened after a week, a
  single comment on the thread is a welcome nudge, not a nuisance.
- Review comments are labelled **blocking**, **should-fix** or **nit**, so you always know what must
  change before merge and what is a suggestion you may decline.
- You need **one maintainer approval** and **green CI**, including the `CONTEXT.md` gate.
- Maintainers merge, not contributors, using **squash and merge** so `main` keeps one commit per
  change.

Expect some back-and-forth on style and design. The questions are aimed at whether the change still
holds up six months from now, not at you — and a reviewer asking "why this way?" usually means they
are taking the contribution seriously.

---

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). In short: be kind, be
specific, be patient. Bug reports and feature ideas are welcome; bad-faith arguments and personal
attacks are not.

To report a security vulnerability, do **not** open a public issue — follow
[SECURITY.md](SECURITY.md) instead.
