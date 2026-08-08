# SYSTEM CONTEXT MANIFEST & EXECUTION TIMELINE

## 1. PROJECT IDENTIFICATION & OPERATIONAL STATE

- **Project Identifier:** AI-VIDEO-STUDIO
- **Operational Status:** STABLE (backend verified booting and serving; generation pipeline requires ComfyUI + models installed)
- **Architecture Style:** Domain-Driven Monolith — Electron/React frontend over a local FastAPI daemon
- **Primary Runtime:** Python 3.14 (`venv/`) / Node.js + Vite + Electron
- **System Purpose:** Turns a text script into a narrated, AI-generated video locally: LLM refines narration and scene prompts, Wan/ComfyUI renders clips, Kokoro synthesises speech, FFmpeg merges and post-processes.

## 2. TECHNICAL STACK MATRIX

| Layer | Technology | Version | Enforcement Rules |
| :--- | :--- | :--- | :--- |
| **API Gateway** | FastAPI + Uvicorn | 0.111+ / 0.29+ | Localhost-only (127.0.0.1:7860), Pydantic request models, WebSocket progress stream |
| **Relational DB** | SQLite via SQLAlchemy | 2.0+ | Declarative ORM, `SessionLocal` per unit of work, additive migrations in `db._run_migrations` |
| **LLM Engine** | Ollama (`gemma4:e4b`) | local | Subprocess-managed; only stopped if this app started it |
| **Video Compute** | ComfyUI + Wan 2.1 | local | Lazy start, VRAM-routed model selection |
| **Speech / Audio** | Kokoro TTS, faster-whisper, MusicGen | local | Optional deps degrade gracefully, never fatally |
| **Media Muxing** | FFmpeg | bundled/system | Temp files always cleaned in `finally` |

## 3. ARCHITECTURAL BOUNDARIES & RULES

1. [RULE-01]: `main.py` is wire-up only — routers, middleware, lifespan. No business logic.
2. [RULE-02]: Routes must not import from `services` upward or define pipeline logic; services must never import from `routes` (shared helpers belong in `models/` or `services/`).
3. [RULE-03]: The generation pipeline runs on a background worker thread, never inside a request handler.
4. [RULE-04]: Version metadata lives only in `app/backend/version.py`. Nothing may import `VERSION` from `main`.
5. [RULE-05]: Every terminal queue state (`done`/`error`/`cancelled`) must set both a status and `completed_at`. No code path may leave an item in `running`.
6. [RULE-06]: Any operation that overwrites user content must snapshot the prior state first.

## 4. CURRENT SYSTEM GAPS & KNOWN SHORTCOMINGS

- [GAP-01]: Deleting a project removes its DB rows but leaves generated media under `app/projects/<id>/` on disk. Intentional for now (avoids irreversible bulk deletion) but leaks storage.
- [GAP-02]: `datetime.utcnow()` is used throughout the models and queue; deprecated in Python 3.12+ and will eventually need `datetime.now(timezone.utc)`.
- [GAP-03]: No auth on the daemon. Acceptable only because it binds to 127.0.0.1; CORS is currently `allow_origins=["*"]` and should be narrowed to the Electron origin.
- [GAP-04]: End-to-end render (ComfyUI/Wan/Kokoro) is unverified in this environment — models and ComfyUI are not installed here. Only pipeline control flow, persistence, and API surface are verified.
- [GAP-05]: Cancellation takes effect at scene boundaries, not mid-clip; a single long clip render must finish before the cancel is observed.
- [GAP-06]: `httpx` is required to run the test suite but is not declared in `requirements.txt` (test-only dependency).

## 5. IMMUTABLE EXECUTION TIMELINE & BUG LOG

<!-- TIMELINE LOGS BEGIN BELOW THIS LINE -->

- **Timestamp:** 2026-08-08T12:00:00Z
- **Session ID:** init-00000000-0000
- **Author/Agent:** Lead Architect AI
- **Target Subsystem:** System Core
- **Intent:** Baseline context initialization under EVCP-v4.0 guidelines.
- **Bugs Discovered:** None.
- **Fixes Applied:** N/A.
- **Context Modifications:** Initialized repository structure and EVCP-v4.0 standards.

---

- **Timestamp:** 2026-08-08T13:30:00Z
- **Session ID:** 321380d6-a866-48e5-8d59-96b5ef626e42
- **Author/Agent:** Claude Opus 5 (Master Orchestrator)
- **Target Subsystem:** `app/backend/` (queue, versions, models, db, daemon, routes), `app/frontend/src/`
- **Intent:** Full-pipeline defect sweep — restore the backend to a working state and eliminate data-loss paths.
- **Bugs Discovered:**
  1. **Backend could not start at all.** `routes/updates.py` imported `VERSION` from `main`, which imports the routers — circular import, hard `ImportError` on boot.
  2. **Missing dependency.** `routes/voices.py` uses `UploadFile`, but `python-multipart` was absent from `requirements.txt`; FastAPI raised at import time.
  3. **DATA LOSS — version restore.** `restore_version` overwrote the live project script, narration and every scene prompt/seed in place with no backup. The user's current work was unrecoverable.
  4. **DATA LOSS — version numbering.** `version_num` was derived as `count() + 1`. After deleting any version the next number collided with an existing one, and `shutil.copy2` overwrote that version's archived `final.mp4`. Present in both `routes/versions.py` and the queue's auto-snapshot.
  5. **Orphaned version rows.** `Project` had no relationship to `ProjectVersion`, so deleting a project stranded its version rows with dangling `project_id`s.
  6. **Stuck jobs after a crash.** Items left in `running` by an unclean shutdown were never recovered; the worker only ever selects `queued`, so the job neither resumed nor reported failure.
  7. **Stuck job on missing project.** `_run_pipeline` returned early when the project was gone, leaving the queue item in `running` forever.
  8. **Cancellation did nothing.** `cancel()` set the status from another session, but the pipeline never re-read it — and SQLite snapshot isolation meant the pipeline's long-lived session could not have seen it anyway. The run continued and then overwrote the status with `done`.
  9. **WebSocket client leak.** Progress sockets were deregistered only on `WebSocketDisconnect`; any other transport error left a dead socket in `_ws_clients` that every later broadcast retried.
  10. **Opaque failure on empty script.** Projects are created with `script: ''`; the pipeline fed that to the LLM and TTS and failed minutes later with an unrelated error.
  11. **Frontend could not represent cancellation.** `Project.status` union lacked `cancelled`, and the WS handler treated only `done`/`error` as terminal — a cancelled job would have pinned the UI to "running" with the socket open.
- **Fixes Applied:**
  - `updates.py` now imports `VERSION` from `app.backend.version`; `main.py` reports `VERSION` instead of a hardcoded literal.
  - Declared and installed `python-multipart`.
  - `restore_version` takes an auto-backup `ProjectVersion` of the live state before overwriting, and returns `backup_version`. The backup deliberately stores `final_path=None` so deleting it can never unlink the project's live video.
  - Added `next_version_num()` on the model layer (`max(version_num) + 1`), used by both call sites; removed the services→routes import that the first cut introduced.
  - Added `Project.versions` relationship with `cascade="all, delete-orphan"`.
  - Added `recover_orphaned_items()`, called from `daemon.startup()` before the worker starts.
  - Early return now marks the queue item terminal with an explanatory error.
  - Added `_Cancelled`, `_is_cancelled()` (fresh session, to escape the pipeline's SQLite read snapshot) and `_abort_if_cancelled()` checks at each scene boundary, before merge, and immediately before the terminal `done` write; cancellation is handled as its own terminal state, not a failure.
  - WebSocket deregistration moved into `finally`.
  - Added a fail-fast guard for an empty script.
  - Error path now stamps `completed_at`.
  - Frontend: added `cancelled` to the project status union, treated it as terminal in `queueStore`, and typed `backup_version` on the restore response.
  - `db.py` honours `AIVS_DB_PATH` so tests never touch the real database.
- **Verification:** Backend boots (62 routes); all 20 GET endpoints return 200; project→version→delete→restore→delete-project lifecycle exercised over live HTTP; version collision, restore backup, cascade, crash recovery and cross-session cancellation each verified; `tsc --noEmit` clean; 11/11 integrity tests pass. User's existing project row left intact and all test data removed.
- **Context Modifications:** Added `app/backend/tests/test_data_integrity.py`, `app/backend/models/project_version.next_version_num`, `generation_queue.recover_orphaned_items`, `AIVS_DB_PATH` env override, and the `.orchestrator/` delegation harness.
