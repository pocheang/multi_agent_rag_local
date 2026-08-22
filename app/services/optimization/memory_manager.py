"""Memory management utilities."""

import gc
import logging
import sys
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)


class MemoryManager:
    """Memory management utilities."""

    @staticmethod
    def get_memory_usage() -> dict[str, float]:
        """Get current memory usage.

        Returns:
            Dictionary with memory stats in MB
        """
        import os

        import psutil

        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()

        return {
            "rss_mb": mem_info.rss / 1024 / 1024,  # Resident Set Size
            "vms_mb": mem_info.vms / 1024 / 1024,  # Virtual Memory Size
            "percent": process.memory_percent(),
        }

    @staticmethod
    @contextmanager
    def track_memory(operation: str = "operation"):
        """Context manager to track memory usage.

        Args:
            operation: Name of operation being tracked
        """
        before = MemoryManager.get_memory_usage()
        logger.debug(f"[{operation}] Memory before: {before['rss_mb']:.1f} MB")

        try:
            yield
        finally:
            after = MemoryManager.get_memory_usage()
            delta = after["rss_mb"] - before["rss_mb"]
            logger.debug(f"[{operation}] Memory after: {after['rss_mb']:.1f} MB (delta: {delta:+.1f} MB)")

    @staticmethod
    def force_gc():
        """Force garbage collection."""
        collected = gc.collect()
        logger.debug(f"Garbage collected {collected} objects")
        return collected

    @staticmethod
    def get_object_count() -> int:
        """Get total number of tracked objects."""
        return len(gc.get_objects())

    @staticmethod
    def get_large_objects(min_size_mb: float = 1.0, limit: int = 10) -> list[dict[str, Any]]:
        """Find large objects in memory.

        Args:
            min_size_mb: Minimum size in MB
            limit: Maximum number of objects to return

        Returns:
            List of large objects with their info
        """
        min_size_bytes = min_size_mb * 1024 * 1024
        large_objects = []

        for obj in gc.get_objects():
            try:
                size = sys.getsizeof(obj)
                if size >= min_size_bytes:
                    large_objects.append(
                        {
                            "type": type(obj).__name__,
                            "size_mb": size / 1024 / 1024,
                            "repr": str(obj)[:100],
                        }
                    )
            except Exception:
                pass

        # Sort by size and limit
        large_objects.sort(key=lambda x: x["size_mb"], reverse=True)
        return large_objects[:limit]


def optimize_memory():
    """Run memory optimization."""
    logger.info("Running memory optimization...")

    # Force garbage collection
    collected = MemoryManager.force_gc()

    # Get memory stats
    mem_usage = MemoryManager.get_memory_usage()

    logger.info(f"Memory optimization complete: collected {collected} objects, RSS: {mem_usage['rss_mb']:.1f} MB")

    return mem_usage
