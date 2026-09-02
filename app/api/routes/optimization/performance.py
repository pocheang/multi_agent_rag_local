"""Performance optimization API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps.auth import require_admin
from app.services.caching import CACHE_PREFIX_PATTERN, get_cache_manager
from app.services.optimization.memory_manager import MemoryManager, optimize_memory
from app.services.performance.monitor import get_monitor

logger = logging.getLogger(__name__)

# A namespace name, not a glob. The value reaches `scan_iter(match=f"{prefix}:*")`,
# so an unconstrained string is a Redis pattern: `*` clears everything, which is
# a different operation from the one this parameter names (and one this endpoint
# already offers by omitting the parameter). Admin-only either way, so the point
# is that the parameter does what it says, not that it stops an attacker.
CachePrefix = Annotated[str | None, Query(pattern=CACHE_PREFIX_PATTERN, max_length=64)]

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

    stats = {
        "metrics": monitor.get_all_stats(),
        "cache": cache_manager.get_stats() if cache_manager else None,
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
async def clear_cache(prefix: CachePrefix = None):
    """Clear cache (all or specific prefix).

    Args:
        prefix: Optional cache namespace to clear. A name, not a pattern -- see
            CachePrefix.
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
