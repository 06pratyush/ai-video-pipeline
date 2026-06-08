"""Auto-update checker — polls GitHub Releases for newer versions."""
import requests
from fastapi import APIRouter
from app.backend.main import VERSION

router = APIRouter(prefix="/updates", tags=["updates"])

GITHUB_RELEASES_API = (
    "https://api.github.com/repos/06pratyush/ai-video-pipeline/releases/latest"
)


def _parse_version(v: str) -> tuple[int, int, int]:
    """Parse 'v1.2.3' or '1.2.3' into a comparable tuple. Returns (0,0,0) on failure."""
    cleaned = v.lstrip("v").split("-")[0]  # strip 'v' prefix and pre-release tags
    parts = cleaned.split(".")
    try:
        return tuple(int(p) for p in parts[:3]) + (0,) * (3 - len(parts))  # type: ignore
    except ValueError:
        return (0, 0, 0)


@router.get("/check")
def check_for_updates():
    """
    Query GitHub for the latest release. Returns current/latest versions and
    whether an update is available. Does not download anything.
    """
    try:
        resp = requests.get(GITHUB_RELEASES_API, timeout=8)
        if resp.status_code != 200:
            return {
                "available":     False,
                "current":       VERSION,
                "latest":        None,
                "error":         f"GitHub API returned {resp.status_code}",
            }
        data = resp.json()
        latest_tag = data.get("tag_name", "")
        latest_url = data.get("html_url", "")
        release_notes = data.get("body", "")
        published = data.get("published_at", "")

        current_t = _parse_version(VERSION)
        latest_t  = _parse_version(latest_tag)
        available = latest_t > current_t

        # Pick the right asset for the user's platform
        assets = data.get("assets", [])
        downloads: dict[str, str] = {}
        for a in assets:
            name = a.get("name", "").lower()
            url  = a.get("browser_download_url", "")
            if name.endswith(".exe") and "portable" not in name:
                downloads["windows"] = url
            elif name.endswith(".appimage"):
                downloads["linux_appimage"] = url
            elif name.endswith(".deb"):
                downloads["linux_deb"] = url
            elif name.endswith(".dmg") and "arm64" in name:
                downloads["macos_arm64"] = url
            elif name.endswith(".dmg"):
                downloads["macos_x64"] = url

        return {
            "available":     available,
            "current":       VERSION,
            "latest":        latest_tag,
            "release_url":   latest_url,
            "published_at":  published,
            "release_notes": release_notes[:2000],  # cap to keep response light
            "downloads":     downloads,
        }
    except requests.RequestException as e:
        return {
            "available":     False,
            "current":       VERSION,
            "latest":        None,
            "error":         str(e),
        }
