"""
Redis-backed Rate Limiting

Provides distributed rate limiting using Redis with fallback to in-memory storage.
"""

import time

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisRateLimiter:
    """
    Redis-backed rate limiter with in-memory fallback.

    Supports:
    - Distributed rate limiting across multiple instances
    - Sliding window algorithm
    - Automatic key expiration
    """

    def __init__(self, redis_url: str | None = None):
        """Initialize rate limiter."""
        self.redis_client = None
        self.use_redis = False
        self._memory_store = {}  # Fallback

        # Try to connect to Redis
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=False)
                self.redis_client.ping()
                self.use_redis = True
                print(f"INFO: RedisRateLimiter: Using Redis at {redis_url}")
            except Exception as e:
                print(f"WARNING: RedisRateLimiter: Redis unavailable ({e}), using in-memory storage")
                self.redis_client = None

        if not self.use_redis:
            print("INFO: RedisRateLimiter: Using in-memory storage (not recommended for production)")

    def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int | None]:
        """
        Check if rate limit is exceeded.

        Returns:
            tuple[is_allowed, retry_after_seconds]
        """
        if self.use_redis and self.redis_client:
            return self._check_redis(key, max_requests, window_seconds)
        else:
            return self._check_memory(key, max_requests, window_seconds)

    def _check_redis(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int | None]:
        """Redis-based sliding window rate limiting."""
        try:
            current_time = time.time()
            window_start = current_time - window_seconds

            pipe = self.redis_client.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(current_time): current_time})

            # Set expiration
            pipe.expire(key, window_seconds + 1)

            results = pipe.execute()
            current_count = results[1]  # Result of zcard

            if current_count >= max_requests:
                # Get oldest request in window to calculate retry_after
                oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_time = oldest[0][1]
                    retry_after = int(window_seconds - (current_time - oldest_time)) + 1
                    return False, retry_after
                return False, window_seconds

            return True, None

        except Exception as e:
            print(f"WARNING: Redis rate limit check failed: {e}, falling back to memory")
            self.use_redis = False
            return self._check_memory(key, max_requests, window_seconds)

    def _check_memory(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int | None]:
        """In-memory fallback rate limiting."""
        current_time = time.time()

        # Clean up old entries periodically
        if len(self._memory_store) > 10000:
            cutoff = current_time - 3600
            self._memory_store = {k: v for k, v in self._memory_store.items() if v["window_start"] > cutoff}

        # Get or create entry
        if key not in self._memory_store:
            self._memory_store[key] = {"count": 1, "window_start": current_time}
            return True, None

        entry = self._memory_store[key]

        # Check if window has expired
        if current_time - entry["window_start"] > window_seconds:
            # Reset window
            self._memory_store[key] = {"count": 1, "window_start": current_time}
            return True, None

        # Within window, check limit
        if entry["count"] >= max_requests:
            retry_after = int(window_seconds - (current_time - entry["window_start"])) + 1
            return False, retry_after

        # Increment count
        entry["count"] += 1
        return True, None

    def reset(self, key: str):
        """Reset rate limit for a key."""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception:
                pass
        else:
            self._memory_store.pop(key, None)


# Singleton instance
_rate_limiter: RedisRateLimiter | None = None


def get_rate_limiter(redis_url: str | None = None) -> RedisRateLimiter:
    """Get or create rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RedisRateLimiter(redis_url)
    return _rate_limiter
