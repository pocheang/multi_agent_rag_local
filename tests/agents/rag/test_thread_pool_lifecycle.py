"""Test thread pool lifecycle management in RAG service.

Verifies that the thread pool is lazily initialized and properly cleaned up,
preventing resource leaks.
"""

import concurrent.futures
import threading

import pytest

from app.agents.rag import service


def test_thread_pool_is_not_created_at_import() -> None:
    """Thread pool should not exist until first use (lazy initialization)."""
    # Access the module-level variable directly
    assert service._retriever_pool is None, "Thread pool should not be created at import time"


def test_thread_pool_is_created_on_first_access() -> None:
    """Thread pool should be created on first access."""
    pool = service._get_retriever_pool()
    assert isinstance(pool, concurrent.futures.ThreadPoolExecutor)
    assert pool is not None


def test_thread_pool_is_reused() -> None:
    """Subsequent calls should return the same pool instance."""
    pool1 = service._get_retriever_pool()
    pool2 = service._get_retriever_pool()
    assert pool1 is pool2, "Should return the same pool instance"


def test_thread_pool_shutdown() -> None:
    """Thread pool should be cleanly shutdown."""
    # Create pool
    pool = service._get_retriever_pool()
    assert pool is not None

    # Shutdown
    service._shutdown_retriever_pool()

    # Pool should be None after shutdown
    assert service._retriever_pool is None


def test_thread_pool_can_be_recreated_after_shutdown() -> None:
    """Pool can be recreated after explicit shutdown."""
    # Create and shutdown
    pool1 = service._get_retriever_pool()
    service._shutdown_retriever_pool()

    # Create again
    pool2 = service._get_retriever_pool()
    assert pool2 is not None
    assert pool1 is not pool2, "Should be a new pool instance"

    # Cleanup for other tests
    service._shutdown_retriever_pool()


def test_thread_pool_thread_safety() -> None:
    """Pool creation should be thread-safe (no race conditions)."""
    # Reset pool
    service._shutdown_retriever_pool()

    pools = []
    errors = []

    def create_pool():
        try:
            pool = service._get_retriever_pool()
            pools.append(pool)
        except Exception as e:
            errors.append(e)

    # Create 10 threads that all try to get the pool simultaneously
    threads = [threading.Thread(target=create_pool) for _ in range(10)]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # No errors should occur
    assert len(errors) == 0, f"Thread safety errors: {errors}"

    # All threads should get the same pool instance
    assert len(set(id(p) for p in pools)) == 1, "All threads should get the same pool"

    # Cleanup
    service._shutdown_retriever_pool()


def test_thread_pool_has_correct_configuration() -> None:
    """Pool should be configured with correct parameters."""
    pool = service._get_retriever_pool()

    # Check max_workers via internal attribute (implementation detail, but useful for testing)
    assert pool._max_workers == service._MAX_WORKERS

    # Check thread name prefix by submitting a dummy task
    def get_thread_name():
        return threading.current_thread().name

    future = pool.submit(get_thread_name)
    thread_name = future.result(timeout=1.0)

    assert thread_name.startswith("retriever"), f"Thread name should start with 'retriever', got: {thread_name}"

    # Cleanup
    service._shutdown_retriever_pool()


@pytest.mark.asyncio
async def test_retrievers_can_use_pool() -> None:
    """Verify retrievers can actually use the lazy-loaded pool."""
    # This is a simple integration test to verify the pool works
    # We don't need to test actual retrieval logic, just pool usage

    try:
        # Get pool and verify it works
        pool = service._get_retriever_pool()
        assert pool is not None

        # Submit a simple task to verify pool works
        future = pool.submit(lambda: "test")
        result = future.result(timeout=1.0)
        assert result == "test"

    finally:
        # Cleanup
        service._shutdown_retriever_pool()


def test_max_workers_constant() -> None:
    """Verify MAX_WORKERS is set to expected value."""
    assert service._MAX_WORKERS == 50, "MAX_WORKERS should be 50"


def test_shutdown_is_idempotent() -> None:
    """Calling shutdown multiple times should be safe."""
    # Create pool
    service._get_retriever_pool()

    # Shutdown multiple times
    service._shutdown_retriever_pool()
    service._shutdown_retriever_pool()
    service._shutdown_retriever_pool()

    # Should not raise any errors
    assert service._retriever_pool is None
