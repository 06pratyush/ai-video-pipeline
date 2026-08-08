"""
Integration tests for the defects fixed in the data-integrity pass.

Each test pins one previously-broken behaviour so it cannot silently regress.
Runs against a throwaway SQLite file via AIVS_DB_PATH — never the user's real DB.
"""
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

# Point the engine at a temp DB *before* importing anything that builds it.
_TMP_DB = Path(tempfile.mkdtemp(prefix="aivs_test_")) / "test.sqlite"
os.environ["AIVS_DB_PATH"] = str(_TMP_DB)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.backend.db import SessionLocal, init_db  # noqa: E402
from app.backend.models.project import Project  # noqa: E402
from app.backend.models.scene import Scene  # noqa: E402
from app.backend.models.queue_item import QueueItem  # noqa: E402
from app.backend.models.project_version import (  # noqa: E402
    ProjectVersion, next_version_num,
)
from app.backend.services import generation_queue  # noqa: E402

init_db()

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = ""):
    (PASS if condition else FAIL).append(name)
    print(f"{'PASS' if condition else 'FAIL'}: {name}" + (f" — {detail}" if detail and not condition else ""))


def _make_project(db, name="p") -> Project:
    p = Project(id=str(uuid.uuid4()), name=name, topic="t", script="original script")
    db.add(p)
    db.flush()
    db.add(Scene(id=str(uuid.uuid4()), project_id=p.id, index=0, prompt="original prompt", seed=11))
    db.commit()
    return p


def _make_version(db, project_id, num, label="v"):
    v = ProjectVersion(
        id=str(uuid.uuid4()), project_id=project_id, version_num=num,
        label=label, snapshot=json.dumps({"script": f"snap{num}", "scenes": []}),
    )
    db.add(v)
    db.commit()
    return v


def test_version_num_survives_deletion():
    """count()+1 collided after a delete and overwrote an existing version's video."""
    db = SessionLocal()
    try:
        p = _make_project(db)
        for n in (1, 2, 3):
            _make_version(db, p.id, n)
        v2 = db.query(ProjectVersion).filter_by(project_id=p.id, version_num=2).first()
        db.delete(v2)
        db.commit()

        nxt = next_version_num(db, p.id)
        existing = {v.version_num for v in db.query(ProjectVersion).filter_by(project_id=p.id)}
        check("next_version_num does not collide after deletion",
              nxt == 4 and nxt not in existing, f"got {nxt}, existing={sorted(existing)}")
    finally:
        db.close()


def test_project_delete_cascades_versions():
    """Version rows used to survive their parent project, dangling forever."""
    db = SessionLocal()
    try:
        p = _make_project(db)
        _make_version(db, p.id, 1)
        pid = p.id
        db.delete(p)
        db.commit()
        left = db.query(ProjectVersion).filter_by(project_id=pid).count()
        scenes_left = db.query(Scene).filter_by(project_id=pid).count()
        check("deleting a project cascades to its versions", left == 0, f"{left} orphan version rows")
        check("deleting a project cascades to its scenes", scenes_left == 0, f"{scenes_left} orphan scenes")
    finally:
        db.close()


def test_recover_orphaned_items():
    """A job left 'running' by a crash was stranded — the worker only picks up 'queued'."""
    db = SessionLocal()
    try:
        p = _make_project(db)
        p.status = "running"
        item = QueueItem(project_id=p.id, stage="full_pipeline", status="running", progress=0.5)
        db.add(item)
        db.commit()
        item_id, pid = item.id, p.id
    finally:
        db.close()

    recovered = generation_queue.recover_orphaned_items()

    db = SessionLocal()
    try:
        item = db.query(QueueItem).filter_by(id=item_id).first()
        proj = db.query(Project).filter_by(id=pid).first()
        check("recover_orphaned_items requeues interrupted jobs",
              recovered >= 1 and item.status == "queued", f"status={item.status}")
        check("recovery resets the project back to queued", proj.status == "queued", f"status={proj.status}")
    finally:
        db.close()


def test_cancellation_is_observed_across_sessions():
    """cancel() commits from another session; the pipeline must actually see it."""
    db = SessionLocal()
    try:
        p = _make_project(db)
        item = QueueItem(project_id=p.id, stage="full_pipeline", status="running")
        db.add(item)
        db.commit()
        item_id = item.id
    finally:
        db.close()

    before = generation_queue._is_cancelled(item_id)
    generation_queue.cancel(item_id)
    after = generation_queue._is_cancelled(item_id)
    check("_is_cancelled sees a cancel committed by another session",
          before is False and after is True, f"before={before} after={after}")


def test_restore_backs_up_current_state():
    """Restore overwrote live work in place with no way back."""
    from fastapi.testclient import TestClient
    from app.backend.main import app

    db = SessionLocal()
    try:
        p = _make_project(db, name="restore-target")
        pid = p.id
        _make_version(db, pid, 1, label="old")
        vid = db.query(ProjectVersion).filter_by(project_id=pid, version_num=1).first().id
    finally:
        db.close()

    with TestClient(app) as client:
        resp = client.post(f"/projects/{pid}/versions/{vid}/restore")
        check("restore endpoint succeeds", resp.status_code == 200, f"{resp.status_code} {resp.text[:200]}")
        if resp.status_code != 200:
            return
        body = resp.json()
        check("restore reports the auto-backup it created", "backup_version" in body, str(body))

    db = SessionLocal()
    try:
        backups = [
            v for v in db.query(ProjectVersion).filter_by(project_id=pid)
            if (v.label or "").startswith("Auto-backup")
        ]
        check("restore snapshots pre-restore state", len(backups) == 1, f"found {len(backups)}")
        if backups:
            snap = json.loads(backups[0].snapshot)
            check("backup captured the original script",
                  snap.get("script") == "original script", f"got {snap.get('script')!r}")
            check("backup captured the original scene prompt",
                  snap.get("scenes", [{}])[0].get("prompt") == "original prompt", str(snap.get("scenes")))
    finally:
        db.close()


if __name__ == "__main__":
    test_version_num_survives_deletion()
    test_project_delete_cascades_versions()
    test_recover_orphaned_items()
    test_cancellation_is_observed_across_sessions()
    test_restore_backs_up_current_state()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED: " + ", ".join(FAIL))
    raise SystemExit(1 if FAIL else 0)
