"""Install the ComfyUI custom nodes listed in installer/catalog.json, at the pinned commits.

    venv311\\Scripts\\python.exe scripts\\setup_nodes.py                  # every node the catalog needs
    venv311\\Scripts\\python.exe scripts\\setup_nodes.py ComfyUI-GGUF     # one node, by directory name
    venv311\\Scripts\\python.exe scripts\\setup_nodes.py --list

Safety: only https clones from github.com are allowed; a node is only ever written inside
app/runtime/comfyui/custom_nodes/; the clone is checked out at the exact commit the catalog
pins, so an install can never pick up node code that nobody reviewed -- an unpinned clone
would mean a silent third-party code update on every machine, every install. The commit must
be a full 40-character sha and the dir and requirements names must be plain file names, so a
catalog value can never reach git or pip as an option or as a path. Node requirements go into
ComfyUI's own venv, never the backend's. A node already present at its pinned commit reports
ok and is left alone.

A node's requirements file is "requirements.txt" unless the catalog entry names another with
a "requirements" key: ComfyUI-Frame-Interpolation ships requirements-no-cupy.txt and
requirements-with-cupy.txt and no plain requirements.txt, so without that key its kornia,
einops, scipy and opencv dependencies would be silently skipped and the node would fail to
import. cupy is left out on purpose -- it needs a matching CUDA toolkit to build, and the
node's own install.py treats it as the optional path.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "installer" / "catalog.json"
COMFY = ROOT / "app" / "runtime" / "comfyui"
NODES_DIR = COMFY / "custom_nodes"
ALLOWED_HOSTS = {"github.com"}
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
PLAIN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def catalog_nodes(catalog: dict | None = None) -> list[dict]:
    """Every distinct custom node the catalog's models require, in catalog order.

    Each entry is {"repo", "commit", "dir", "models": [catalog ids that need it]}.
    """
    if catalog is None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    nodes: dict[str, dict] = {}
    for m in catalog["models"]:
        for n in m.get("requires_custom_nodes", []):
            got = nodes.setdefault(n["dir"], {**n, "models": []})
            got["models"].append(m["id"])
    return list(nodes.values())


def safe_dest(n: dict) -> Path:
    if not PLAIN_NAME_RE.match(n.get("dir") or ""):
        raise ValueError(f"node dir is not a plain directory name: {n.get('dir')!r}")
    dest = (NODES_DIR / n["dir"]).resolve()
    if dest.parent != NODES_DIR.resolve():
        raise ValueError(f"node dir escapes custom_nodes/: {n['dir']}")
    return dest


def safe_requirements(n: dict, dest: Path) -> Path:
    name = n.get("requirements", "requirements.txt")
    if not PLAIN_NAME_RE.match(name or ""):
        raise ValueError(f"requirements is not a plain file name: {name!r}")
    return dest / name


def check_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"refusing to clone {url}: only https from {sorted(ALLOWED_HOSTS)}")


def check_commit(commit: str) -> None:
    if not COMMIT_RE.match(commit or ""):
        raise ValueError(f"not a full 40-character commit sha: {commit!r}")


def comfy_python() -> Path | None:
    for p in (COMFY / "venv" / "Scripts" / "python.exe", COMFY / "venv" / "bin" / "python"):
        if p.exists():
            return p
    return None


def git(*args: str, cwd: Path | None = None) -> bool:
    r = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    git {' '.join(args[:2])}: {(r.stderr or r.stdout).strip()[-200:]}", flush=True)
    return r.returncode == 0


def installed_commit(dest: Path) -> str:
    r = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def install_requirements(n: dict, dest: Path) -> bool:
    req = safe_requirements(n, dest)
    if not req.exists():
        print(f"    {dest.name}: no {req.name}, nothing to install")
        return True
    python = comfy_python()
    if python is None:
        print(f"  BAD  {dest.name}: no ComfyUI venv at {COMFY / 'venv'} "
              f"-- run installer/bootstrap.py first")
        return False
    print(f"  pip  {dest.name} {req.name} -> {python.parent.parent}", flush=True)
    r = subprocess.run([str(python), "-m", "pip", "install", "--quiet", "-r", str(req)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  BAD  {dest.name} {req.name}: {(r.stderr or r.stdout).strip()[-300:]}")
        return False
    return True


def install(n: dict) -> bool:
    """Put the node at its pinned commit. True when it is there and its requirements are in."""
    repo, commit, dest = n["repo"], n["commit"], safe_dest(n)
    check_url(repo)
    check_commit(commit)
    safe_requirements(n, dest)  # refuse a hostile file name before anything is cloned

    have = installed_commit(dest) if dest.is_dir() else ""
    if have == commit:
        print(f"  ok   {dest.name} @ {commit[:12]}")
        return True

    if not dest.is_dir():
        print(f"  get  {dest.name} <- {repo}", flush=True)
        NODES_DIR.mkdir(parents=True, exist_ok=True)
        if not git("clone", "--depth=1", repo, str(dest)):
            print(f"  BAD  {dest.name}: clone failed")
            return False
    elif not (dest / ".git").is_dir():
        print(f"  BAD  {dest.name}: present but not a git checkout -- remove it and re-run")
        return False
    else:
        print(f"  pin  {dest.name} {have[:12] or '?'} -> {commit[:12]}", flush=True)

    # --depth=1 only brings the tip, so fetch the pinned commit itself before checking it out.
    if not git("-C", str(dest), "fetch", "--depth=1", "origin", commit):
        print(f"  BAD  {dest.name}: cannot fetch pinned commit {commit[:12]}")
        return False
    if not git("-C", str(dest), "checkout", "--detach", "--force", commit):
        print(f"  BAD  {dest.name}: cannot check out {commit[:12]}")
        return False
    at = installed_commit(dest)
    if at != commit:
        print(f"  BAD  {dest.name}: HEAD is {at[:12] or '?'}, wanted {commit[:12]}")
        return False

    ok = install_requirements(n, dest)
    print(f"  {'ok' if ok else 'BAD'}   {dest.name} @ {commit[:12]}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("nodes", nargs="*", help="node directory names (default: all the catalog needs)")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    nodes = {n["dir"]: n for n in catalog_nodes()}
    if args.list:
        width = max((len(d) for d in nodes), default=0)
        for n in nodes.values():
            req = n.get("requirements", "requirements.txt")
            print(f"  {n['dir'].ljust(width)}  {n['commit'][:12]}  {n['repo']}"
                  f"  ({', '.join(n['models'])}; {req})")
        return 0
    wanted = args.nodes or list(nodes)
    bad = 0
    for d in wanted:
        n = nodes.get(d)
        if not n:
            print(f"unknown custom node: {d} (known: {', '.join(nodes) or 'none'})")
            return 2
        bad += not install(n)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
