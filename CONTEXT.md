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

---

- **Timestamp:** 2026-08-09T02:00:00Z
- **Trigger Event:** Pull Request Merge
- **Author/Agent:** Claude Opus 5 (Master Orchestrator) for 06pratyush
- **Target Subsystem:** `.github/workflows/`
- **Intent:** Enforce the Continuous Synchronization Mandate in CI. `CONTEXT.md` already existed and was already being maintained by hand; this makes it impossible to skip.
- **Bugs Discovered:** None — no application code was touched. The generation pipeline, API surface and database layer are unchanged.
- **Fixes Applied:** N/A.
- **Verification:** No test run required or performed — the change adds a workflow file and this log entry, and touches no Python, TypeScript or configuration the application loads. The workflow validates itself on the pull request that introduces it, because `pull_request` events evaluate workflows from the merge result.
- **Context Modifications:** Added `.github/workflows/enforce-context-sync.yml`. It fails any pull request into `main` that does not add at least three lines to `CONTEXT.md`. Actions are referenced by tag (`@v4`) to match the existing `release.yml` in this repository; note that the companion gate on the `thehallucinatedlab` site repository pins by commit SHA instead, which is the stronger choice and worth adopting here when `release.yml` is next revised.
- **Cross-repository note:** The same session published this project as **AI Video Studio** on https://thehallucinatedlab.space/solutions.html — a spotlight card, a `SoftwareApplication` JSON-LD node, and long-form coverage in `llms.txt` and `llms-full.txt` — across three pull requests in `The-Hallucinated-Lab/thehallucinatedlab` (#30, #31, #32). The site now states publicly that this application requires an NVIDIA GPU with CUDA plus a local ComfyUI and Wan 2.1 install, which matches [GAP-04] here: end-to-end render remains unverified in the development environment.

---

- **Timestamp:** 2026-08-09T02:30:00Z
- **Trigger Event:** Pull Request Merge
- **Author/Agent:** Claude Opus 5 (Master Orchestrator) for 06pratyush
- **Target Subsystem:** `.orchestrator/session.md`
- **Intent:** Record the session ledger for the publish-to-website work, so the routing decisions and the reader outage survive context compaction.
- **Bugs Discovered:** Two defects in the supplied CI specification, both fixed before either gate shipped. (1) `runs-name:` was used as a job key — not valid GitHub Actions syntax; GitHub rejects the entire workflow file and surfaces a parse error on every pull request. Corrected to `name:`. (2) The specified check only asserted that `CONTEXT.md` appears in the diff, which a one-character edit satisfies; a minimum-added-lines assertion was added so the gate cannot be cleared by touching the file.
- **Fixes Applied:** Both corrections are in `.github/workflows/enforce-context-sync.yml` here and in the companion workflow on the site repository.
- **Verification:** Ledger only — no application code touched. The local Ollama reader was unavailable for the whole session (`ollama list` and `warm.sh` both hung past 120s and returned empty), so all file inspection was done directly, kept within the protocol's 100-line ceiling using targeted grep and line-range reads. No unit was delegated: with the reader down and every unit being judgment, prose, or CI configuration, the delegation packets would have been longer than the artifacts.
- **Context Modifications:** Appended a session block to `.orchestrator/session.md`. No change to application code, dependencies, or the database schema.

- **Timestamp:** 2026-11-06T00:00:00Z
- **Trigger Event:** Pull Request
- **Author/Agent:** Claude Opus 5 (Master Orchestrator) for 06pratyush
- **Target Subsystem:** `README.md`, `llms.txt`, `CONTRIBUTING.md`, `REVIEW_AND_MERGE.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `.github/` (templates, CODEOWNERS), plus GitHub-side repository metadata.
- **Intent:** Make the repository discoverable (GitHub internal search, Google, LLM retrieval) and make the contribution path explicit end to end — how to contribute, how a pull request is raised, reviewed, approved and merged, and how a release is cut. Until now the only indexable artifacts were `README.md`, `LICENSE` and this file, the repository carried no topics at all, and the contribution guide lived in gitignored `docs/`, so GitHub never surfaced it and no contributor could read it.
- **Bugs Discovered:**
  1. **The repository had zero topics.** `repositoryTopics` was `null`, which makes the project unreachable by every `topic:` query in GitHub's own search — the primary discovery path on the platform.
  2. **The entire documentation set was unpublished.** `.gitignore:40-44` excludes `docs/`, `CHANGELOG.md` and `AI_VIDEO_STUDIO_ROADMAP.md` as "development-only documentation". GitHub therefore served none of the ~81 KB of Architecture, Building, Skills, Troubleshooting and Contributing documentation, and showed no "Contributing guidelines" link because `docs/CONTRIBUTING.md` — a location GitHub does recognise — had never been committed. The owner elected to keep `docs/` private, so the fix was to publish a self-contained contribution and governance set at the repository root instead, and to keep every link inside the published set.
  3. **`CHANGELOG.md` is gitignored, yet the contribution guide instructed contributors to edit it.** A forked clone does not contain the file, so the instruction was impossible to follow. Contributors are now asked to state a changelog line in the pull request description, which the merging maintainer transfers.
  4. **The `CONTEXT.md` sync gate was undocumented.** `.github/workflows/enforce-context-sync.yml` hard-fails any pull request that does not add at least three lines to this file, but no contributor-facing document mentioned it. A first contribution would have failed CI with `PROTOCOL VIOLATION` against a rule the contributor was never given. It is now the second section of `CONTRIBUTING.md`, with a copy-paste entry template, and is restated in the pull request template and the review policy.
  5. **A misnested `validations:` key** in `.github/ISSUE_TEMPLATE/question.yml` (indented under `attributes:` rather than beside it) silently made every field optional. Caught by schema validation before commit and corrected.
- **Fixes Applied:**
  - **Repository metadata, applied live via `gh` and not carried by this pull request:** description rewritten keyword-first ("Local AI video generator: text-to-video on your own GPU with Wan2.1, Kokoro TTS and Whisper — offline, open source, no API keys."); 20 topics added, GitHub's maximum (`ai-video-generator`, `text-to-video`, `video-generation`, `generative-ai`, `self-hosted`, `local-first`, `offline-ai`, `comfyui`, `wan2-1`, `ollama`, `kokoro-tts`, `text-to-speech`, `whisper`, `musicgen`, `ffmpeg`, `electron`, `fastapi`, `react`, `python`, `cuda`); homepage set to `https://thehallucinatedlab.space/solutions.html`, which reciprocates the link the site already carries; seven triage labels created (`stale`, `security`, `blocked`, `needs-info`, `area: pipeline`, `area: frontend`, `area: installer`), each referenced by the new documents or templates.
  - **`README.md`:** added a `## What is AI Video Studio?` prose section above the visual layer, because the first ninety lines were badges, a centered `<div>` and table cells with almost no indexable text; rewrote the H1 subtitle to carry the primary keyword; added a nine-question `## FAQ` whose headings match question-shaped queries; rewrote `## Contributing` to point at the new documents with an "easiest first" table; added `FAQ` and `Contributing` to the top navigation. Every link added points inside the published set — no link resolves into gitignored `docs/`.
  - **`llms.txt`** (new, repository root): a self-sufficient retrieval artifact following the llmstxt.org convention. Because `docs/` stays private, it carries the facts outright — licence, hardware floor, render times, platforms, all eight pipeline stages, the seven Skills, and the three-tier architecture — rather than acting as a link index into pages that do not exist publicly.
  - **`CONTRIBUTING.md`** (moved from gitignored `docs/` to the root, where it is both published and recognised by GitHub): the technical body is preserved verbatim; new material adds a contents list, a "Ways to contribute" table ordered by required skill, the `CONTEXT.md` gate with a copy-paste template, branch-prefix conventions, a pre-push verification block, commit-message guidance with a worked example, and a "keep it reviewable" section on splitting large changes.
  - **`REVIEW_AND_MERGE.md`** (new): the full lifecycle — automated checks, triage, what a reviewer reads and in what order, a `blocking:` / `should-fix:` / `nit:` / `question:` / `praise:` comment-severity convention with an explicit statement of which of those block a merge, a reviewer checklist grouped as correctness / local-first / architecture / interfaces / hygiene and keyed to the `[RULE-nn]` list in section 3 of this file, the one-approval rule with a two-reviewer requirement on queue, schema and restore changes, squash-merge-only with the reasoning (one commit in `main` per timeline entry here), revert-not-patch-forward, the release and tagging procedure, response-time targets, the reasons a pull request is closed unmerged, an escalation path for disagreements, and a maintainer section permitting self-merge only for `docs/`, `chore/` and `fix/` work with the verification stated.
  - **`CODE_OF_CONDUCT.md`** (new): written for this project rather than a reproduction of the Contributor Covenant, which it cites. Reporting routes to GitHub direct message and to GitHub's own independent abuse reporting where the report concerns the owner, so no personal email address is published.
  - **`SECURITY.md`** (new): private-advisory reporting with response targets, and a threat model stating that the trust boundary is the machine — so the absent daemon authentication recorded as [GAP-03] is documented behaviour and explicitly out of scope, while the `allow_origins=["*"]` CORS policy at `main.py:35`, any non-loopback binding, command injection through script text or filenames, path traversal via project ids or version restore, and any unexpected outbound request are all in scope. Carries a contributor section and install-hardening notes.
  - **`.github/`:** `PULL_REQUEST_TEMPLATE.md` (problem, approach, test plan, changelog line, type, and a checklist led by the `CONTEXT.md` requirement and the `[RULE-05]` / `[RULE-06]` data-integrity rules); `ISSUE_TEMPLATE/bug_report.yml` (12 blocks, 9 required — GPU, VRAM, OS, version, install method and failing pipeline stage are mandatory, because [GAP-04] means a report without them cannot be triaged); `ISSUE_TEMPLATE/feature_request.yml` (8 blocks, 6 required, with a mandatory acknowledgement that the proposal needs no cloud service); `ISSUE_TEMPLATE/question.yml`; `ISSUE_TEMPLATE/config.yml` with `blank_issues_enabled: false` and contact links that divert vulnerability reports away from the public tracker; and `CODEOWNERS` auto-requesting review, with the data-integrity paths called out to match the two-reviewer rule.
- **Verification:** No application code, dependency, or database schema was touched — this change is documentation, GitHub templates and repository metadata only, so no test run was required and none was performed; the backend was not restarted and no render was attempted. What was verified: all four `.github/ISSUE_TEMPLATE/*.yml` files and both existing workflow files parse as YAML (`yaml.safe_load`), and the required-field counts were asserted per form (bug 9, feature 6, question 1) which is how the misnested `validations:` key in `question.yml` was caught and fixed; a link audit resolved all 70 relative links across the six published markdown documents, checking both that each target exists on disk and that it is not gitignored, and validating in-page anchors against the target file's actual headings using github-slugger's rule that each whitespace character becomes its own hyphen; `gh repo view` confirmed the description, homepage and all 20 topics are live; `gh label list` confirmed all 16 labels. The repository metadata and label changes took effect immediately and are therefore already in force regardless of this pull request's outcome.
- **Context Modifications:** Added `llms.txt`, `CONTRIBUTING.md` (moved from untracked `docs/CONTRIBUTING.md`), `REVIEW_AND_MERGE.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/CODEOWNERS`, and `.github/ISSUE_TEMPLATE/{bug_report,feature_request,question,config}.yml`; modified `README.md`. No change to `.gitignore` — `docs/`, `CHANGELOG.md` and the roadmap remain unpublished by the owner's decision, which is why the governance set lives at the root and `llms.txt` states facts rather than linking to them. Three improvements remain outstanding and are not addressed here, each requiring a repository setting or an upload rather than a commit: no custom social preview image is set (`usesCustomOpenGraphImage: false`, so link previews on every social and chat surface fall back to a generated avatar card; a 1280×640 PNG must be uploaded through the repository settings UI, which has no API); `main` has no branch protection (`GET /branches/main/protection` returns 404, so the one-approval and green-CI requirements this pull request documents are conventions a maintainer can bypass rather than enforced rules); and Discussions is disabled (`hasDiscussionsEnabled: false`), which enabling would add indexable long-tail question-and-answer pages. One defect found while checking the last of those was fixed here rather than deferred: the README footer's "Discuss" link pointed at `/discussions` on a repository where Discussions is off, verified returning HTTP 404, and now points at the new question issue form.

---

- **Timestamp:** 2026-11-07T00:00:00Z
- **Trigger Event:** Repository settings change, on the same pull request
- **Author/Agent:** Claude Opus 5 (Master Orchestrator) for 06pratyush
- **Target Subsystem:** GitHub repository settings (branch protection, Discussions), plus `README.md`, `REVIEW_AND_MERGE.md` and `.github/ISSUE_TEMPLATE/{config,question}.yml`.
- **Intent:** Close two of the three items the preceding entry left outstanding, at the owner's instruction, and bring the documents into line with the settings now in force. **This entry supersedes the closing statements of the preceding entry**, which recorded that `main` had no branch protection and that Discussions was disabled; the timeline is append-only, so the correction is recorded here rather than by editing that entry. Of the three items, only the social preview image remains, because it has no API.
- **Bugs Discovered:**
  1. **A policy that would have bricked the repository, caught before it was applied.** This project is maintained by one person much of the time, and GitHub does not permit approving your own pull request. Requiring one approving review with `enforce_admins: true` would therefore have made every solo pull request permanently unmergeable, beginning with the one carrying this entry. Applied with `enforce_admins: false` instead, so the requirements bind outside contributors while the owner retains a bypass — which is precisely the arrangement `REVIEW_AND_MERGE.md` already described, permitting self-merge for `docs/`, `chore/` and `fix/` work with the verification stated.
  2. **Two documents made stale by the settings change itself.** The README footer link and the issue-template configuration had been written for a repository where Discussions was off: the preceding entry records replacing a verified 404 `/discussions` link with the new question form. With Discussions now enabled, that routing was inverted again, and open-ended questions are directed to Discussions — which is both the better venue and the one that produces indexable long-tail pages, the reason for enabling it.
- **Fixes Applied:**
  - **Discussions enabled** (`has_discussions: true`), confirmed by read-back.
  - **Branch protection applied to `main`**, confirmed field by field by reading the protection back: required status check `CONTEXT.md is in sync` (the exact context string was taken from the live check run on the pull request rather than guessed, because a wrong context leaves every future pull request waiting forever on a check that never reports); `strict: true`, so a branch must be up to date with `main` before merging, matching the existing requirement in `REVIEW_AND_MERGE.md`; one approving review required, with stale approvals dismissed on a new push; `required_conversation_resolution: true`, which gives the `blocking:` comment convention structural force; `required_linear_history: true`, which refuses merge commits and so enforces the squash-merge rule rather than leaving it a convention; force pushes and branch deletion both refused; `require_code_owner_reviews: false`, left off deliberately because the owner is the sole code owner and enabling it would reintroduce the self-approval deadlock — the comment in `.github/CODEOWNERS` already describes this as a setting not yet enabled and remains accurate.
  - **`REVIEW_AND_MERGE.md`:** the "Required before merge" section now states that these requirements are enforced by branch protection rather than agreed, lists what is enforced, and documents the administrator bypass together with the narrow circumstances in which using it is legitimate.
  - **`README.md`:** the footer "Ask a question" link now points at Discussions, which exists.
  - **`.github/ISSUE_TEMPLATE/config.yml`:** Discussions added as the first contact link, so open-ended questions, hardware advice and half-formed ideas are routed there and the issue tracker keeps to things that are broken or specifically proposed. **`question.yml`:** its preamble now names Discussions as the better venue for an open-ended question, so the two surfaces do not compete.
- **Verification:** No application code, dependency or database schema was touched; no test run was required and none was performed. Settings verified by read-back rather than by assuming the write succeeded: `GET /branches/main/protection` returned every field as intended, and `gh repo view` confirmed `hasDiscussionsEnabled: true` alongside the 20 topics and the homepage from the preceding entry. The effect on the open pull request was then checked rather than predicted — `gh pr view` reports `mergeable: MERGEABLE` with `mergeStateStatus: BLOCKED` and `reviewDecision: REVIEW_REQUIRED`, which is the intended behaviour and confirms the protection is live and binding; the `CONTEXT.md is in sync` check had already passed on that pull request in 6 seconds, which is where the required context string was read from. Not verified: how the revised issue-template configuration and the Discussions landing page render in GitHub's interface, both observable only after merge.
- **Context Modifications:** No new files. Modified `README.md`, `REVIEW_AND_MERGE.md`, `.github/ISSUE_TEMPLATE/config.yml` and `.github/ISSUE_TEMPLATE/question.yml`. One item remains outstanding from the preceding entry and is unchanged: no custom social preview image is set (`usesCustomOpenGraphImage: false`), so link previews on every social and chat surface still fall back to a generated avatar card. It requires a 1280x640 PNG uploaded through Settings → General → Social preview, for which GitHub exposes no API, so it cannot be done from a commit or from the CLI. Also unchanged, and still recommended: `docs/`, `CHANGELOG.md` and the roadmap remain gitignored by the owner's decision, which is why the published governance set lives at the repository root and `llms.txt` states facts rather than linking to pages that are not served.

---

- **Timestamp:** 2026-11-07T08:30:00Z
- **Trigger Event:** Pull Request
- **Author/Agent:** Claude Opus 5 (Master Orchestrator) for 06pratyush
- **Target Subsystem:** `.github/social-preview.png`, `.github/social-preview.py`
- **Intent:** Produce the social preview card, the last outstanding item from the two preceding entries. GitHub exposes no API for setting it, so this commit supplies the artwork and the script that generated it; the upload itself remains a manual step through Settings → General → Social preview. Committing the generator alongside the image means the card can be re-rendered when the version, branding or model lineup changes, instead of becoming an orphaned binary nobody can reproduce.
- **Bugs Discovered:** Three defects in the first render, all found by inspecting the output rather than by assuming the code was right.
  1. **A hard vertical seam down the canvas.** `Image.radial_gradient` runs 0 at the centre to 255 at the edge, and the linear inversion used for the alpha mask left a small but non-zero alpha along the border of the paste box. Against a near-black background that reads as a crisp rectangular edge. Fixed by raising the falloff to a power (`t ** 2.2`), which drives alpha to exactly zero at the boundary. Confirmed by measuring column-mean brightness across the full width on content-free rows: the largest column-to-column jump is now 1.00, where a visible seam is several units.
  2. **The title collided with the video motif.** At 116px, "AI Video Studio" reached x=935 while the frame stack began at x=824, so the frame border passed behind the final letters. Fixed by reducing the title to 100px and moving the motif right, giving a 119px gap. The script now prints the title's right edge, the motif's left edge and the resulting gap on every render, so a future edit that reintroduces the collision fails visibly instead of silently.
  3. **A hyphen where an em dash belonged**, in "colour-graded MP4 - entirely on your own GPU".
- **Fixes Applied:** All three corrected and the result re-inspected. The card is 1280x640, which is GitHub's specification and also X/Twitter's `summary_large_image` ratio, so it crops minimally on the surfaces that matter. Design decisions worth recording: the title is set at 100px because these cards are frequently rendered small in Slack and Discord sidebars, where anything under roughly 90px stops being legible — legibility at thumbnail scale was prioritised over a more balanced composition; the play glyph and video frames are drawn as polygons and rounded rectangles rather than typographic characters, so there is no font fallback to produce tofu boxes on another machine; and the palette is taken from the repository's own badges (`#0a0a0b` background, `#6366f1` indigo accent, `#22c55e` for the MIT rule) so the card matches the README rather than inventing a second identity. Fonts degrade through a declared chain (Segoe UI, then Arial, then Calibri), so the script still renders on a machine without Segoe UI, though metrics will shift.
- **Verification:** No application code, dependency or database schema was touched; no test run was required and none was performed. The rendered PNG was inspected visually, not merely generated — which is how all three defects above were found. Output asserted at exactly 1280x640 before commit. The seam fix was verified numerically as described rather than by eye alone, since a one-unit brightness step is below what is reliably visible in a screenshot but would still band on a calibrated display. Not verified, and not verifiable from here: how the card is cropped and scaled by X, LinkedIn, Slack and Discord, each of which applies its own treatment; and the upload itself, which GitHub permits only through the settings interface, so `usesCustomOpenGraphImage` will remain `false` until 06pratyush performs it.
- **Context Modifications:** Added `.github/social-preview.png` (101 KB) and `.github/social-preview.py`, which regenerates it. Requires Pillow, which is **not** a project dependency and is deliberately not added to `requirements.txt` — the script is a one-off authoring tool, not part of the application or its test path, and nothing the application loads imports it. With the upload done, every item raised in the two preceding entries is closed except the owner's standing decision to keep `docs/`, `CHANGELOG.md` and the roadmap unpublished, which remains the largest discoverability gain still available and is recorded here as an open recommendation rather than a defect.

---

- **Timestamp:** 2026-11-10T00:00:00Z
- **Trigger Event:** Pull Request
- **Author/Agent:** Claude Opus 5 (Master Orchestrator) for 06pratyush
- **Target Subsystem:** `site/`, `.github/workflows/pages.yml`, `llms.txt`, `README.md`, and the repository homepage field.
- **Intent:** Give this project its own GitHub Pages site explaining how the pipeline works, and remove the dependency on the external `thehallucinatedlab.space` listing. 06pratyush reported "the GitHub Pages website is not working" and then asked for a standalone site instead.
- **Bugs Discovered:**
  1. **There was no Pages site to be broken.** `GET /repos/06pratyush/ai-video-pipeline/pages` returned 404 — Pages had never been configured on this repository. The appearance of one came from the homepage field pointing at the external site, which the preceding entries record as the project's public listing. So the report was accurate about the symptom and the cause was absence, not failure.
  2. **The obvious Pages source was unavailable.** GitHub's classic options are the branch root or a `/docs` folder, and `docs/` is gitignored here by the owner's standing decision. Using it would have silently reversed that decision. Deploying from `site/` through Actions avoids the conflict entirely and leaves `.gitignore` untouched.
  3. **Two SEO defects in the page's own head, caught by measuring rather than eyeballing.** The meta description was 268 characters against Google's truncation point of roughly 155, and the `<title>` was 67 against roughly 60. Both were rewritten to 158 and 57 and the lengths asserted.
  4. **An overwritten file, caught and restored.** `.claude/launch.json` was overwritten with a preview-server entry rather than appended to, discarding the existing `frontend` configuration. Restored from `HEAD` and the new entry added alongside it; the file is reverted entirely in this pull request, since a launch configuration pointing at a scratchpad path is of no use to anyone else.
- **Fixes Applied:**
  - **`site/index.html`**, a single page covering what the software is, all eight pipeline stages with the tool and typical cost of each and which are optional, what makes the pipeline survivable (VRAM routing, the persistent queue, the scene cache, soft failure), the three-tier architecture with the transport between tiers, the seven Skills with a sample Skill file, hardware requirements, both install routes, an eight-question FAQ, and contribution links. It carries a canonical URL, Open Graph and Twitter card tags, and JSON-LD for both `SoftwareApplication` and `FAQPage` — the latter being the one most likely to earn a rich result, since the FAQ answers are question-shaped.
  - **`site/style.css`**, dark, responsive, no webfont and no CDN, with the palette taken from the repository's own badges so the site, the README and the social card read as one thing. `prefers-reduced-motion` is honoured.
  - **`site/robots.txt`** and **`site/sitemap.xml`**.
  - **`.github/workflows/pages.yml`**, deploying from `site/` on pushes that touch it. The build step copies `llms.txt` to the site root — which is where the llmstxt.org convention expects it, and better than the repository-only copy it had before — and `.github/social-preview.png` to `og.png`, so each file keeps exactly one source of truth rather than being duplicated in git. The step then asserts all six published files are present and non-empty, so a broken card or a footer link to a missing file fails the deploy instead of publishing.
  - **`llms.txt`:** the `Project page` line now names the new site instead of the external one, and the site is listed first under Documentation. **`README.md`:** a `Website` link added to the top navigation, which also gives the repository an internal link to the site.
  - **Repository homepage** repointed from `https://thehallucinatedlab.space/solutions.html` to the Pages URL, and Pages enabled with `build_type: workflow`.
  - **Not changed, deliberately:** the references to `thehallucinatedlab.space` in section 5 of this file and in `.orchestrator/session.md`. Those are historical timeline records of what a past session did, and section 5 is append-only. Rewriting them to match the present is precisely what this file exists to prevent.
- **Verification:** No application code, dependency or database schema was touched; no test run was required and none was performed. The site was assembled locally exactly as the workflow assembles it and served over HTTP, then audited in a browser rather than assumed: no horizontal page overflow at desktop or at phone width (the only elements extending past the viewport are table cells inside a wrapper with `overflow-x: auto`, confirmed by walking each offender's ancestors for a scroll container — zero elements truly escape); every in-page anchor resolves to an element that exists; no empty, `#` or placeholder links; no zero-sized sections; the JSON-LD parses and yields `SoftwareApplication` and `FAQPage`; and the counts match the content (8 pipeline stages, 3 tiers, 7 Skills, 8 FAQ entries, exactly one `h1`). Title and meta-description lengths asserted after the fix. Screenshots were unreliable for part of this — the browser pane stopped painting and returned blank frames — so layout was verified by measuring the rendered DOM instead, which is the stronger check in any case. Not verified until after merge: the live deployment, the Actions run itself, and how the Open Graph card renders on each social platform.
- **Context Modifications:** Added `site/index.html`, `site/style.css`, `site/robots.txt`, `site/sitemap.xml` and `.github/workflows/pages.yml`. Modified `llms.txt` and `README.md`. `.gitignore` is unchanged — `docs/`, `CHANGELOG.md` and the roadmap remain unpublished, which is why the site states its content directly rather than linking into `docs/`. The site has no build step, no dependencies and no package manifest: it is two files plus two copied at deploy time, so it cannot rot through a dependency.

---

- **Timestamp:** 2026-11-10T12:00:00Z
- **Trigger Event:** Pull Request
- **Author/Agent:** Claude Opus 5 (Master Orchestrator) for 06pratyush
- **Target Subsystem:** `site/index.html`
- **Intent:** Repair a text-extraction defect in the site's `h1`, found while verifying the live deployment from the preceding entry.
- **Bugs Discovered:** The `h1` split its two lines with a bare `<br>` and no surrounding whitespace, so while `innerText` correctly returned `"...finished video\non your own machine."` — which is what a browser renders and what Google, which renders pages, sees — `textContent` returned `"...finished videoon your own machine."`. Any extractor that reads `textContent`, or that strips tags without substituting whitespace for `<br>`, therefore read the page's single most important heading as containing the non-word "videoon". That class of extractor includes a good deal of simple tooling and some AI retrieval crawlers, which makes it worth fixing on a page whose stated purpose includes LLM retrieval.
- **Fixes Applied:** A single space before the `<br>`, with a comment recording why it is deliberate so a later tidy-up does not remove it. CSS `white-space: normal` collapses trailing whitespace before a line break, so there is no visual change whatsoever.
- **Verification:** No application code, dependency or database schema was touched; no test run was required and none was performed. The fix was proved by extracting the `h1`'s text nodes from the source and asserting both directions — the literal string `videoon` is absent, and `video on your own machine` is present. Note that the first attempt at that check was itself wrong and was corrected before being trusted: the parser tracked element depth with a counter incremented on every start tag, but `<br>` is a void element that never emits an end tag, so the depth never returned to zero and the checker silently captured the entire remainder of the document rather than the heading. The visual result is unchanged by inspection of the rule rather than by screenshot, since collapsing whitespace before a line break is specified behaviour rather than something to confirm empirically.
- **Context Modifications:** None beyond the one-line edit. No new files, dependencies or schema changes.

---
