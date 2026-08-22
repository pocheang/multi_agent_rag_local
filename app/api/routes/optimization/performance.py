"""Performance optimization API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps.auth import require_admin
from app.database.connection_pool import get_connection_pool
from app.database.query_optimizer import QueryOptimizer, optimize_database
from app.services.caching import get_cache_manager
from app.services.optimization.memory_manager import MemoryManager, optimize_memory
from app.services.performance.monitor import get_monitor

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/optimization",
    tags=["optimization"],
    dependencies=[Depends(require_admin)],
)


@router.get("/stats")
async def get_performance_stats():
    """Get comprehensive performance statistics."""
    monitor = get_monitor()
    cache_manager = get_cache_manager()
    connection_pool = get_connection_pool()

    stats = {
        "metrics": monitor.get_all_stats(),
        "cache": cache_manager.get_stats() if cache_manager else None,
        "database": connection_pool.get_pool_stats(),
        "memory": MemoryManager.get_memory_usage(),
    }

    return {"success": True, "data": stats}


@router.get("/metrics")
async def get_metrics():
    """Get performance metrics."""
    monitor = get_monitor()
    return {"success": True, "data": monitor.get_all_stats()}


@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    cache_manager = get_cache_manager()

    if not cache_manager:
        raise HTTPException(status_code=503, detail="Cache not available")

    return {"success": True, "data": cache_manager.get_stats()}


@router.post("/cache/clear")
async def clear_cache(prefix: str | None = None):
    """Clear cache (all or specific prefix).

    Args:
        prefix: Optional cache prefix to clear
    """
    cache_manager = get_cache_manager()

    if not cache_manager:
        raise HTTPException(status_code=503, detail="Cache not available")

    if prefix:
        await cache_manager.clear_prefix(prefix)
        return {"success": True, "message": f"Cache cleared for prefix: {prefix}"}
    else:
        await cache_manager.clear()
        return {"success": True, "message": "All caches cleared"}


@router.get("/database/stats")
async def get_database_stats():
    """Get database statistics."""
    connection_pool = get_connection_pool()
    return {"success": True, "data": connection_pool.get_pool_stats()}


@router.post("/database/optimize")
async def optimize_database_tables(tables: list[str] | None = None):
    """Optimize database tables.

    Args:
        tables: List of table names to optimize (default: common tables)
    """
    if tables is None:
        tables = ["session_metadata"]

    pool = get_connection_pool()

    try:
        async with pool.session() as session:
            results = await optimize_database(session, tables)

        return {"success": True, "data": results}
    except Exception:
        logger.exception("Database optimization failed")
        raise HTTPException(status_code=500, detail="Database optimization failed")


@router.get("/database/slow-queries")
async def get_slow_queries(
    min_duration_ms: int = Query(default=1000, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
):
    """Get slow database queries.

    Args:
        min_duration_ms: Minimum query duration in milliseconds
        limit: Maximum number of queries to return
    """
    pool = get_connection_pool()
    optimizer = QueryOptimizer()

    try:
        async with pool.session() as session:
            slow_queries = await optimizer.get_slow_queries(
                session,
                min_duration_ms=min_duration_ms,
                limit=limit,
            )

        return {"success": True, "data": slow_queries}
    except Exception:
        logger.exception("Failed to fetch slow database queries")
        raise HTTPException(status_code=500, detail="Failed to fetch slow queries")


@router.get("/memory/stats")
async def get_memory_stats():
    """Get memory usage statistics."""
    stats = MemoryManager.get_memory_usage()
    return {"success": True, "data": stats}


@router.post("/memory/optimize")
async def run_memory_optimization():
    """Run memory optimization (garbage collection)."""
    try:
        stats = optimize_memory()
        return {"success": True, "data": stats}
    except Exception:
        logger.exception("Memory optimization failed")
        raise HTTPException(status_code=500, detail="Memory optimization failed")


@router.get("/memory/large-objects")
async def get_large_objects(min_size_mb: float = 1.0, limit: int = 10):
    """Get large objects in memory.

    Args:
        min_size_mb: Minimum object size in MB
        limit: Maximum number of objects to return
    """
    try:
        objects = MemoryManager.get_large_objects(min_size_mb=min_size_mb, limit=limit)
        return {"success": True, "data": objects}
    except Exception:
        logger.exception("Failed to inspect large memory objects")
        raise HTTPException(status_code=500, detail="Failed to inspect large memory objects")


@router.post("/metrics/reset")
async def reset_metrics():
    """Reset performance metrics."""
    monitor = get_monitor()
    monitor.reset()
    return {"success": True, "message": "Metrics reset"}
