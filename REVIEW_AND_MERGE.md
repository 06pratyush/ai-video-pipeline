# Review and merge policy

How a pull request in AI Video Studio goes from opened to merged: who reviews it, what blocks it,
how long it takes, and how it reaches a release.

This document is the contract in both directions. Contributors should know exactly what will be
asked of them before they open a pull request, and reviewers should be held to a standard too — a
review that arrives three weeks late, or that rejects a change without saying what would make it
acceptable, is a failure of this process rather than a fact of life.

If you are writing the pull request, start with [CONTRIBUTING.md](CONTRIBUTING.md). Come back here
once it is open.

**Contents**

- [The lifecycle at a glance](#the-lifecycle-at-a-glance)
- [Stage 1 — Automated checks](#stage-1--automated-checks)
- [Stage 2 — Human review](#stage-2--human-review)
- [Comment severities](#comment-severities)
- [The reviewer checklist](#the-reviewer-checklist)
- [Stage 3 — Approval](#stage-3--approval)
- [Stage 4 — Merge](#stage-4--merge)
- [Stage 5 — Release](#stage-5--release)
- [Service levels](#service-levels)
- [When a pull request is closed unmerged](#when-a-pull-request-is-closed-unmerged)
- [Disagreements](#disagreements)
- [For maintainers](#for-maintainers)

---

## The lifecycle at a glance

```
  contributor                     automation                      maintainer
  ───────────                     ──────────                      ──────────

  open PR  ──────────────────────▶ Context Sync gate
  (template filled)                CONTEXT.md +3 lines?
                                          │
                                   ┌──────┴──────┐
                                 fail          pass
                                   │             │
      ◀── red check, fix ──────────┘             ▼
                                           triage: label,
                                           assign reviewer
                                                 │
                                                 ▼
                                           REVIEW  ◀── first pass
                                                 │     within 5 working days
                                   ┌─────────────┼─────────────┐
                                   ▼             ▼             ▼
                              blocking      should-fix        nit
                               (must)      (default yes)   (optional)
                                   │             │             │
      ◀── push fixes ──────────────┴─────────────┘             │
          (do not force-push mid-review)                       │
                                   │                           │
                                   ▼                           │
                              re-review  ◀─────────────────────┘
                                   │
                                   ▼
                            1 maintainer approval
                              + all checks green
                                   │
                                   ▼
                            SQUASH AND MERGE  ──▶ main
                              (maintainer only)      │
                                                     ▼
                                            CHANGELOG [Unreleased]
                                                     │
                                                     ▼
                                              tagged release
                                            (installers built by
                                             release.yml workflow)
```

---

## Stage 1 — Automated checks

Automation runs before a human looks at the diff. Nothing is reviewed while CI is red, because the
first failure usually invalidates the rest of the reading.

| Check | Workflow | What it enforces |
|---|---|---|
| **Context Sync** | [`enforce-context-sync.yml`](.github/workflows/enforce-context-sync.yml) | `CONTEXT.md` is in the diff **and** gained at least 3 lines |
| **Release build** | [`release.yml`](.github/workflows/release.yml) | Runs on tags, not pull requests — installers build for Windows, Linux and macOS |

The Context Sync gate is the one that surprises people. It fails with
`PROTOCOL VIOLATION — CONTEXT.md was not updated`, and the fix is to append a timeline entry to
section 5 of `CONTEXT.md`; see
[the CONTRIBUTING section on it](CONTRIBUTING.md#the-one-rule-that-fails-ci) for the exact shape.
A pull request that changes no files at all passes the gate, by design.

**What CI cannot check.** There is no automated test of a real render, because the models are large
and local and no hosted runner has the GPU for it. Type checking, a clean backend boot and the
integrity tests are the contributor's responsibility to run locally, and the reviewer's to ask about:

```bash
cd app/frontend && npm run typecheck
python -m uvicorn app.backend.main:app
python -m pytest app/backend/tests/
```

Because of that gap, **the "how did you test this?" answer in the pull request template is load
bearing.** A reviewer is entitled to block on a missing or vague test plan, and "it should work" is
not a test plan.

---

## Stage 2 — Human review

### Triage

A maintainer triages within **2 working days** of CI going green: applies labels (`bug`,
`enhancement`, `documentation`), confirms scope against any linked issue, and either starts the
review or says when it will start. Triage is not review — it exists so nobody waits in silence
wondering whether their pull request was seen.

### What a reviewer actually does

Reviewers read in this order, and stop early if an earlier question fails:

1. **The description.** What problem, what approach, how tested. If the approach is wrong, nothing
   in the diff matters, and the discussion belongs at this level rather than line by line.
2. **The architecture.** Does this belong where it was put? See
   [architecture conventions](CONTRIBUTING.md#architecture-conventions) and the `[RULE-nn]` list in
   section 3 of [`CONTEXT.md`](CONTEXT.md). A change that violates a rule is either wrong or is
   proposing to change the rule — and the second is a conversation, not a line comment.
3. **The data paths.** Anything touching the queue, the database or user media gets read twice. The
   rules that exist because they were learned the hard way:
   `[RULE-05]` — every terminal queue state sets both a status and `completed_at`, and no path may
   leave an item in `running`; `[RULE-06]` — anything overwriting user content snapshots the prior
   state first.
4. **Failure behaviour.** Optional stages must degrade, never crash the pipeline. New external tools
   need the `is_available()` pattern and a clear message when the dependency is absent.
5. **The line-level detail.** Style, naming, types, dead code. Last, because it is the cheapest to
   fix and the least important.

### Review happens in public

Design discussion goes on the pull request or the issue, not in private messages — so that the
reasoning survives for whoever reads the thread in a year, and so that the decision is visible to
anyone else who might have written the same patch.

---

## Comment severities

Every review comment is prefixed so its weight is unambiguous. This is the single convention that
most reduces review friction: contributors stop guessing which comments are mandatory, and reviewers
stop having to soften suggestions into vagueness.

| Prefix | Meaning | Contributor's options |
|---|---|---|
| **blocking:** | Must change before merge | Fix it, or make the case why it is not a problem |
| **should-fix:** | A real improvement; default is to do it | Do it, or explain why not — either is accepted |
| **nit:** | Taste, or a micro-optimisation | Take it or leave it, no justification needed |
| **question:** | The reviewer does not understand yet | Answer it; often the answer belongs in a code comment |
| **praise:** | This was done well | Nothing — but say so when it is true |

A reviewer who writes **blocking:** states what would make the change acceptable. "This is wrong" is
not a review; "this leaves the queue item in `running` if the probe times out, which `[RULE-05]`
forbids — bound the probe and mark the item `error`" is.

Only these block a merge:

- any unresolved **blocking:** comment
- a **should-fix:** that the contributor has neither addressed nor answered
- a failing required check
- an unanswered **question:** on a data path

Nits never block. If a nit is important enough to block on, it was not a nit.

---

## The reviewer checklist

Reviewers work through this before approving. It is also the best pre-flight list for a contributor:
anything you can tick yourself is a round trip you have saved.

**Correctness**

- [ ] The change does what the description claims, and the description claims what the change does
- [ ] Error paths are handled, not swallowed — no bare `except: pass` on a path that can fail
      meaningfully
- [ ] No queue item can be left in `running` (`[RULE-05]`)
- [ ] Anything overwriting user content snapshots first (`[RULE-06]`)
- [ ] Optional pipeline stages degrade gracefully and never kill the render

**Local-first**

- [ ] No network calls to anything but the user's own localhost services
- [ ] No telemetry, analytics, crash reporting or licence check
- [ ] No new credential, API key or account requirement
- [ ] Any new dependency is installable offline after first setup

**Architecture**

- [ ] Routes stay thin; business logic is in `services/`; tool wrappers are in `pipeline/`
- [ ] No `services` → `routes` import (`[RULE-02]`)
- [ ] Pipeline work stays on the worker thread, never inside a request handler (`[RULE-03]`)
- [ ] `VERSION` is imported from `app/backend/version.py` only (`[RULE-04]`)
- [ ] Schema changes are additive and idempotent in `db._run_migrations()`

**Interfaces**

- [ ] New endpoints are added to `app/frontend/src/api/backend.ts` with TypeScript types
- [ ] Response shape changes are reflected on both sides in the same pull request
- [ ] Python signatures are type hinted; request and response bodies are Pydantic v2 models

**Hygiene**

- [ ] `CONTEXT.md` has a real timeline entry, and section 4 is updated if a gap opened or closed
- [ ] A user-facing changelog line is stated in the description, for the maintainer to transfer
- [ ] No secrets, absolute local paths, or machine-specific config
- [ ] No generated artefacts, `node_modules`, databases or media committed
- [ ] A test plan is stated, and it is plausible for what changed

---

## Stage 3 — Approval

**One maintainer approval** is required to merge. In two cases a second reviewer is requested:

- the change touches the generation queue, the database schema, or version restore — the paths where
  a mistake destroys someone's work
- the change is the author's own, and another maintainer is available (nobody approves their own
  pull request; see [For maintainers](#for-maintainers))

Approval means: *I have read this, I believe it works, and I accept responsibility for it being in
`main`.* It does not mean every nit was addressed.

Reviewers use GitHub's three verdicts literally:

| Verdict | Use it when |
|---|---|
| **Approve** | Mergeable now. Outstanding comments are nits |
| **Comment** | Observations, questions, or a partial pass with no verdict yet |
| **Request changes** | At least one **blocking:** comment stands |

After pushing fixes, re-request review explicitly — GitHub does not reliably notify on a new push
alone, and a pull request can sit for a week because both sides are waiting for the other.

**Do not force-push while a review is in progress.** It detaches existing comments from their lines
and makes the reviewer re-read the whole diff. Push follow-up commits instead; the squash merge
cleans the history at the end, so there is no reason to tidy it by hand mid-review.

---

## Stage 4 — Merge

**Maintainers merge. Contributors do not**, even with write access — the person who approves is the
one who presses the button, so that approval and merge are never separated.

### Required before merge

These are **enforced by branch protection on `main`**, not merely agreed: one approving review,
a passing `CONTEXT.md is in sync` check, resolved conversations, a branch up to date with `main`,
and linear history — so merge commits are refused and squash or rebase is the only way in. Stale
approvals are dismissed when new commits are pushed.

Repository administrators retain a bypass, because this project is small enough to have exactly one
maintainer much of the time and GitHub does not permit approving your own pull request. That bypass
is what the [maintainer section](#for-maintainers) governs: it is for `docs/`, `chore/` and `fix/`
work with the verification stated, and using it for anything else is the failure this document
exists to prevent.

1. One maintainer approval (two for queue, schema or restore changes)
2. All checks green, including Context Sync
3. No unresolved **blocking:** comments
4. Branch up to date with `main` — rebase or merge `main` in if it has moved and the diff is stale
5. A user-facing changelog line stated in the pull request description, which the merging maintainer
   transfers into `CHANGELOG.md` (maintained outside the repository)
6. `CONTEXT.md` timeline entry present

### Squash and merge, always

`main` keeps **one commit per pull request**. Squashing means the timeline log in `CONTEXT.md` and
the commit history in `main` agree with each other one-to-one, which is what makes `git log` on
`main` readable as a change narrative rather than a work diary.

The squash commit message is the pull request title and a cleaned body — not the default list of
"wip" subjects. The title becomes permanent history, so it is written in the same imperative,
sentence-case style as a commit subject:

```
Fix ComfyUI hang when VRAM is exhausted mid-render (#123)
```

Rebase merges are used only to preserve a deliberately curated multi-commit series, which is rare
here. Merge commits are not used, because they put the per-commit noise into `main` permanently.

### After merge

- The branch is deleted. Linked issues close automatically via `Fixes #nnn`
- `[Unreleased]` in `CHANGELOG.md` accumulates until a release is cut
- If the merge turns out to be wrong, it is **reverted, not patched forward** — `main` goes back to
  working first, and the fix comes as a fresh pull request. A revert is not a judgement on the
  contributor; it is how a small project keeps `main` installable

---

## Stage 5 — Release

Releases are cut by a maintainer when `[Unreleased]` has accumulated enough to be worth installing:

1. Move `[Unreleased]` entries under a new `## [x.y.z] — YYYY-MM-DD` heading in the maintainers'
   `CHANGELOG.md`, folding in the changelog lines from each merged pull request description
2. Bump `VERSION` in `app/backend/version.py` — the single source of truth (`[RULE-04]`) — and the
   frontend `package.json`
3. Tag and push: `git tag -a v1.2.0 -m "v1.2.0" && git push origin v1.2.0`
4. [`release.yml`](.github/workflows/release.yml) builds the Windows, Linux and macOS installers and
   attaches them to the GitHub release
5. Write release notes from the changelog, grouped by `Added` / `Changed` / `Fixed`, and credit
   contributors by handle

Versioning follows [Semantic Versioning](https://semver.org/): patch for fixes, minor for new
capability, major for a breaking change to the API surface, the database schema, or the Skill JSON
format. Note that the in-app update banner polls GitHub Releases every 6 hours, so a published
release reaches users without any further action.

---

## Service levels

What you can expect, and what to do when it does not happen. This is a volunteer project, so these
are honest targets rather than guarantees.

| Event | Target |
|---|---|
| Triage and labelling | 2 working days |
| First review pass | 5 working days |
| Re-review after you push fixes | 3 working days |
| Security report acknowledgement | 48 hours — see [SECURITY.md](SECURITY.md) |
| Decision on a `good first issue` pull request | 5 working days — new contributors go first |

**If a target is missed,** comment once on the thread tagging a maintainer. That is welcome, not a
nuisance; a silent pull request is almost always an oversight rather than a signal. A pull request
with no contributor response for 30 days is marked `stale` and closed after a further 14 — closed,
not rejected, and reopening it later is fine.

---

## When a pull request is closed unmerged

A maintainer closing a pull request without merging always says which of these it is, and what — if
anything — would change the answer:

| Reason | What it means |
|---|---|
| **Out of scope** | Real work, wrong project. Often a plugin or fork is the right home |
| **Conflicts with local-first** | Needs a cloud service, telemetry or an account. Not negotiable |
| **Superseded** | Fixed another way, or overtaken by a larger change. The reason links to the replacement |
| **Stale** | No response for 44 days. Reopen whenever you like |
| **Incomplete and inactive** | Approach was agreed but the work stopped. Reopen or hand it off |

"Out of scope" is not a verdict on quality. The most common version of it is a genuinely good feature
that would commit the maintainers to supporting a subsystem they cannot maintain — which is why
opening an issue first is worth the extra day.

---

## Disagreements

1. **Discuss on the thread.** Most disagreements are missing context on one side, and one concrete
   example usually settles it
2. **If it is about a rule in `CONTEXT.md` section 3,** the rule wins until the rule is changed —
   and changing it is its own pull request, which is a legitimate thing to propose
3. **If it is about taste,** the reviewer's call stands for code inside their area, and the
   contributor's for code inside theirs. Neither is worth a long thread
4. **If it stays stuck,** the repository owner ([@06pratyush](https://github.com/06pratyush))
   decides, and the reasoning is written on the thread

Nobody needs to win. The question is whether the change still makes sense to a stranger reading it
in six months.

---

## For maintainers

- **Never approve or merge your own pull request** when another maintainer is available. When none
  is — which is most of the time on this project — self-merge is permitted for `docs/`, `chore/` and
  `fix/` work, and the pull request description must say so explicitly along with how it was
  verified. `feat/` work and anything touching the queue, the schema or restore waits for a second
  pair of eyes
- **Review the diff, not the author.** A first-time contributor's patch gets the same reading as
  your own
- **Say what would make it acceptable.** Every rejection and every **blocking:** comment carries the
  path forward, or it is not finished
- **Credit contributors** in release notes by handle
- **Keep `CONTEXT.md` honest.** If verification was not done, the entry says so. A manifest the next
  reader cannot trust is worse than no manifest, which is the whole reason the gate exists

---

## Related

- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, code style, and how to raise a pull request
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — expected conduct and how to report a problem
- [SECURITY.md](SECURITY.md) — reporting a vulnerability privately
- [CONTEXT.md](CONTEXT.md) — the architectural rules and known gaps reviewers check against
