"""Rate limiting middleware for sensitive endpoints.

Backed by Redis where one is configured, and by an in-process window otherwise.

Rules match on method and path *pattern*, not on an exact path. They used to be
exact, which was enough while the only protected routes were `/auth/login` and
its two siblings -- and was why the admin routes could not be added here, since
every one of them carries a `{user_id}`.

That mattered because the admin routes believed they were rate limited. Eight of
them carried `@limiter.limit(...)` from a slowapi wrapper in
`app/services/security/admin_rate_limit.py`, and slowapi was never a dependency
of this project: not in pyproject, not in the locks, not installed. So
`SLOWAPI_AVAILABLE` was always False, the wrapper always returned a no-op
decorator, and creating an administrator, resetting a password and resetting an
approval token were all unlimited. Nor was a limiter ever registered on the app,
so installing slowapi would not have fixed it either. That module is gone and
its limits are rules here, where the middleware that runs them is registered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.auth.redis_rate_limit import get_rate_limiter

HOUR = 3600
MINUTE = 60


@dataclass(frozen=True)
class RateLimitRule:
    """One limit, keyed per client IP.

    `name` is what appears in the rate-limit key, so two rules cannot share a
    bucket by accident -- keying on the request path would have given every
    `{user_id}` its own, which is not a limit on the operation at all.
    """

    name: str
    methods: frozenset[str]
    pattern: re.Pattern[str]
    max_requests: int
    window_seconds: int

    def matches(self, method: str, path: str) -> bool:
        return method in self.methods and bool(self.pattern.fullmatch(path))


def _rule(name: str, methods: str, path: str, max_requests: int, window_seconds: int) -> RateLimitRule:
    return RateLimitRule(
        name=name,
        methods=frozenset(methods.split()),
        pattern=re.compile(path),
        max_requests=max_requests,
        window_seconds=window_seconds,
    )


_ID = r"[^/]+"

RATE_LIMIT_RULES: tuple[RateLimitRule, ...] = (
    # Unauthenticated, and the reason this middleware exists.
    _rule("login", "POST", r"/auth/login", 5, MINUTE),
    _rule("register", "POST", r"/auth/register", 3, 5 * MINUTE),
    _rule("change_password", "POST", r"/auth/change-password", 3, 5 * MINUTE),
    # Administrative, and unlimited until 2026-09-02 -- see the module docstring.
    # The numbers are the ones the dead decorators carried.
    _rule("admin_create", "POST", r"/admin/users/create-admin", 1, HOUR),
    _rule("approval_token_reset", "POST", rf"/admin/users/{_ID}/reset-approval-token", 3, HOUR),
    _rule("admin_password_reset", "POST", rf"/admin/users/{_ID}/reset-password", 5, HOUR),
    _rule("role_update", "PATCH", rf"/admin/users/{_ID}/role", 10, HOUR),
    _rule("status_update", "PATCH", rf"/admin/users/{_ID}/status", 20, HOUR),
    _rule("credit_add", "POST", rf"/admin/users/{_ID}/credits/add", 30, HOUR),
    _rule("list_users", "GET", r"/admin/users", 100, MINUTE),
    _rule("audit_logs", "GET", r"/admin/audit-logs", 50, MINUTE),
)


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    # Check for proxy headers first
    forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for

    real_ip = request.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip

    # Fallback to direct connection IP
    if request.client and request.client.host:
        return request.client.host

    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limit requests to sensitive endpoints, per client IP."""

    def __init__(self, app, redis_url=None):
        super().__init__(app)
        self.rate_limiter = get_rate_limiter(redis_url)

    async def dispatch(self, request: Request, call_next):
        """Check rate limits for sensitive endpoints."""

        path = request.url.path
        rule = next((r for r in RATE_LIMIT_RULES if r.matches(request.method, path)), None)
        if rule is None:
            return await call_next(request)

        client_ip = get_client_ip(request)
        if client_ip == "unknown":
            # Can't rate limit without IP, allow but log
            return await call_next(request)

        rate_key = f"rate_limit:{client_ip}:{rule.name}"

        is_allowed, retry_after = await self.rate_limiter.check_rate_limit_async(
            rate_key, rule.max_requests, rule.window_seconds
        )

        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Too many requests. Try again in {retry_after} seconds.",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
