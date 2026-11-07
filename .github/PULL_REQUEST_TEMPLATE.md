<!--
  Thanks for contributing to AI Video Studio.

  Reviewers read this description before they read your diff, so filling it in
  honestly is the difference between a one-pass review and four rounds of
  questions. Please do not delete the sections — write "N/A" where one does not
  apply.

  Full guides:
    Contributing      -> CONTRIBUTING.md
    Review and merge  -> REVIEW_AND_MERGE.md
-->

## What problem does this solve?

<!-- One or two sentences. Link the issue if there is one: "Fixes #123" closes it on merge. -->

Fixes #

## What is the approach?

<!--
  What you changed and why this way rather than an obvious alternative. If you
  rejected a simpler approach, say so — it saves the reviewer suggesting it.
-->

## How did you test it?

<!--
  This section is load-bearing. CI cannot run a real render, because the models
  are large and local, so your manual verification is the only evidence that
  exists. Replace the examples with what you actually ran and saw. An honest
  "I could not test X because I have no AMD GPU" is useful; "should work" is not.
-->

- [ ] `cd app/frontend && npm run typecheck` — clean
- [ ] Backend boots: `python -m uvicorn app.backend.main:app`
- [ ] `python -m pytest app/backend/tests/` — passing
- [ ] One real 1-scene render with the default Skill
- [ ] (If the pipeline changed) a render with every quality toggle enabled

**What I ran and what happened:**

## Changelog line

<!--
  One line for users, not reviewers, under the right heading. The changelog is
  maintained outside the repository, so the merging maintainer copies this across
  — if you do not write one, nobody can.
-->

**Added / Changed / Fixed / Removed:**

## Type of change

- [ ] Bug fix (no behaviour change beyond the fix)
- [ ] New feature
- [ ] Documentation
- [ ] Refactor (no behaviour change)
- [ ] Tests
- [ ] Build, CI, or tooling
- [ ] Breaking change — API surface, database schema, or Skill JSON format

## Checklist

<!-- See REVIEW_AND_MERGE.md for the full reviewer checklist. -->

- [ ] **`CONTEXT.md` has a new timeline entry in section 5.** CI fails this pull request without
      one — see [the rule](../CONTRIBUTING.md#the-one-rule-that-fails-ci)
- [ ] Section 4 of `CONTEXT.md` updated, if this opens or closes a `[GAP-nn]`
- [ ] No cloud calls, telemetry, or new account/credential requirement
- [ ] No queue item can be left in `running` (`[RULE-05]`)
- [ ] Anything overwriting user content snapshots the prior state first (`[RULE-06]`)
- [ ] Routes stay thin; logic in `services/`; tool wrappers in `pipeline/`
- [ ] Schema changes are additive and idempotent in `db._run_migrations()`
- [ ] New endpoints added to `app/frontend/src/api/backend.ts` with TypeScript types
- [ ] No secrets, absolute local paths, generated artefacts, databases or media committed

## Anything else?

<!--
  Known limitations, follow-up work you are deliberately leaving out, screenshots
  or a clip for UI changes, or a specific question you want the reviewer to focus
  on. Mark the PR as a draft if you want feedback on the approach before it is
  finished.
-->
