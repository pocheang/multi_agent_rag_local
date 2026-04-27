"""
Main FastAPI application for Multi-Agent Local RAG.
"""
import logging
import os
import sys
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.services.log_buffer import setup_log_capture
from app.graph.neo4j_client import Neo4jClient

# Import dependencies to initialize services
from app.api.dependencies import (
    auto_ingest_watcher,
    shadow_queue,
    settings,
    _auto_ingest_stop_event,
)

# Import middleware
from app.api.middleware import request_timing_middleware

# Import route modules
from app.api.routes import health, auth, query, sessions, documents, prompts
from app.api.routes import admin_users, admin_ops, admin_settings

# Initialize FastAPI app
app = FastAPI(title="Multi-Agent Local RAG")

# Setup logging
setup_log_capture()
logger = logging.getLogger(__name__)

# Configure CORS
if bool(getattr(settings, "cors_enabled", True)):
    cors_origins = settings.cors_origins or []
    allow_all = "*" in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else cors_origins,
        allow_credentials=bool(getattr(settings, "cors_allow_credentials", True)) and (not allow_all),
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
    )

# Add request timing middleware
app.middleware("http")(request_timing_middleware)

# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(query.router)
app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(prompts.router)
app.include_router(admin_users.router)
app.include_router(admin_ops.router)
app.include_router(admin_settings.router)

# React frontend serving
react_dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
react_index_file = react_dist_dir / "index.html"
react_assets_dir = react_dist_dir / "assets"

# Serve React build assets
if react_assets_dir.exists():
    app.mount("/app/assets", StaticFiles(directory=str(react_assets_dir)), name="react-assets")


def _serve_react_index() -> FileResponse:
    """Serve the React index.html file."""
    if not react_index_file.exists():
        raise HTTPException(status_code=404, detail="frontend build not found")
    return FileResponse(str(react_index_file))


@app.get("/app")
@app.get("/app/")
def serve_react_app_root():
    """Serve React app root."""
    return _serve_react_index()


@app.get("/app/{frontend_path:path}")
def serve_react_app(frontend_path: str):
    """Serve React app for all frontend routes."""
    normalized = str(frontend_path or "").strip().strip("/")
    if normalized.startswith("assets/"):
        raise HTTPException(status_code=404, detail="asset not found")
    return _serve_react_index()


# Auto-ingest watcher state
_auto_ingest_thread: threading.Thread | None = None


@app.on_event("startup")
def start_auto_ingest_watcher():
    """Start the auto-ingest watcher on application startup."""
    global _auto_ingest_thread
    logger.info(
        "startup_runtime python=%s conda_env=%s model_backend=%s ollama=%s chat_model=%s",
        sys.executable,
        str(os.environ.get("CONDA_DEFAULT_ENV", "") or ""),
        str(settings.model_backend or ""),
        str(settings.ollama_base_url or ""),
        str(settings.ollama_chat_model or ""),
    )
    shadow_queue.start()
    if not settings.auto_ingest_enabled:
        return
    if _auto_ingest_thread is not None and _auto_ingest_thread.is_alive():
        return
    _auto_ingest_stop_event.clear()
    _auto_ingest_thread = threading.Thread(
        target=auto_ingest_watcher.run_loop,
        args=(lambda: _auto_ingest_stop_event.is_set(),),
        daemon=True,
        name="auto-ingest-watcher",
    )
    _auto_ingest_thread.start()


@app.on_event("shutdown")
def stop_auto_ingest_watcher():
    """Stop the auto-ingest watcher on application shutdown."""
    global _auto_ingest_thread
    _auto_ingest_stop_event.set()
    if _auto_ingest_thread is not None and _auto_ingest_thread.is_alive():
        _auto_ingest_thread.join(timeout=5)
    _auto_ingest_thread = None
    shadow_queue.stop(timeout=2.0)
    Neo4jClient.close_shared_driver()
