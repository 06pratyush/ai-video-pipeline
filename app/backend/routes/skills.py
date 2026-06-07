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
