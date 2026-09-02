"""Common error response helpers for FastAPI routes.

The helpers below *raise* the errors; `error_responses` *declares* them, so the
OpenAPI document says what a route can return. Those were separate facts until
2026-09-02: a route raising `conflict(...)` documented only its 200, and the
generated document told a client the call could not fail -- `python:S8415`.

One place for the descriptions, because fifty-three route decorators writing
their own would be fifty-three chances to describe the same 400 differently.
"""

from typing import Any

from fastapi import HTTPException

_ERROR_DESCRIPTIONS: dict[int, str] = {
    400: "The request was rejected by validation.",
    401: "Authentication is required.",
    403: "The caller lacks the required permission.",
    404: "No such resource, or none visible to this caller.",
    409: "The request conflicts with the current state of the resource.",
    413: "The payload exceeds the configured limit.",
    422: "The request body did not match the expected schema.",
    429: "Rate limit exceeded; retry after the interval in the Retry-After header.",
    500: "The request failed for a reason the caller cannot act on.",
    501: "Not implemented.",
    503: "A dependency this endpoint needs is unavailable; retry later.",
}


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Declare the failures a route can return, for the OpenAPI document.

    404 and 403 deliberately describe *visibility* rather than existence: the
    document should not promise a caller that a resource it cannot see exists.
    """

    return {code: {"description": _ERROR_DESCRIPTIONS[code]} for code in sorted(set(status_codes))}


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


def service_unavailable(detail: str = "Service temporarily overloaded, retry later") -> HTTPException:
    """Return a 503 Service Unavailable error."""
    return HTTPException(status_code=503, detail=detail)


def not_implemented(detail: str = "Not implemented") -> HTTPException:
    """Return a 501 Not Implemented error."""
    return HTTPException(status_code=501, detail=detail)


def payload_too_large(detail: str = "Payload too large") -> HTTPException:
    """Return a 413 Payload Too Large error."""
    return HTTPException(status_code=413, detail=detail)
