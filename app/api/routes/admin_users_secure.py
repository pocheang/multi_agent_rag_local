"""Admin user management routes with security enhancements.

This module provides secure admin operations with:
- Self-modification prevention
- Approval token single-use enforcement
- Rate limiting
- Comprehensive audit logging
- Input validation
"""
import hashlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import (
    auth_service,
    _audit,
    _require_user,
    _require_permission,
    settings,
)
from app.core.schemas import (
    AdminCreateAdminRequest,
    AdminResetApprovalTokenRequest,
    AdminResetPasswordRequest,
    AdminRoleUpdateRequest,
    AdminStatusUpdateRequest,
    AdminUserClassificationUpdateRequest,
    AdminUserSummary,
    AuditLogEntry,
)
from app.services.log_buffer import list_captured_logs
from app.services.admin_security import (
    check_self_modification,
    check_admin_role_change,
    validate_ticket_id,
    validate_reason,
    validate_approval_token_length,
)
from app.services.admin_token_tracker import validate_admin_approval_token, get_token_tracker
from app.services.admin_rate_limit import get_limiter, get_rate_limit
from app.api.utils.admin_helpers import handle_service_exception

router = APIRouter(prefix="/admin", tags=["admin"])
limiter = get_limiter()


@router.get("/users", response_model=list[AdminUserSummary])
@limiter.limit(get_rate_limit("list_users"))
def admin_list_users(request: Request, user: dict[str, Any] = Depends(_require_user)):
    """List all users (admin only)."""
    _require_permission(user, "admin:user_manage", request, "admin")
    rows = auth_service.list_users()
    return [AdminUserSummary(**x) for x in rows]


@router.get("")
def admin_page(request: Request, user: dict[str, Any] = Depends(_require_user)):
    """Admin portal landing page."""
    _require_permission(user, "admin:user_manage", request, "admin")
    return {"ok": True, "message": "admin portal"}


@router.patch("/users/{user_id}/role", response_model=AdminUserSummary)
@limiter.limit(get_rate_limit("role_update"))
def admin_update_user_role(
    user_id: str,
    req: AdminRoleUpdateRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user)
):
    """Update user role with security checks."""
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)

    # Security: Prevent self-modification
    check_self_modification(user_id, user, "admin.user.role_update", _audit, request)

    # Security: Prevent direct admin promotion
    check_admin_role_change(req.role)

    try:
        row = auth_service.update_user_role(user_id=user_id, role=req.role)
    except Exception as e:
        handle_service_exception(e, _audit, request, "admin.user.role_update", user, user_id)

    if row is None:
        raise HTTPException(status_code=404, detail="user not found")

    _audit(
        request,
        action="admin.user.role_update",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=f"role={row['role']}",
    )
    return AdminUserSummary(**row)


@router.post("/users/create-admin", response_model=AdminUserSummary)
@limiter.limit(get_rate_limit("admin_create"))
def admin_create_user_as_admin(
    req: AdminCreateAdminRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user)
):
    """Create new admin user with approval token validation."""
    _require_permission(user, "admin:user_manage", request, "admin")

    approval_token = req.approval_token or ""
    actor_user_id = str(user.get("user_id", ""))

    # Security: Validate approval token (single-use, timing-attack resistant)
    configured_hash = str(
        getattr(settings, "admin_create_approval_token_hash", "") or ""
    ).strip().lower()

    tracker = get_token_tracker()
    token_ok, token_mode = validate_admin_approval_token(
        approval_token,
        configured_hash,
        actor_user_id,
        tracker
    )

    if not token_ok:
        _audit(
            request,
            action="admin.user.create_admin",
            resource_type="user",
            result="failed",
            user=user,
            detail=f"approval_failed; mode={token_mode}"
        )
        raise HTTPException(status_code=403, detail="unauthorized")

    ticket_id = (req.ticket_id or "").strip()
    reason = (req.reason or "").strip()
    new_admin_approval_token = (req.new_admin_approval_token or "").strip()

    # Security: Enhanced input validation
    validate_ticket_id(ticket_id)
    validate_reason(reason)
    validate_approval_token_length(new_admin_approval_token)

    new_admin_approval_hash = hashlib.sha256(new_admin_approval_token.encode("utf-8")).hexdigest()

    try:
        row = auth_service.create_user_with_role(
            username=req.username,
            password=req.password,
            role="admin",
            created_by_user_id=actor_user_id,
            created_by_username=str(user.get("username", "")),
            admin_ticket_id=ticket_id,
            admin_approval_token_hash=new_admin_approval_hash,
        )
    except Exception as e:
        handle_service_exception(e, _audit, request, "admin.user.create_admin", user)

    _audit(
        request,
        action="admin.user.create_admin",
        resource_type="user",
        result="success",
        user=user,
        resource_id=row["user_id"],
        detail=f"username={row['username']}; mode={token_mode}; ticket={ticket_id}; reason={reason}",
    )
    return AdminUserSummary(**row)


@router.post("/users/{user_id}/reset-approval-token", response_model=AdminUserSummary)
@limiter.limit(get_rate_limit("approval_token_reset"))
def admin_reset_user_approval_token(
    user_id: str,
    req: AdminResetApprovalTokenRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """Reset admin approval token with security checks."""
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)

    # Security: Prevent self-modification
    check_self_modification(user_id, user, "admin.user.reset_approval_token", _audit, request)

    target = auth_service.get_user_profile(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    if str(target.get("role", "")).lower() != "admin":
        raise HTTPException(status_code=400, detail="target user is not admin")

    approval_token = req.approval_token or ""
    actor_user_id = str(user.get("user_id", ""))

    # Security: Validate approval token
    configured_hash = str(
        getattr(settings, "admin_create_approval_token_hash", "") or ""
    ).strip().lower()

    tracker = get_token_tracker()
    token_ok, token_mode = validate_admin_approval_token(
        approval_token,
        configured_hash,
        actor_user_id,
        tracker
    )

    if not token_ok:
        _audit(
            request,
            action="admin.user.reset_approval_token",
            resource_type="user",
            result="failed",
            user=user,
            resource_id=user_id,
            detail=f"approval_failed; mode={token_mode}"
        )
        raise HTTPException(status_code=403, detail="unauthorized")

    ticket_id = (req.ticket_id or "").strip()
    reason = (req.reason or "").strip()
    new_admin_approval_token = (req.new_admin_approval_token or "").strip()

    validate_ticket_id(ticket_id)
    validate_reason(reason)
    validate_approval_token_length(new_admin_approval_token)

    token_hash = hashlib.sha256(new_admin_approval_token.encode("utf-8")).hexdigest()
    row = auth_service.update_user_admin_approval_token(
        user_id=user_id,
        admin_approval_token_hash=token_hash,
        admin_ticket_id=ticket_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")

    _audit(
        request,
        action="admin.user.reset_approval_token",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=(
            f"target={target.get('username', '-')}; mode={token_mode}; ticket={ticket_id}; reason={reason}; "
            f"actor={user.get('username', '-')}"
        ),
    )
    return AdminUserSummary(**row)


@router.post("/users/{user_id}/reset-password", response_model=AdminUserSummary)
@limiter.limit(get_rate_limit("password_reset"))
def admin_reset_user_password(
    user_id: str,
    req: AdminResetPasswordRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """Reset user password with approval token validation."""
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)

    target = auth_service.get_user_profile(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    approval_token = req.approval_token or ""
    actor_user_id = str(user.get("user_id", ""))

    # Security: Validate approval token
    configured_hash = str(
        getattr(settings, "admin_create_approval_token_hash", "") or ""
    ).strip().lower()

    tracker = get_token_tracker()
    token_ok, token_mode = validate_admin_approval_token(
        approval_token,
        configured_hash,
        actor_user_id,
        tracker
    )

    if not token_ok:
        _audit(
            request,
            action="admin.user.reset_password",
            resource_type="user",
            result="failed",
            user=user,
            resource_id=user_id,
            detail=f"approval_failed; mode={token_mode}"
        )
        raise HTTPException(status_code=403, detail="unauthorized")

    ticket_id = (req.ticket_id or "").strip()
    reason = (req.reason or "").strip()
    new_password = req.new_password or ""

    validate_ticket_id(ticket_id)
    validate_reason(reason)

    try:
        row = auth_service.update_user_password(user_id=user_id, password=new_password)
    except Exception as e:
        handle_service_exception(e, _audit, request, "admin.user.reset_password", user, user_id)

    if row is None:
        raise HTTPException(status_code=404, detail="user not found")

    _audit(
        request,
        action="admin.user.reset_password",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=(
            f"target={target.get('username', '-')}; mode={token_mode}; ticket={ticket_id}; reason={reason}; "
            f"actor={user.get('username', '-')}"
        ),
    )
    return AdminUserSummary(**row)


@router.patch("/users/{user_id}/status", response_model=AdminUserSummary)
@limiter.limit(get_rate_limit("status_update"))
def admin_update_user_status(
    user_id: str,
    req: AdminStatusUpdateRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user)
):
    """Update user status with self-modification check."""
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)

    # Security: Prevent self-modification
    check_self_modification(user_id, user, "admin.user.status_update", _audit, request)

    try:
        row = auth_service.update_user_status(user_id=user_id, status=req.status)
    except Exception as e:
        handle_service_exception(e, _audit, request, "admin.user.status_update", user, user_id)

    if row is None:
        raise HTTPException(status_code=404, detail="user not found")

    _audit(
        request,
        action="admin.user.status_update",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=f"status={row['status']}",
    )
    return AdminUserSummary(**row)


@router.patch("/users/{user_id}/classification", response_model=AdminUserSummary)
def admin_update_user_classification(
    user_id: str,
    req: AdminUserClassificationUpdateRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """Update user classification with improved error handling."""
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)

    try:
        row = auth_service.update_user_classification(
            user_id=user_id,
            business_unit=req.business_unit,
            department=req.department,
            user_type=req.user_type,
            data_scope=req.data_scope,
        )
    except Exception as e:
        handle_service_exception(e, _audit, request, "admin.user.classification_update", user, user_id)

    if row is None:
        raise HTTPException(status_code=404, detail="user not found")

    _audit(
        request,
        action="admin.user.classification_update",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=(
            f"business_unit={row.get('business_unit') or '-'}; department={row.get('department') or '-'}; "
            f"user_type={row.get('user_type') or '-'}; data_scope={row.get('data_scope') or '-'}"
        ),
    )
    return AdminUserSummary(**row)


@router.get("/audit-logs", response_model=list[AuditLogEntry])
@limiter.limit(get_rate_limit("audit_logs"))
def admin_list_audit_logs(
    request: Request,
    limit: int = 200,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
    event_category: str | None = None,
    severity: str | None = None,
    result: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    """List audit logs with rate limiting."""
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = auth_service.list_audit_logs(
        limit=limit,
        actor_user_id=actor_user_id,
        action_keyword=action_keyword,
        event_category=event_category,
        severity=severity,
        result=result,
    )
    return [AuditLogEntry(**x) for x in rows]


@router.get("/system-logs")
def admin_system_logs(
    request: Request,
    limit: int = 200,
    level: str | None = None,
    logger: str | None = None,
    keyword: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    """Get system logs (admin only)."""
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = list_captured_logs(limit=limit, level=level, logger_keyword=logger, keyword=keyword)
    return {"items": rows, "count": len(rows)}
