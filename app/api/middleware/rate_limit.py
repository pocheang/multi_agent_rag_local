"""
Rate limiting middleware for sensitive endpoints.

Now enhanced with Redis support for distributed deployments.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.middleware.csrf import RATE_LIMIT_CONFIG, get_client_ip
from app.services.auth.redis_rate_limit import get_rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Enhanced Rate Limiting Middleware with Redis support

    Limits requests to sensitive endpoints based on client IP.
    Supports distributed rate limiting via Redis.
    """

    def __init__(self, app, redis_url=None):
        super().__init__(app)
        self.rate_limiter = get_rate_limiter(redis_url)

    async def dispatch(self, request: Request, call_next):
        """Check rate limits for sensitive endpoints."""

        # Check if this path needs rate limiting
        endpoint_config = None
        for config in RATE_LIMIT_CONFIG.values():
            if request.url.path == config["path"]:
                endpoint_config = config
                break

        # No rate limiting for this endpoint
        if not endpoint_config:
            return await call_next(request)

        # Get client IP
        client_ip = get_client_ip(request)
        if client_ip == "unknown":
            # Can't rate limit without IP, allow but log
            return await call_next(request)

        # Rate limit key
        rate_key = f"rate_limit:{client_ip}:{request.url.path}"

        # Check rate limit
        is_allowed, retry_after = self.rate_limiter.check_rate_limit(
            rate_key, endpoint_config["max_requests"], endpoint_config["window_seconds"]
        )

        if not is_allowed:
            # Rate limit exceeded
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Too many requests. Try again in {retry_after} seconds.",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        # Proceed with request
        return await call_next(request)
