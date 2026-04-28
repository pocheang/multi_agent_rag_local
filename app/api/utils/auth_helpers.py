"""
Authentication helper functions for the Multi-Agent Local RAG API.
"""
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import get_settings
from app.services.auth_db import AuthDBService

settings = get_settings()
auth_service = AuthDBService()


def _auth_cookie_name() -> str:
    """Get the authentication cookie name from settings."""
    value = str(getattr(settings, "auth_cookie_name", "auth_token") or "auth_token").strip()
    return value or "auth_token"


def _auth_cookie_samesite() -> str:
    """Get the SameSite policy for auth cookies."""
    raw = str(getattr(settings, "auth_cookie_samesite", "lax") or "lax").strip().lower()
    if raw not in {"lax", "strict", "none"}:
        return "lax"
    if raw == "none" and not bool(getattr(settings, "auth_cookie_secure", False)):
        return "lax"
    return raw


def _resolve_auth_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> tuple[str | None, str | None]:
    """Resolve authentication token from bearer header or cookie."""
    if credentials and credentials.credentials:
        token = str(credentials.credentials).strip() or None
        return token, ("bearer" if token else None)
    cookie_value = str(request.cookies.get(_auth_cookie_name(), "") or "").strip()
    token = cookie_value or None
    return token, ("cookie" if token else None)


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set authentication cookie on response."""
    ttl_hours = int(getattr(settings, "auth_token_ttl_hours", 24) or 24)
    max_age = max(300, ttl_hours * 3600)
    response.set_cookie(
        key=_auth_cookie_name(),
        value=token,
        max_age=max_age,
        httponly=True,
        secure=bool(getattr(settings, "auth_cookie_secure", False)),
        samesite=_auth_cookie_samesite(),
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    """Clear authentication cookie from response."""
    response.delete_cookie(
        key=_auth_cookie_name(),
        path="/",
    )


def _request_origin(request: Request) -> str | None:
    """Extract origin from request headers."""
    origin = str(request.headers.get("origin", "") or "").strip()
    if origin:
        return origin
    referer = str(request.headers.get("referer", "") or "").strip()
    if not referer:
        return None
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _origin_is_allowed(request: Request, origin: str | None) -> bool:
    """Check if origin is allowed for CORS."""
    if not origin:
        return False
    candidate = origin.strip().rstrip("/").lower()
    if not candidate:
        return False
    allowed: set[str] = set()
    for item in settings.cors_origins:
        value = str(item or "").strip().rstrip("/").lower()
        if value:
            allowed.add(value)
    req_origin = str(request.base_url).strip().rstrip("/").lower()
    if req_origin:
        allowed.add(req_origin)
    return candidate in allowed


def _enforce_cookie_csrf(request: Request, token_source: str | None) -> None:
    """Enforce CSRF protection for cookie-based authentication."""
    if token_source != "cookie":
        return
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    if _origin_is_allowed(request, _request_origin(request)):
        return
    raise HTTPException(status_code=403, detail="csrf validation failed")


def _client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    ip, _ua = _request_meta(request)
    return ip or "unknown"


def _request_meta(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP and user agent from request."""
    return request.client.host if request.client else None, request.headers.get("user-agent")


def _audit(
    request: Request,
    action: str,
    resource_type: str,
    result: str,
    user: dict[str, Any] | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
) -> None:
    """Add an audit log entry."""
    ip, user_agent = _request_meta(request)
    auth_service.add_audit_log(
        action=action,
        resource_type=resource_type,
        result=result,
        actor_user_id=user.get("user_id") if user else None,
        actor_role=user.get("role") if user else None,
        resource_id=resource_id,
        ip=ip,
        user_agent=user_agent,
        detail=detail,
    )
