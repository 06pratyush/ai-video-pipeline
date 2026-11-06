# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | Yes — current release line |
| < 1.0 | No — pre-release, please upgrade |

There is one active line at a time. Fixes land on `main` and ship in the next patch release, which
the in-app update banner surfaces within about six hours of publication.

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Report it through
[GitHub's private vulnerability reporting](https://github.com/06pratyush/ai-video-pipeline/security/advisories/new),
which opens a private advisory visible only to the maintainers. If that form is unavailable to you,
send a direct message to [@06pratyush](https://github.com/06pratyush) on GitHub asking for a private
channel — do not put the details in the first message.

A useful report includes:

- the version and commit, your OS, and whether you are running an installer build or from source
- what an attacker can do, and what access they need in order to do it
- the steps to reproduce, ideally minimal
- any proof-of-concept you have, as an attachment rather than a third-party link

**What to expect:**

| Stage | Target |
|---|---|
| Acknowledgement | 48 hours |
| Initial assessment, with severity and a plan | 7 days |
| Fix released, or a dated plan if it is involved | 30 days for high severity |
| Public disclosure | After the fix ships, coordinated with you |

You will be credited in the advisory and the release notes unless you would rather not be. If 30
days pass with no fix and no plan from us, you are free to disclose publicly — a maintainer going
quiet is not a reason for you to stay silent indefinitely.

## Threat model

This matters more than usual here, because AI Video Studio is a **local desktop application, not a
network service**, and that changes which findings are real.

**What the application is**

The backend is a FastAPI daemon bound to `127.0.0.1:7860` with **no authentication**, driven by an
Electron frontend on the same machine. It starts and supervises local ComfyUI and Ollama processes,
runs FFmpeg, reads and writes an SQLite database and generated media under `app/`, and downloads
models from upstream hosts on first run.

**The trust boundary is the machine.** Anyone with a local user session or the ability to make
requests to `localhost:7860` is already trusted by design. "The API has no authentication" is a
documented property, tracked as `[GAP-03]` in [CONTEXT.md](CONTEXT.md), not a vulnerability.

### In scope

These are real, and worth reporting:

- **Anything reachable from off the machine.** A binding that is not `127.0.0.1`, a path that makes
  the daemon listen on `0.0.0.0`, or a route reachable through a proxy or container port mapping
- **Browser-driven access to the daemon.** The CORS policy is currently `allow_origins=["*"]`
  ([`main.py:35`](app/backend/main.py)), so a web page the user visits may be able to reach
  `localhost:7860`. Any concrete attack built on that is in scope and interesting to us
- **Command injection** via script text, project titles, filenames, Skill JSON, or voice reference
  uploads reaching an FFmpeg, ComfyUI or shell invocation
- **Path traversal** letting a request read or write outside `app/projects/` and the database — in
  particular through project ids, version restore, voice uploads or Skill import
- **Arbitrary code execution** from loading a crafted Skill JSON, an imported template, or a
  downloaded model
- **Privilege escalation during install** — the bootstrap writes to disk and fetches dependencies;
  a writable intermediate path or an unverified download that a local attacker can poison
- **Supply chain integrity** of what we fetch: a model or dependency pulled over plain HTTP, or
  without a checksum where one is available
- **Unexpected outbound traffic.** The project promises no telemetry. Any call to anything but the
  user's own localhost services and the deliberate GitHub Releases update check is a bug we want to
  know about, and we treat it as a security issue because the local-first guarantee is the product
- **Secret or content leakage** — generated media, scripts or database contents reachable by another
  local user, or written outside the user's own profile

### Out of scope

Not vulnerabilities in this project. Reporting these will get a polite pointer back to this section:

- **No authentication on the localhost daemon** — by design; see `[GAP-03]`
- **An attacker who already has your user account.** Local code execution as the same user is above
  the trust boundary; such an attacker does not need our API
- **Findings in upstream projects.** ComfyUI, Ollama, Wan2.1, FFmpeg, PyTorch, Electron. Report
  those upstream. If our *integration* makes an upstream issue exploitable in a way it otherwise
  would not be, that is in scope — say so explicitly
- **Dependency CVEs with no reachable path** in this application. A scanner's output is a starting
  point, not a report; show the path from an entry point to the vulnerable call
- **Missing hardening with no attack attached** — a missing security header on a localhost-only API,
  no rate limiting, verbose error messages locally
- **Content generated by the models.** What the pipeline produces is governed by the model licences,
  not this policy
- **Self-XSS**, or anything requiring the user to paste attacker-supplied code into a console
- **Automated scanner output pasted without analysis**, and anything requiring a physically
  compromised machine

## For contributors

The review checklist in [REVIEW_AND_MERGE.md](REVIEW_AND_MERGE.md) carries the security-relevant
items reviewers check on every pull request. The ones most often missed:

- Pass untrusted strings — script text, titles, filenames — to subprocesses as **argument lists,
  never through a shell**. No `shell=True` on a command built from user input
- Validate and normalise any path derived from a request before touching the filesystem, and confirm
  the resolved path is still inside the directory you intended
- Treat an uploaded Skill JSON, template or voice clip as hostile input: validate required fields,
  reject unknown types, and never `eval` or dynamically import from it
- Do not add a network call. If a feature seems to need one, raise an issue first — this is the one
  project rule with no exceptions
- Never commit a credential, token or absolute local path. If one reaches a commit, say so
  immediately rather than quietly force-pushing; it has to be rotated regardless of history rewrites

## Hardening your own install

- Keep the daemon on `127.0.0.1`. Do not put it behind a reverse proxy or expose the port from a
  container without adding authentication of your own
- Treat downloaded models as data from the internet, because they are. Prefer the catalogued sources
  in [`installer/catalog.json`](installer/catalog.json)
- Generated media and your project database live unencrypted under `app/`. On a shared machine, rely
  on full-disk or home-directory encryption
- Skills and templates are executable configuration in practice — they drive FFmpeg filter chains.
  Review one from a stranger before importing it, exactly as you would a shell script
