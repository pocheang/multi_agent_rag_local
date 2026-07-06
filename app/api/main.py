"""
Main FastAPI application for QueryMind（智询）.
"""

import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Import dependencies to initialize services
from app.api import dependencies as api_dependencies
from app.api.dependencies import (
    _auto_ingest_stop_event,
    auth_service,
    auto_ingest_watcher,
    settings,
    shadow_queue,
)

# Import middleware
from app.api.middleware import request_timing_middleware

# Import route modules
from app.api.routes import (
    admin_agent_quality,
    admin_graph_rag,
    admin_language_stats,
    admin_ops,
    admin_settings,
    admin_users,
    advanced_rag,
    agent_health,
    agent_tracking,
    analytics,
    auth,
    documents,
    enhanced_query,
    evaluation,
    health,
    prompts,
    query,
    sessions,
    web_activity_admin,  # Web Activity Monitoring
)
from app.api.utils import (
    admin_helpers,
    auth_dependencies,
    auth_helpers,
    document_helpers,
    memory_helpers,
    query_helpers,
    session_helpers,
)
from app.api.utils.error_responses import not_found
from app.graph.neo4j_client import Neo4jClient
from app.services.log_buffer import setup_log_capture

auth_dependencies.auth_service = auth_service
auth_helpers.auth_service = auth_service

_ROUTE_MODULES = (
    api_dependencies,
    admin_helpers,
    auth_dependencies,
    auth_helpers,
    document_helpers,
    health,
    memory_helpers,
    query_helpers,
    session_helpers,
    auth,
    query,
    sessions,
    documents,
    prompts,
    admin_users,
    admin_ops,
    admin_settings,
    admin_language_stats,
    agent_tracking,
    evaluation,
    advanced_rag,
    analytics,
    enhanced_query,
)

# Setup logging
setup_log_capture()
logger = logging.getLogger(__name__)

# Auto-ingest watcher state
_auto_ingest_thread: threading.Thread | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage backend lifecycle (replaces deprecated on_event hooks)."""
    global _auto_ingest_thread

    # Startup
    logger.info(
        "startup_runtime python=%s conda_env=%s model_backend=%s ollama=%s chat_model=%s",
        sys.executable,
        str(os.environ.get("CONDA_DEFAULT_ENV", "") or ""),
        str(settings.model_backend or ""),
        str(settings.ollama_base_url or ""),
        str(settings.ollama_chat_model or ""),
    )

    # Start shadow queue for background processing
    shadow_queue.start()

    # Warmup: Pre-load NLI model to avoid first-query delay (P1-5 fix)
    try:
        from app.agents.answer_validator_agent import _get_nli_model
        logger.info("Warming up NLI model for hallucination detection...")
        _get_nli_model()  # Lazy load on startup
        logger.info("✓ NLI model loaded successfully")
    except Exception as e:
        logger.warning(f"NLI model warmup failed (non-critical): {e}")

    # Start Context Tracker background cleanup (P1-6 fix)
    try:
        from app.agents.context_tracker_agent import start_background_cleanup
        start_background_cleanup()
        logger.info("✓ Context Tracker background cleanup started")
    except Exception as e:
        logger.warning(f"Context cleanup startup failed (non-critical): {e}")

    # Start agent execution tracker periodic cleanup
    from app.services.agent_execution_tracker import get_tracker

    tracker = get_tracker()
    await tracker.start_periodic_cleanup(interval_seconds=300)  # 5 minutes

    if settings.auto_ingest_enabled and (_auto_ingest_thread is None or not _auto_ingest_thread.is_alive()):
        _auto_ingest_stop_event.clear()
        _auto_ingest_thread = threading.Thread(
            target=auto_ingest_watcher.run_loop,
            args=(lambda: _auto_ingest_stop_event.is_set(),),
            daemon=True,
            name="auto-ingest-watcher",
        )
        _auto_ingest_thread.start()

    try:
        yield
    finally:
        # Shutdown
        logger.info("Shutting down services...")

        # Stop Context Tracker background cleanup (P1-6 fix)
        try:
            from app.agents.context_tracker_agent import stop_background_cleanup
            stop_background_cleanup()
        except Exception as e:
            logger.warning(f"Context cleanup shutdown failed: {e}")

        # Stop agent execution tracker cleanup
        await tracker.stop_periodic_cleanup()

        _auto_ingest_stop_event.set()
        if _auto_ingest_thread is not None and _auto_ingest_thread.is_alive():
            _auto_ingest_thread.join(timeout=5)
        _auto_ingest_thread = None
        shadow_queue.stop(timeout=2.0)
        Neo4jClient.close_shared_driver()


# Initialize FastAPI app
app = FastAPI(title="QueryMind（智询）", lifespan=lifespan)

_APP_BASE_API_SEGMENTS = {
    "admin",
    "api",
    "auth",
    "documents",
    "prompts",
    "query",
    "sessions",
    "upload",
    "user",
}

_LEGACY_API_PREFIX_SEGMENTS = {
    "agent-tracking",
    "auth",
    "documents",
    "prompts",
    "query",
    "sessions",
    "upload",
}


@app.middleware("http")
async def rewrite_app_prefixed_api_paths(request, call_next):
    """Support public /app prefixes and legacy /api prefixes for bare routers."""
    path = str(request.scope.get("path", "") or "")
    if path.startswith("/app/"):
        remainder = path[len("/app/") :]
        first_segment = remainder.split("/", 1)[0]
        if first_segment in _APP_BASE_API_SEGMENTS:
            request.scope["path"] = f"/{remainder}"
    elif path.startswith("/api/"):
        remainder = path[len("/api/") :]
        first_segment = remainder.split("/", 1)[0]
        if first_segment in _LEGACY_API_PREFIX_SEGMENTS:
            request.scope["path"] = f"/{remainder}"
    return await call_next(request)

def _configure_cors(app_obj: FastAPI, settings_obj) -> None:
    """Attach CORS middleware according to settings, with prod-safety guards.

    Refuses to start when ``CORS_ALLOW_ORIGINS`` includes ``*`` and
    ``APP_ENV`` is set to ``prod`` / ``production``. Wildcards are still
    accepted in dev/staging but credentials are disabled in that case.
    """
    if not bool(getattr(settings_obj, "cors_enabled", True)):
        return

    cors_origins = settings_obj.cors_origins or []
    allow_all = "*" in cors_origins
    is_production = str(getattr(settings_obj, "app_env", "dev") or "").strip().lower() in {
        "prod",
        "production",
    }

    if allow_all and is_production:
        raise RuntimeError(
            "Refusing to start: CORS_ALLOW_ORIGINS=='*' is not allowed when APP_ENV is "
            "'prod' or 'production'. Set CORS_ALLOW_ORIGINS to an explicit comma-separated "
            "list of trusted frontend origins (https URLs)."
        )

    app_obj.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else cors_origins,
        allow_credentials=bool(getattr(settings_obj, "cors_allow_credentials", True)) and (not allow_all),
        allow_methods=settings_obj.cors_methods,
        allow_headers=settings_obj.cors_headers,
    )


# Configure CORS
_configure_cors(app, settings)

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
app.include_router(admin_language_stats.router)
app.include_router(admin_agent_quality.router)
app.include_router(agent_tracking.router)
app.include_router(agent_health.router)
app.include_router(evaluation.router)
app.include_router(advanced_rag.router)
app.include_router(analytics.router)
app.include_router(admin_graph_rag.router)
app.include_router(enhanced_query.router)
app.include_router(web_activity_admin.router)  # Web Activity Monitoring

# React frontend serving
react_dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
react_index_file = react_dist_dir / "index.html"
react_assets_dir = react_dist_dir / "assets"

# Serve React build assets
if react_assets_dir.exists():
    app.mount("/app/assets", StaticFiles(directory=str(react_assets_dir)), name="react-assets")

# Serve static files for Web Activity Dashboard
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def _serve_react_index() -> FileResponse:
    """Serve the React index.html file."""
    if not react_index_file.exists():
        raise not_found("frontend build not found")
    return FileResponse(str(react_index_file))


@app.get("/app")
@app.get("/app/")
def serve_react_app_root():
    """Serve React app root."""
    return _serve_react_index()


def __getattr__(name: str):
    """Expose route/helper symbols for backward-compatible test monkeypatching."""
    for module in _ROUTE_MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")




@app.get("/app/{frontend_path:path}")
def serve_react_app(frontend_path: str):
    """Serve React app for all frontend routes."""
    normalized = str(frontend_path or "").strip().strip("/")
    if normalized.startswith("assets/"):
        raise not_found("asset not found")
    return _serve_react_index()


class _CompatMainModule(type(sys)):
    """Backward-compat shim for tests that monkeypatch ``app.api.main`` symbols.

    Many tests do ``monkeypatch.setattr(api_main, "_audit", ...)`` or replace
    globals such as ``auth_service`` and ``settings`` on ``app.api.main``. After
    routes were split into ``app.api.routes.*`` and helpers into
    ``app.api.utils.*``, those modules each hold their own bindings to the same
    callables/instances. Without this shim, monkeypatching ``app.api.main`` no
    longer affects the actual code path executed by the routes.

    This metaclass intercepts attribute writes on the ``app.api.main`` module
    object and propagates them to every module in ``_ROUTE_MODULES`` that
    already has a binding with the same name. New route modules MUST be added
    to ``_ROUTE_MODULES`` above; otherwise their copies of shared globals will
    drift away from the patched ones.
    """

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for module in _ROUTE_MODULES:
            if hasattr(module, name):
                setattr(module, name, value)


sys.modules[__name__].__class__ = _CompatMainModule


