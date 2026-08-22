"""Common error response helpers for FastAPI routes."""

from fastapi import HTTPException


def not_found(resource: str = "Resource") -> HTTPException:
    """Return a 404 Not Found error."""
    return HTTPException(status_code=404, detail=f"{resource} not found")


def bad_request(detail: str) -> HTTPException:
    """Return a 400 Bad Request error."""
    return HTTPException(status_code=400, detail=detail)


def unauthorized(detail: str = "Unauthorized") -> HTTPException:
    """Return a 401 Unauthorized error."""
    return HTTPException(status_code=401, detail=detail)


def forbidden(detail: str = "Forbidden") -> HTTPException:
    """Return a 403 Forbidden error (alias for unauthorized)."""
    return HTTPException(status_code=403, detail=detail)


def internal_error(detail: str = "Internal server error") -> HTTPException:
    """Return a 500 Internal Server Error."""
    return HTTPException(status_code=500, detail=detail)


def conflict(detail: str) -> HTTPException:
    """Return a 409 Conflict error."""
    return HTTPException(status_code=409, detail=detail)


def accepted(detail: str = "Request accepted for processing", headers: dict[str, str] | None = None) -> HTTPException:
    """Return a 202 Accepted response (for async operations)."""
    return HTTPException(status_code=202, detail=detail, headers=headers or {})


def rate_limited(detail: str = "Too many requests, retry later") -> HTTPException:
    """Return a 429 Rate Limited error."""
    return HTTPException(status_code=429, detail=detail)


def not_implemented(detail: str = "Not implemented") -> HTTPException:
    """Return a 501 Not Implemented error."""
    return HTTPException(status_code=501, detail=detail)


def payload_too_large(detail: str = "Payload too large") -> HTTPException:
    """Return a 413 Payload Too Large error."""
    return HTTPException(status_code=413, detail=detail)
