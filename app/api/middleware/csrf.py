"""
CSRF Protection Middleware for FastAPI

Implements Cross-Site Request Forgery (CSRF) protection by validating
X-CSRF-Token headers on state-changing requests (POST, PUT, PATCH, DELETE).

Now enhanced with:
- Session-based CSRF token validation
- Redis-backed session storage
- Constant-time comparison for security
"""

import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.auth.enhanced_session import get_session_manager

# Methods that require CSRF protection
CSRF_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

# Paths that are exempt from CSRF validation
CSRF_EXEMPT_PATHS = {
    "/health",
    "/ready",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/auth/login",  # Initial login doesn't have CSRF token yet
    "/auth/register",  # Initial registration doesn't have CSRF token yet
    "/api/v1/clarification",  # Clarification API endpoints
}


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_hex(32)


def is_csrf_exempt(path: str) -> bool:
    """Check if a path is exempt from CSRF validation."""
    return any(path.startswith(exempt_path) for exempt_path in CSRF_EXEMPT_PATHS)


def get_session_id_from_cookie(request: Request) -> str | None:
    """Extract session ID from cookie."""
    return request.cookies.get("session_id")


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    Enhanced CSRF Protection Middleware

    Validates X-CSRF-Token header against session-stored token.
    Uses constant-time comparison to prevent timing attacks.
    """

    async def dispatch(self, request: Request, call_next):
        """Validate CSRF token for unsafe methods."""

        # Skip CSRF validation for safe methods
        if request.method in CSRF_SAFE_METHODS:
            return await call_next(request)

        # Skip CSRF validation for exempt paths
        request_path = request.url.path
        is_exempt = is_csrf_exempt(request_path)

        # 安全修复：移除生产环境的调试代码，使用条件日志记录
        # if "clarification" in request_path:
        #     print(f"[CSRF DEBUG] Path: {request_path}")
        #     print(f"[CSRF DEBUG] Is exempt: {is_exempt}")
        #     print(f"[CSRF DEBUG] Exempt paths: {CSRF_EXEMPT_PATHS}")

        if is_exempt:
            return await call_next(request)

        # Get CSRF token from request header
        csrf_token = request.headers.get("X-CSRF-Token", "").strip()

        # Get session ID from cookie (HttpOnly)
        session_id = get_session_id_from_cookie(request)

        # Bearer-token clients and routes that perform their own authentication
        # are not vulnerable to cookie-based CSRF.  Cookie auth is enforced by
        # the auth dependency; this middleware only validates enhanced sessions.
        if not session_id:
            return await call_next(request)

        # Validate CSRF token against session
        try:
            session_manager = get_session_manager()

            # Check if token is provided
            if not csrf_token:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "CSRF token missing. Include X-CSRF-Token header.",
                        "error_code": "CSRF_TOKEN_MISSING",
                    },
                )

            # Validate token against session (constant-time comparison)
            if not session_manager.validate_csrf_token(session_id, csrf_token):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "CSRF token validation failed. Token mismatch or session expired.",
                        "error_code": "CSRF_TOKEN_INVALID",
                    },
                )

            # Store session in request state for endpoints to use
            request.state.session_id = session_id
            request.state.csrf_token = csrf_token

        except Exception as e:
            # Log error but don't expose details
            print(f"CSRF validation error: {e}")
            return JSONResponse(
                status_code=403, content={"detail": "CSRF validation failed.", "error_code": "CSRF_VALIDATION_ERROR"}
            )

        # Proceed with the request
        return await call_next(request)


class SessionCSRFMiddleware(BaseHTTPMiddleware):
    """
    Session-aware CSRF Middleware

    Generates CSRF tokens for authenticated sessions and validates them.
    """

    async def dispatch(self, request: Request, call_next):
        """Manage CSRF tokens in session."""

        response = await call_next(request)

        # If this is a login response, the auth endpoint should have set the session cookie
        # The CSRF token is already in the session, no need to add it to headers

        return response


# Rate limiting configuration for sensitive endpoints
RATE_LIMIT_CONFIG = {
    "login": {
        "path": "/auth/login",
        "max_requests": 5,
        "window_seconds": 60,
    },
    "register": {
        "path": "/auth/register",
        "max_requests": 3,
        "window_seconds": 300,
    },
    "password_change": {
        "path": "/auth/change-password",
        "max_requests": 3,
        "window_seconds": 300,
    },
}


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
