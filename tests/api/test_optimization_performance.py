"""Regression tests for the registered performance-optimization routes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine


def test_application_imports_with_optimization_router():
    """A registered router must not make the whole FastAPI app unimportable."""
    from app.api.main import app

    assert any(route.path == "/optimization/stats" for route in app.routes)


def test_optimization_routes_reject_unauthenticated_callers():
    """Operational metrics and mutation endpoints must not be public."""
    from app.api.main import app

    response = TestClient(app).get("/optimization/metrics")

    assert response.status_code == 401


def test_admin_can_read_optimization_metrics():
    """The route must call the monitor's real public stats API."""
    from app.api.main import app

    response = TestClient(app).get(
        "/optimization/metrics",
        headers={"X-Test-User": "admin", "X-Test-Role": "admin"},
    )

    assert response.status_code == 200
    assert "uptime_seconds" in response.json()["data"]


@pytest.mark.asyncio
async def test_clear_cache_endpoint_removes_cached_values(monkeypatch):
    """A success response must correspond to an actual cache mutation."""
    from app.api.routes.optimization import performance
    from app.services.caching.cache_manager import CacheManager

    cache = CacheManager()
    await cache.initialize()
    await cache.set("query", "cached-answer", question="q")
    monkeypatch.setattr(performance, "get_cache_manager", lambda: cache)

    response = await performance.clear_cache()

    assert response == {"success": True, "message": "All caches cleared"}
    assert await cache.get("query", question="q") is None


@pytest.mark.asyncio
async def test_clear_cache_prefix_preserves_unrelated_values(monkeypatch):
    """Prefix invalidation must not wipe unrelated cache namespaces."""
    from app.api.routes.optimization import performance
    from app.services.caching.cache_manager import CacheManager

    cache = CacheManager()
    await cache.initialize()
    await cache.set("query", "query-answer", question="q")
    await cache.set("document", "document-value", document_id="d")
    monkeypatch.setattr(performance, "get_cache_manager", lambda: cache)

    response = await performance.clear_cache(prefix="query")

    assert response == {"success": True, "message": "Cache cleared for prefix: query"}
    assert await cache.get("query", question="q") is None
    assert await cache.get("document", document_id="d") == "document-value"


def test_application_lifespan_initializes_registered_cache_service(monkeypatch):
    """Startup must initialize the same cache singleton consumed by routes."""
    from app.api.application import lifespan as lifespan_module
    from app.api.main import app
    from app.services import legacy_agent_runtime

    monkeypatch.setattr(lifespan_module.settings, "enable_reranker", False)
    monkeypatch.setattr(lifespan_module.settings, "auto_ingest_enabled", False)
    monkeypatch.setattr(legacy_agent_runtime, "warm_nli_model", lambda: None)
    monkeypatch.setattr(legacy_agent_runtime, "start_context_tracker_cleanup", lambda: None)
    monkeypatch.setattr(legacy_agent_runtime, "stop_context_tracker_cleanup", lambda: None)

    with TestClient(app) as client:
        response = client.get(
            "/optimization/cache/stats",
            headers={"X-Test-User": "admin", "X-Test-Role": "admin"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["l1"]["size"] == 0


@pytest.mark.asyncio
async def test_query_optimizer_rejects_untrusted_table_identifier():
    from app.database.query_optimizer import QueryOptimizer

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.connect() as connection:
            with pytest.raises(ValueError, match="Invalid SQL identifier"):
                await QueryOptimizer.analyze_table(connection, "sessions; DROP TABLE users")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_query_optimizer_does_not_turn_database_failure_into_success():
    from app.database.query_optimizer import QueryOptimizer

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.connect() as connection:
            with pytest.raises(Exception):
                await QueryOptimizer.get_table_stats(connection, "missing_table")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_default_database_pool_uses_async_sqlite_driver(monkeypatch, tmp_path):
    from app.database.connection_pool import DatabaseConnectionPool

    pool = DatabaseConnectionPool()
    monkeypatch.setattr(pool.settings, "database_url", f"sqlite:///{tmp_path / 'optimization.db'}")
    await pool.initialize()
    try:
        assert pool.get_pool_stats()["status"] == "active"
        async with pool.session() as session:
            value = (await session.execute(__import__("sqlalchemy").text("SELECT 1"))).scalar()
        assert value == 1
    finally:
        await pool.close()
