"""Generation queue endpoints and WebSocket progress streaming."""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import asyncio
import json

from app.backend.db import get_db
from app.backend.models.project import Project
from app.backend.models.queue_item import QueueItem
from app.backend.services import generation_queue

router = APIRouter(prefix="/generation", tags=["generation"])

# Active WebSocket connections keyed by project_id
_ws_clients: dict[str, list[WebSocket]] = {}


async def broadcast_progress(project_id: str, stage: str, progress: float, status: str, message: str = ""):
    """Called by generation_queue worker to push progress to connected frontends."""
    clients = _ws_clients.get(project_id, [])
    payload = json.dumps({
        "project_id": project_id,
        "stage": stage,
        "progress": progress,
        "status": status,
        "message": message,
    })
    dead = []
    for ws in clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.remove(ws)


# Register broadcast hook with queue service
generation_queue.broadcast_progress = broadcast_progress


@router.websocket("/ws/{project_id}")
async def progress_ws(websocket: WebSocket, project_id: str):
    await websocket.accept()
    _ws_clients.setdefault(project_id, []).append(websocket)
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"ping": True}))
    except WebSocketDisconnect:
        if project_id in _ws_clients:
            _ws_clients[project_id] = [
                w for w in _ws_clients[project_id] if w is not websocket
            ]


class GenerateRequest(BaseModel):
    project_id: str


@router.post("/start")
def start_generation(req: GenerateRequest, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(id=req.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status == "running":
        raise HTTPException(status_code=409, detail="Project is already generating")
    queue_id = generation_queue.enqueue(req.project_id)
    project.status = "queued"
    db.commit()
    return {"queued": True, "queue_item_id": queue_id}


@router.post("/cancel/{queue_item_id}")
def cancel_generation(queue_item_id: str):
    generation_queue.cancel(queue_item_id)
    return {"cancelled": queue_item_id}


@router.get("/queue")
def get_queue(db: Session = Depends(get_db)):
    items = (
        db.query(QueueItem)
        .filter(QueueItem.status.in_(["queued", "running"]))
        .order_by(QueueItem.created_at)
        .all()
    )
    return [
        {
            "id": i.id,
            "project_id": i.project_id,
            "stage": i.stage,
            "status": i.status,
            "progress": i.progress,
            "eta_seconds": i.eta_seconds,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in items
    ]


@router.get("/history")
def get_history(db: Session = Depends(get_db), limit: int = 20):
    items = (
        db.query(QueueItem)
        .filter(QueueItem.status.in_(["done", "error", "cancelled"]))
        .order_by(QueueItem.completed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": i.id,
            "project_id": i.project_id,
            "stage": i.stage,
            "status": i.status,
            "error_message": i.error_message,
            "completed_at": i.completed_at.isoformat() if i.completed_at else None,
        }
        for i in items
    ]
