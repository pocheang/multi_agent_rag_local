"""Application startup and shutdown lifecycle for the QueryMind API."""

from __future__ import annotations

import logging
import os
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import dependencies as api_dependencies
from app.api.dependencies import (
    _auto_ingest_stop_event,
    auto_ingest_watcher,
)
from app.api.deps.runtime import install_app_services
from app.core.config import validate_security_settings
from app.graph.knowledge.client import Neo4jClient
from app.services.observability.log_buffer import setup_log_capture

setup_log_capture()
logger = logging.getLogger(__name__)
_auto_ingest_thread: threading.Thread | None = None

# Performance optimization imports
_pool_initialized = False
_cache_initialized = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage backend lifecycle (replaces deprecated on_event hooks)."""
    global _auto_ingest_thread
    query_runtime = api_dependencies.get_query_runtime()
    settings = query_runtime.settings
    validate_security_settings(settings)

    install_app_services(app)
    logger.info(
        "startup_runtime python=%s conda_env=%s model_backend=%s ollama=%s chat_model=%s",
        sys.executable,
        str(os.environ.get("CONDA_DEFAULT_ENV", "") or ""),
        str(settings.model_backend or ""),
        str(settings.ollama_base_url or ""),
        str(settings.ollama_chat_model or ""),
    )

    query_runtime.shadow_queue.start()

    try:
        from app.services.legacy_agent_runtime import warm_nli_model

        logger.info("Warming up NLI model for hallucination detection...")
        warm_nli_model()
        logger.info("✓ NLI model loaded successfully")
    except Exception as e:
        logger.warning(f"NLI model warmup failed (non-critical): {e}")

    # Warm up reranker model
    if settings.enable_reranker:
        try:
            from app.retrievers.reranker import _load_cross_encoder

            logger.info("Warming up reranker model (%s)...", settings.reranker_model_name)
            model = _load_cross_encoder()
            if model is not None:
                logger.info("✓ Reranker model loaded successfully")
            else:
                logger.warning("⚠ Reranker model not available (will use lexical fallback)")
        except Exception as e:
            logger.warning(f"Reranker model warmup failed (non-critical): {e}")

    try:
        from app.services.legacy_agent_runtime import start_context_tracker_cleanup

        start_context_tracker_cleanup()
        logger.info("✓ Context Tracker background cleanup started")
    except Exception as e:
        logger.warning(f"Context cleanup startup failed (non-critical): {e}")

    from app.services.observability.agent_execution_tracker import get_tracker

    tracker = get_tracker()
    await tracker.start_periodic_cleanup(interval_seconds=300)

    # Initialize performance optimization services
    global _pool_initialized, _cache_initialized

    try:
        from app.database.connection_pool import initialize_pool

        await initialize_pool()
        _pool_initialized = True
        logger.info("✓ Database connection pool initialized (size=%d)", settings.db_pool_size)
    except Exception as e:
        logger.warning(f"Database pool initialization failed (non-critical): {e}")

    try:
        from app.services.caching import initialize_cache_manager

        await initialize_cache_manager(
            l1_max_size=settings.cache_l1_size,
            l1_ttl=settings.cache_l1_ttl,
            l2_enabled=settings.cache_l2_enabled,
            l2_ttl=settings.cache_l2_ttl,
            redis_url=settings.redis_url if settings.cache_l2_enabled else None,
        )
        _cache_initialized = True
        logger.info(
            "✓ Cache manager initialized (L1: %d items, L2: %s)",
            settings.cache_l1_size,
            "enabled" if settings.cache_l2_enabled else "disabled",
        )
    except Exception as e:
        logger.warning(f"Cache manager initialization failed (non-critical): {e}")

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
        api_dependencies.get_query_runtime().shadow_queue.stop(timeout=2.0)
        Neo4jClient.close_shared_driver()

        # Shutdown performance optimization services
        if _pool_initialized:
            try:
                from app.database.connection_pool import close_pool

                await close_pool()
                logger.info("Database connection pool closed")
            except Exception as e:
                logger.warning(f"Database pool shutdown failed: {e}")

        if _cache_initialized:
            try:
                from app.services.caching import close_cache_manager

                await close_cache_manager()
                logger.info("Cache manager closed")
            except Exception as e:
                logger.warning(f"Cache manager shutdown failed: {e}")


__all__ = ["lifespan"]
