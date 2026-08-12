"""Authentication dependencies used by API routes."""

import os
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.transport.errors import forbidden
from app.services.auth.auth_service import AuthDBService

auth_scheme = HTTPBearer(auto_error=False)
auth_service = AuthDBService()


def _resolve_pytest_header_user(request: Request) -> dict[str, Any] | None:
    """Allow lightweight test-user injection only during pytest runs or TestClient calls."""
    is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
    client_host = getattr(getattr(request, "client", None), "host", "")
    is_testclient = client_host == "testclient"
    if not is_pytest and not is_testclient:
        return None

    username = str(request.headers.get("X-Test-User", "") or "").strip()
    role = str(request.headers.get("X-Test-Role", "viewer") or "viewer").strip().lower()
    user_id = str(request.headers.get("X-Test-User-Id", "") or "").strip()
    if not username and not user_id:
        return None

    return {
        "user_id": user_id or username or "pytest-user",
        "username": username or user_id or "pytest-user",
        "role": role or "viewer",
        "status": "active",
        "auth_source": "test-header",
    }


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _resolve_authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> tuple[dict[str, Any], str, str | None]:
    from app.api.utils.auth_helpers import _enforce_cookie_csrf, _resolve_auth_token

    pytest_user = _resolve_pytest_header_user(request)
    if pytest_user is not None:
        return pytest_user, "pytest-header-auth", "test-header"

    token, token_source = _resolve_auth_token(request, credentials)
    if not token:
        raise _unauthorized("Authentication required")

    _enforce_cookie_csrf(request, token_source)
    try:
        user = auth_service.get_user_by_token(token, include_disabled=True)
    except TypeError:
        user = auth_service.get_user_by_token(token)
    if not user:
        raise _unauthorized("Invalid or expired token")

    auth_service.touch_session(token)
    return user, token, token_source


def _require_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> dict[str, Any]:
    """Require a valid authenticated user with active status."""
    from app.api.utils.auth_helpers import _audit

    user, _token, _source = _resolve_authenticated_user(request, credentials)

    user_status = str(user.get("status", "")).lower()
    if user_status != "active":
        _audit(
            request,
            action="auth.access_denied",
            resource_type="session",
            result="blocked_inactive_user",
            user=user,
            detail=f"status={user_status}",
        )
        raise forbidden("account is not active")

    return user


def _require_user_and_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> tuple[dict[str, Any], str]:
    """Require a valid authenticated user and return user + token."""
    user, token, _source = _resolve_authenticated_user(request, credentials)
    return user, token


def _require_permission(
    user: dict[str, Any],
    permission: str,
    request: Request,
    resource_type: str,
    resource_id: str | None = None,
) -> None:
    """
    Check user permission using RBAC system with audit logging.

    Args:
        user: User information
        permission: Permission to check (e.g., "admin:user_manage", "document:read")
        request: FastAPI request object
        resource_type: Type of resource being accessed
        resource_id: Optional resource identifier

    Raises:
        HTTPException: If user lacks the required permission
    """
    from app.api.utils.auth_helpers import _audit
    from app.services.security.rbac import can

    if not can(permission, user):
        _audit(
            request,
            action="auth.permission_denied",
            resource_type=resource_type,
            result="denied",
            user=user,
            resource_id=resource_id,
            detail=f"permission={permission}; role={user.get('role', 'unknown')}",
        )
        raise forbidden(f"Permission denied: {permission}")



def require_admin(
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
) -> dict[str, Any]:
    """Require an active administrator for standalone admin routers."""
    _require_permission(user, "admin:audit_read", request, "admin")
    return user


