"""
AI Video Studio — FastAPI Backend Daemon
Runs on localhost:7860
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend.db import init_db
from app.backend import daemon
from app.backend.routes import (
    projects, generation, models, skills, system, templates, versions, batch,
    updates, voices, longform,
)
from app.backend.version import VERSION, BUILD


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await daemon.startup()
    yield
    await daemon.shutdown()


app = FastAPI(
    title="AI Video Studio",
    description="Backend daemon for AI Video Studio desktop app",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(projects.router)
app.include_router(generation.router)
app.include_router(models.router)
app.include_router(skills.router)
app.include_router(templates.router)
app.include_router(versions.router)
app.include_router(batch.router)
app.include_router(updates.router)
app.include_router(voices.router)
app.include_router(longform.router)


@app.get("/")
def root():
    return {"name": "AI Video Studio Backend", "version": VERSION, "status": "running"}


@app.get("/version")
def version():
    """Returns version metadata for the About dialog and update checks."""
    import platform as _plat
    return {
        "version":  VERSION,
        "build":    BUILD,
        "python":   _plat.python_version(),
        "platform": _plat.platform(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.backend.main:app", host="127.0.0.1", port=7860, reload=False)
