"""
P0 Security Fixes Test Suite

Tests for critical cache security vulnerabilities:
- P0-1: User cache isolation
- P0-2: Concurrent race conditions
- P0-3: Redis connection pool
"""

import asyncio
import hashlib
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.runtime.query_result_cache import QueryResultCache


class TestP0_UserCacheIsolation:
    """Test P0-1: User cache isolation fixes"""

    @pytest.fixture
    def cache(self):
        """Create cache instance for testing"""
        return QueryResultCache(
            backend="memory",
            ttl_seconds=60,
            max_items=100,
            session_ttl_seconds=60,
        )

    def test_get_without_user_id_rejected(self, cache):
        """Test that cache access without user_id is rejected"""
        # Set cache with user_id
        cache.set("test_key", {"data": "secret"}, user_id="user_a")

        # Try to get without user_id - should be rejected
        result = cache.get("test_key", user_id=None)
        assert result is None, "Access without user_id should be rejected"

    def test_set_without_user_id_rejected(self, cache):
        """Test that cache set without user_id is rejected"""
        # Try to set without user_id - should be rejected
        cache.set("test_key", {"data": "secret"}, user_id=None)

        # Verify nothing was cached
        result = cache.get("test_key", user_id="user_a")
        assert result is None, "Set without user_id should not cache anything"

    def test_cross_user_access_blocked(self, cache):
        """Test that users cannot access each other's cache"""
        # User A sets cache
        cache.set("test_key", {"data": "secret_a"}, user_id="user_a")

        # User B should not access User A's cache
        result_b = cache.get("test_key", user_id="user_b")
        assert result_b is None, "User B should not access User A's cache"

        # User A should access their own cache
        result_a = cache.get("test_key", user_id="user_a")
        assert result_a is not None, "User A should access their own cache"
        assert result_a["data"] == "secret_a"

    def test_session_cache_isolation(self, cache):
        """Test session cache respects user isolation"""
        # User A sets cache with session
        cache.set("test_key", {"data": "secret_a"}, session_id="session1", user_id="user_a")

        # User B with same session should not access User A's cache
        result = cache.get("test_key", session_id="session1", user_id="user_b")
        assert result is None, "User B should not access User A's session cache"

        # User A should access their own session cache
        result = cache.get("test_key", session_id="session1", user_id="user_a")
        assert result is not None
        assert result["data"] == "secret_a"

    @patch('app.services.runtime.query_result_cache._get_redis_client')
    def test_redis_cache_isolation(self, mock_redis, cache):
        """Test Redis cache includes user_id in key"""
        # Mock Redis client
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        # Create cache with Redis backend
        cache._backend = "redis"

        # Set cache
        cache.set("test_key", {"data": "secret"}, user_id="user_a")

        # Verify Redis key includes user_id
        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args
        redis_key = call_args[0][0]
        assert redis_key.startswith("qcache:user_a:"), f"Redis key should include user_id: {redis_key}"

    @patch('app.services.runtime.query_result_cache._get_redis_client')
    def test_poisoned_cache_detection(self, mock_redis, cache):
        """Test detection and removal of poisoned cache entries"""
        # Mock Redis client
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        # Create cache with Redis backend
        cache._backend = "redis"

        # Simulate poisoned cache: Redis returns data with wrong user_id
        poisoned_data = json.dumps({"data": "stolen", "user_id": "attacker"})
        mock_client.get.return_value = poisoned_data

        # User A tries to access cache
        result = cache.get("test_key", user_id="user_a")

        # Should detect poisoning and return None
        assert result is None, "Poisoned cache should be detected"

        # Should delete the poisoned cache
        mock_client.delete.assert_called_once()

    def test_user_id_included_in_cache_value(self, cache):
        """Test that user_id is always included in cached value"""
        # Set cache
        cache.set("test_key", {"data": "value"}, user_id="user_a")

        # Get and verify user_id is in the cached value
        result = cache.get("test_key", user_id="user_a")
        assert result is not None
        assert result.get("user_id") == "user_a", "user_id should be in cached value"


class TestP0_RaceConditions:
    """Test P0-2: Concurrent race condition fixes"""

    @pytest.fixture
    def cache(self):
        """Create cache instance for testing"""
        return QueryResultCache(
            backend="memory",
            ttl_seconds=60,
            max_items=100,
            session_ttl_seconds=60,
        )

    def test_concurrent_inflight_marking_memory(self, cache):
        """Test that only one thread can mark inflight (memory backend)"""
        results = []

        def mark_worker():
            result = cache.mark_inflight("test_key", user_id="user_test")
            results.append(result)

        # Create 100 threads trying to mark the same key
        import threading
        threads = [threading.Thread(target=mark_worker) for _ in range(100)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Only one should succeed
        assert sum(results) == 1, f"Expected 1 success, got {sum(results)}"

        # Cleanup
        cache.clear_inflight("test_key")

    @patch('app.services.runtime.query_result_cache._get_redis_client')
    def test_concurrent_inflight_marking_redis(self, mock_redis, cache):
        """Test that only one thread can mark inflight (Redis backend)"""
        # Mock Redis client
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        # First call succeeds, subsequent calls fail (simulating Redis NX)
        call_count = 0
        def redis_set_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return call_count == 1  # Only first call succeeds

        mock_client.set.side_effect = redis_set_side_effect

        # Create cache with Redis backend
        cache._backend = "redis"

        results = []

        def mark_worker():
            result = cache.mark_inflight("test_key", user_id="user_test")
            results.append(result)

        # Create 10 threads
        import threading
        threads = [threading.Thread(target=mark_worker) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Only one should succeed
        assert sum(results) == 1, f"Expected 1 success, got {sum(results)}"

    def test_inflight_expiration(self, cache):
        """Test that inflight marks expire properly"""
        # Mark as inflight
        assert cache.mark_inflight("test_key") is True

        # Should be inflight
        assert cache.is_inflight("test_key") is True

        # Manually expire by modifying timestamp
        cache._inflight["test_key"] = time.time() - cache._ttl_seconds - 1

        # Try to mark again - should succeed after expiration
        assert cache.mark_inflight("test_key") is True

    def test_atomic_check_and_set(self, cache):
        """Test that check-and-set is atomic"""
        # This test verifies the fix works by ensuring the lock is held
        # during the entire check-and-set operation

        # Mark as inflight
        result1 = cache.mark_inflight("test_key")
        assert result1 is True

        # Immediate second attempt should fail
        result2 = cache.mark_inflight("test_key")
        assert result2 is False

        # Clear and try again
        cache.clear_inflight("test_key")
        result3 = cache.mark_inflight("test_key")
        assert result3 is True


class TestP0_RedisConnectionPool:
    """Test P0-3: Redis connection pool fixes"""

    @patch('app.services.runtime.query_result_cache.redis')
    def test_redis_timeout_configuration(self, mock_redis_module):
        """Test that Redis timeouts are properly configured"""
        from app.services.runtime.query_result_cache import _get_redis_client

        # Mock Redis
        mock_client = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.ping.return_value = True

        # Get Redis client
        client = _get_redis_client()

        # Verify from_url was called with correct timeouts
        mock_redis_module.from_url.assert_called_once()
        call_kwargs = mock_redis_module.from_url.call_args[1]

        assert call_kwargs['socket_connect_timeout'] == 2.0, "Connect timeout should be 2s"
        assert call_kwargs['socket_timeout'] == 2.0, "Socket timeout should be 2s"
        assert call_kwargs['retry_on_timeout'] is True, "Retry should be enabled"
        assert call_kwargs['socket_keepalive'] is True, "Keepalive should be enabled"

    @patch('app.services.runtime.query_result_cache.redis')
    def test_redis_connection_cleanup_on_error(self, mock_redis_module):
        """Test that Redis connections are cleaned up on error"""
        from app.services.runtime.query_result_cache import _get_redis_client, _REDIS_CLIENT

        # Mock Redis to raise error
        mock_redis_module.from_url.side_effect = Exception("Connection failed")

        # Try to get client - should handle error
        client = _get_redis_client()

        # Should return None on error
        assert client is None

    @patch('app.services.runtime.query_result_cache._get_redis_client')
    def test_redis_fallback_to_memory(self, mock_redis):
        """Test that cache falls back to memory when Redis is unavailable"""
        # Redis unavailable
        mock_redis.return_value = None

        cache = QueryResultCache(
            backend="redis",  # Request Redis
            ttl_seconds=60,
            max_items=100,
            session_ttl_seconds=60,
        )

        # Should fallback to memory
        assert cache._effective_backend() == "memory"

        # Should still work with memory backend
        cache.set("test_key", {"data": "value"}, user_id="user_a")
        result = cache.get("test_key", user_id="user_a")
        assert result is not None
        assert result["data"] == "value"

    def test_connection_pool_configuration(self):
        """Test that connection pool is properly configured"""
        # This is tested via the timeout configuration test above
        pass


class TestIntegration:
    """Integration tests for all P0 fixes"""

    @pytest.fixture
    def cache(self):
        """Create cache instance for testing"""
        return QueryResultCache(
            backend="memory",
            ttl_seconds=60,
            max_items=100,
            session_ttl_seconds=60,
        )

    def test_full_workflow_with_security(self, cache):
        """Test complete workflow with all security fixes"""
        # User A queries
        key = QueryResultCache.build_key(
            user_id="user_a",
            session_id="session1",
            question="What is Python?",
            use_web_fallback=False,
            use_reasoning=False,
            retrieval_strategy="hybrid",
            agent_class_hint="rag",
        )

        # Mark as inflight
        assert cache.mark_inflight(key, user_id="user_a") is True

        # Second request should be blocked
        assert cache.mark_inflight(key, user_id="user_a") is False

        # Cache result
        cache.set(key, {"answer": "Python is a programming language"}, user_id="user_a")

        # Clear inflight
        cache.clear_inflight(key)

        # User A should access cache
        result_a = cache.get(key, user_id="user_a")
        assert result_a is not None
        assert result_a["answer"] == "Python is a programming language"

        # User B should NOT access User A's cache
        result_b = cache.get(key, user_id="user_b")
        assert result_b is None

        # Without user_id should be rejected
        result_none = cache.get(key, user_id=None)
        assert result_none is None

    def test_concurrent_users_isolated(self, cache):
        """Test that concurrent users are completely isolated"""
        import threading

        results = {"user_a": [], "user_b": []}

        def user_workflow(user_id, data):
            key = f"key_{user_id}"
            cache.set(key, {"data": data}, user_id=user_id)
            result = cache.get(key, user_id=user_id)
            results[user_id].append(result)

            # Try to access other user's cache
            other_user = "user_b" if user_id == "user_a" else "user_a"
            other_key = f"key_{other_user}"
            cross_result = cache.get(other_key, user_id=user_id)
            results[user_id].append(cross_result)

        # Create threads for two users
        t1 = threading.Thread(target=user_workflow, args=("user_a", "secret_a"))
        t2 = threading.Thread(target=user_workflow, args=("user_b", "secret_b"))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Each user should access their own cache
        assert results["user_a"][0] is not None
        assert results["user_a"][0]["data"] == "secret_a"
        assert results["user_b"][0] is not None
        assert results["user_b"][0]["data"] == "secret_b"

        # Neither should access the other's cache
        assert results["user_a"][1] is None  # user_a cannot access user_b's cache
        assert results["user_b"][1] is None  # user_b cannot access user_a's cache


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
