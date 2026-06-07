"""
Service orchestrator — called on app startup to bring up all dependencies
and tear them down cleanly on shutdown.
"""
import asyncio
from app.backend.services import ollama_manager, comfyui_manager, model_registry
from app.backend.services import generation_queue


async def startup():
    print("[DAEMON] Starting services...")

    # Ollama starts eagerly (lightweight)
    if not ollama_manager.is_running():
        print("[DAEMON] Starting Ollama...")
        ok = ollama_manager.start()
        print(f"[DAEMON] Ollama: {'running' if ok else 'not found / failed'}")
    else:
        print("[DAEMON] Ollama already running")

    # ComfyUI starts lazily (see generation_queue — it's started on first generation)
    # But we check if it's already up
    if comfyui_manager.is_running():
        print("[DAEMON] ComfyUI already running")

    # Build model registry
    print("[DAEMON] Scanning installed models...")
    model_registry.refresh()
    print(f"[DAEMON] Registry built: {len(model_registry.get_all())} entries")

    # Wire event loop into queue worker
    loop = asyncio.get_event_loop()
    generation_queue.set_event_loop(loop)
    generation_queue.start_worker()
    print("[DAEMON] Generation queue worker started")

    print("[DAEMON] Startup complete")


async def shutdown():
    print("[DAEMON] Shutting down services...")
    generation_queue.stop_worker()
    comfyui_manager.stop()
    ollama_manager.stop()
    print("[DAEMON] Shutdown complete")
