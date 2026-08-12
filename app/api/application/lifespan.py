"""Application startup and shutdown lifecycle for the QueryMind API."""

from __future__ import annotations

import logging
import os
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.dependencies import (
    _auto_ingest_stop_event,
    auto_ingest_watcher,
    settings,
    shadow_queue,
)
from app.api.deps.runtime import install_app_services
from app.graph.knowledge.client import Neo4jClient
from app.services.observability.log_buffer import setup_log_capture

setup_log_capture()
logger = logging.getLogger(__name__)
_auto_ingest_thread: threading.Thread | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage backend lifecycle (replaces deprecated on_event hooks)."""
    global _auto_ingest_thread

    install_app_services(app)
    logger.info(
        "startup_runtime python=%s conda_env=%s model_backend=%s ollama=%s chat_model=%s",
        sys.executable,
        str(os.environ.get("CONDA_DEFAULT_ENV", "") or ""),
        str(settings.model_backend or ""),
        str(settings.ollama_base_url or ""),
        str(settings.ollama_chat_model or ""),
    )

    shadow_queue.start()

    try:
        from app.services.legacy_agent_runtime import warm_nli_model

        logger.info("Warming up NLI model for hallucination detection...")
        warm_nli_model()
        logger.info("✓ NLI model loaded successfully")
    except Exception as e:
        logger.warning(f"NLI model warmup failed (non-critical): {e}")

    try:
        from app.services.legacy_agent_runtime import start_context_tracker_cleanup

        start_context_tracker_cleanup()
        logger.info("✓ Context Tracker background cleanup started")
    except Exception as e:
        logger.warning(f"Context cleanup startup failed (non-critical): {e}")

    from app.services.observability.agent_execution_tracker import get_tracker

    tracker = get_tracker()
    await tracker.start_periodic_cleanup(interval_seconds=300)

    if settings.auto_ingest_enabled and (
        _auto_ingest_thread is None or not _auto_ingest_thread.is_alive()
    ):
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
        logger.info("Shutting down services...")

        try:
            from app.services.legacy_agent_runtime import stop_context_tracker_cleanup

            stop_context_tracker_cleanup()
        except Exception as e:
            logger.warning(f"Context cleanup shutdown failed: {e}")

        await tracker.stop_periodic_cleanup()

        _auto_ingest_stop_event.set()
        if _auto_ingest_thread is not None and _auto_ingest_thread.is_alive():
            _auto_ingest_thread.join(timeout=5)
        _auto_ingest_thread = None
        shadow_queue.stop(timeout=2.0)
        Neo4jClient.close_shared_driver()


__all__ = ["lifespan"]
