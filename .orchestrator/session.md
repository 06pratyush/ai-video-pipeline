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
