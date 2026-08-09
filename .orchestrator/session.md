## Session 2026-08-08
Models available: gemma4:e4b, llama3:latest, gemma4:latest, kimi-k2.6:cloud, kimi-k2.5:cloud
Reader: `orch-reader` (gemma4:e4b, num_ctx 65536, temp 0.1) — resident, keep_alive 8h
Goal: Fix all defects in the AI Video Studio pipeline; guarantee no data loss.

### Units
| # | Task | Route | Model | Attempts | Status | Notes |
|---|------|-------|-------|----------|--------|-------|
| 1 | Map generation_queue session/state handling | DELEGATE | orch-reader | 1 | used | Accurate line map; its "stuck in running" verdict was half wrong — verified myself |
| 2 | Audit versions.py destructive paths | DELEGATE | orch-reader | 1 | used | Correctly flagged restore as irrecoverable overwrite |
| 3 | Audit projects.py delete cascade | DELEGATE | orch-reader | 1 | used | Correctly flagged orphan risk |
| 4 | Circular import fix | RETAIN | — | — | merged | 1-line, under delegation floor |
| 5 | Queue cancellation + crash recovery | RETAIN | — | — | merged | Concurrency + irreversible state — never delegated |
| 6 | Version numbering + restore backup | RETAIN | — | — | merged | Data integrity |
| 7 | Model cascade relationship | RETAIN | — | — | merged | Schema change |
| 8 | Integrity test suite | RETAIN | — | — | merged | Spec would have cost more than the code |
| 9 | Frontend cancelled-state handling | RETAIN | — | — | merged | Cross-file, caused by my own backend change |

### Failure patterns (fold into future packets)
- N/A — no code generation was delegated this session. Reader used for triage only.

### Harness notes (important for future sessions)
- `ollama run` CANNOT be used for reader calls: it scans prompt text for quoted
  file paths and tries to attach them as multimodal input, so any prompt
  containing source code dies with `Couldn't process file`. `ask.sh` therefore
  wraps `ask.py`, which uses the Ollama HTTP API. Do not "simplify" it back.
- Do not use `set -o pipefail` with `| head -n` around ollama: SIGPIPE makes
  every successful call exit non-zero.
- `venv/` is Python 3.14 and holds the real deps. `venv311/` does NOT have
  fastapi installed — use `venv/Scripts/python.exe`.

### Decisions
- Crash recovery *requeues* interrupted jobs rather than failing them: the
  pipeline catches its own exceptions, so a `running` item implies a hard kill,
  not a poisonous job. Scene-level caching means little work is repeated.
- The restore auto-backup stores `final_path=None` on purpose. `delete_version`
  unlinks `final_path`, so pointing the backup at the live video would let
  deleting that backup destroy the project's current render.
- Did NOT add filesystem deletion on project delete. Orphaned media is a storage
  leak (logged as GAP-01), not data loss; adding recursive deletion would
  introduce new irreversible behaviour that was never requested.

## Session 2026-08-09 — publish AI Video Studio to the website

Goal: merge the pipeline data-integrity work, publish this project on
thehallucinatedlab.space/solutions.html, and adopt the Continuous
Synchronization Mandate in both repositories.

### Reader status
`ollama list` and `warm.sh` both hung past 120s and returned empty.
The reader was never resident this session. Fell back to direct reading
throughout, per §11.1. Kept inside the 100-line ceiling by using Grep
and targeted `sed -n` ranges rather than whole-file reads — the only
files read in full were under 100 lines. No ceiling breach.

### Units
| # | Task | Route | Attempts | Status | Notes |
|---|------|-------|----------|--------|-------|
| 1 | Site CONTEXT.md manifest | RETAIN | 1 | merged (site #30) | Architecture + honest gap list; judgment work, not transcription |
| 2 | Context-sync CI gate (site) | RETAIN | 1 | merged (site #30) | CI/irreversible — never delegated (§15) |
| 3 | Solutions spotlight card | RETAIN | 1 | merged (site #31) | Product copy; delegation packet would exceed the output (§4 RETAIN-7) |
| 4 | JSON-LD + meta description | RETAIN | 1 | merged (site #31) | Structured-data honesty is a correctness claim |
| 5 | llms.txt / llms-full.txt | RETAIN | 1 | merged (site #32) | Written work — explicitly ours under §11.4 |
| 6 | Context-sync CI gate (pipeline) | RETAIN | 1 | merged (pipeline #1) | Same reasoning as unit 2 |

Nothing was delegated. With the reader down and every unit being either
judgment, prose, or CI configuration, delegation would have been theater
(§15) — the packets would have been longer than the artifacts.

### Failure patterns
- The supplied workflow spec used `runs-name:` as a job key. Invalid
  Actions syntax; GitHub rejects the whole file and shows a parse error
  on every PR. Corrected to `name:` in both repositories.
- The supplied spec checked only that CONTEXT.md appears in the diff.
  A one-character edit satisfies that. Added a minimum-added-lines check.

### Decisions
- Three sequential PRs per repository rather than parallel branches:
  every PR must touch CONTEXT.md section 5, which is append-only, so
  concurrent branches would have conflicted at the file tail by
  construction. Each branch was cut only after the previous merged.
- Declined to write `thl solutions install aivideostudio` on the new
  card. The subcommand does not exist in the Python package. The two
  pre-existing instances are logged as site GAP-06 rather than silently
  matched.
