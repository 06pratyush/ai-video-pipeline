"""Download the v2 model files listed in installer/catalog.json, resumably, and verify them.

    venv311\\Scripts\\python.exe scripts\\setup_models.py                 # the default v2 stack
    venv311\\Scripts\\python.exe scripts\\setup_models.py flux-kontext    # one model (non-commercial)
    venv311\\Scripts\\python.exe scripts\\setup_models.py --list

Safety: only https downloads from huggingface.co and github.com are allowed; files go only
to the catalog's install_path under this repository; each file is checked against the
catalog's exact byte size (and sha256 where the catalog has one) before it is kept.
Interrupted downloads resume from where they stopped.
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "installer" / "catalog.json"
DEFAULT = ["wan2.2-ti2v-5b", "flux-schnell", "ace-step-3.5b", "rife-esrgan"]
ALLOWED_HOSTS = {"huggingface.co", "github.com"}


def file_url(f: dict) -> str:
    if "url" in f:
        return f["url"]
    return f"https://huggingface.co/{f['hf_repo']}/resolve/main/{f['file']}"


def safe_dest(f: dict) -> Path:
    dest = (ROOT / f["install_path"] / Path(f["file"]).name).resolve()
    if ROOT.resolve() not in dest.parents:
        raise ValueError(f"install_path escapes the repository: {f['install_path']}")
    return dest


def check_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"refusing to download from {url}: only https from {sorted(ALLOWED_HOSTS)}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def download(url: str, dest: Path, want: int | None, attempts: int = 60) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    if dest.exists() and not part.exists():
        dest.replace(part)  # resume an earlier partial file left under the final name
    for attempt in range(attempts):
        have = part.stat().st_size if part.exists() else 0
        if want and have == want:
            break
        req = urllib.request.Request(url, headers={"User-Agent": "ai-video-studio-setup"})
        if have:
            req.add_header("Range", f"bytes={have}-")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                mode = "ab" if have and r.status == 206 else "wb"
                with open(part, mode) as out:
                    while chunk := r.read(1 << 20):
                        out.write(chunk)
            if not want:
                break
        except OSError as e:
            print(f"    retry {attempt + 1}: {e}", flush=True)
            time.sleep(min(30, 2 + attempt))
    part.replace(dest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="*", help="catalog ids (default: the v2 stack)")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    catalog = {m["id"]: m for m in json.loads(CATALOG.read_text(encoding="utf-8"))["models"]}
    if args.list:
        for m in catalog.values():
            if m.get("files"):
                nc = "  [NON-COMMERCIAL]" if m.get("non_commercial") else ""
                print(f"  {m['id']:<16} {m['size_gb']:>5} GB  {m.get('license', '?')}{nc}")
        return 0
    ids = args.models or DEFAULT
    bad = 0
    for mid in ids:
        m = catalog.get(mid)
        if not m or not m.get("files"):
            print(f"unknown or non-downloadable model: {mid}")
            return 2
        if m.get("non_commercial"):
            print(f"NOTE: {m['name']} is licensed for non-commercial use only.")
        for f in m["files"]:
            url, dest, want = file_url(f), safe_dest(f), f.get("bytes")
            check_url(url)
            if dest.exists() and want and dest.stat().st_size == want:
                print(f"  ok   {dest.name}")
                continue
            print(f"  get  {dest.name} ({(want or 0) / 1e9:.2f} GB)", flush=True)
            download(url, dest, want)
            size = dest.stat().st_size
            ok = (not want or size == want) and (not f.get("sha256") or sha256(dest) == f["sha256"])
            print(f"  {'ok' if ok else 'BAD'}  {dest.name} {size} bytes")
            bad += not ok
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
