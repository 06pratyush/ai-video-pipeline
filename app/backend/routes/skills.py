"""Skills system endpoints."""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/skills", tags=["skills"])

SKILLS_DIR = Path("app/skills")


@router.get("/")
def list_skills():
    skills = []
    for f in sorted(SKILLS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            skills.append(data)
        except Exception:
            pass
    return skills


@router.get("/{skill_id}")
def get_skill(skill_id: str):
    path = SKILLS_DIR / f"{skill_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return json.loads(path.read_text())


@router.post("/")
def create_skill(skill: dict):
    skill_id = skill.get("id")
    if not skill_id:
        raise HTTPException(status_code=400, detail="Skill must have an 'id' field")
    path = SKILLS_DIR / f"{skill_id}.json"
    if path.exists():
        raise HTTPException(status_code=409, detail=f"Skill '{skill_id}' already exists")
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(skill, indent=2))
    return skill


@router.put("/{skill_id}")
def update_skill(skill_id: str, skill: dict):
    path = SKILLS_DIR / f"{skill_id}.json"
    skill["id"] = skill_id
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(skill, indent=2))
    return skill


@router.delete("/{skill_id}")
def delete_skill(skill_id: str):
    path = SKILLS_DIR / f"{skill_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    path.unlink()
    return {"deleted": skill_id}


@router.get("/{skill_id}/export")
def export_skill(skill_id: str):
    """Return a Skill as a downloadable JSON file."""
    from fastapi.responses import FileResponse
    path = SKILLS_DIR / f"{skill_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return FileResponse(
        path,
        media_type="application/json",
        filename=f"{skill_id}.skill.json",
    )


@router.post("/import")
def import_skill(skill: dict):
    """
    Import a Skill from a JSON payload (e.g. uploaded file).
    Validates required fields, assigns a fresh id if it would collide.
    """
    required = ["name", "voice", "prompt_template", "aspect_ratio"]
    missing = [f for f in required if f not in skill]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Skill missing required fields: {', '.join(missing)}",
        )

    skill_id = skill.get("id") or skill["name"].lower().replace(" ", "-")
    path = SKILLS_DIR / f"{skill_id}.json"

    # Collision handling — suffix with -1, -2, ...
    if path.exists():
        i = 1
        while (SKILLS_DIR / f"{skill_id}-{i}.json").exists():
            i += 1
        skill_id = f"{skill_id}-{i}"
        path = SKILLS_DIR / f"{skill_id}.json"

    skill["id"] = skill_id
    skill.setdefault("voice_speed", 1.0)
    skill.setdefault("scene_pacing", "medium")
    skill.setdefault("resolution", "1080p")
    skill.setdefault("subtitles", False)
    skill.setdefault("music_mood", "ambient_score")
    skill.setdefault("post_processing", [])
    skill.setdefault("description", "")
    skill.setdefault("icon", f"{skill_id}.svg")

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(skill, indent=2))
    return skill
