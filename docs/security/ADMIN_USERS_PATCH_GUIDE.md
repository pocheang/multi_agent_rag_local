# admin_users.py 安全修复补丁

本文档说明了对 `app/api/routes/admin_users.py` 的关键安全修复。

## 修改概述

1. 添加自我修改检查
2. 使用新的令牌验证函数
3. 改进异常处理
4. 添加速率限制

## 需要导入的新模块

在文件顶部添加：

```python
from app.services.admin_security import (
    check_self_modification,
    check_admin_role_change,
    validate_ticket_id,
    validate_reason,
    validate_approval_token_length,
)
from app.services.admin_rate_limit import get_limiter, get_rate_limit
from app.api.utils.admin_helpers import (
    validate_and_check_approval_token,
    handle_service_exception,
)

# 初始化速率限制器
limiter = get_limiter()
```

## 修复 1: admin_update_user_role (Line 51-72)

**在函数开头添加自我修改检查**:

```python
@router.patch("/users/{user_id}/role", response_model=AdminUserSummary)
@limiter.limit(get_rate_limit("role_update"))
def admin_update_user_role(user_id: str, req: AdminRoleUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    
    # 添加自我修改检查
    check_self_modification(user_id, user, "admin.user.role_update", _audit, request)
    
    # 检查角色变更
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
```

## 修复 2: admin_create_user_as_admin (Line 75-134)

**使用新的令牌验证函数**:

```python
@router.post("/users/create-admin", response_model=AdminUserSummary)
@limiter.limit(get_rate_limit("admin_create"))
def admin_create_user_as_admin(req: AdminCreateAdminRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin")
    
    approval_token = req.approval_token or ""
    actor_user_id = str(user.get("user_id", ""))
    
    # 使用新的令牌验证函数（防止信息泄露和令牌重用）
    token_ok, token_mode = validate_and_check_approval_token(
        approval_token,
        actor_user_id,
        _audit,
        request,
        user,
        "admin.user.create_admin"
    )
    
    ticket_id = (req.ticket_id or "").strip()
    reason = (req.reason or "").strip()
    new_admin_approval_token = (req.new_admin_approval_token or "").strip()
    
    # 使用新的验证函数
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
```

## 修复 3: admin_reset_user_approval_token (Line 137-200)

**添加自我修改检查和新的令牌验证**:

```python
@router.post("/users/{user_id}/reset-approval-token", response_model=AdminUserSummary)
@limiter.limit(get_rate_limit("approval_token_reset"))
def admin_reset_user_approval_token(
    user_id: str,
    req: AdminResetApprovalTokenRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    
    # 添加自我修改检查
    check_self_modification(user_id, user, "admin.user.reset_approval_token", _audit, request)
    
    target = auth_service.get_user_profile(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    if str(target.get("role", "")).lower() != "admin":
        raise HTTPException(status_code=400, detail="target user is not admin")

    approval_token = req.approval_token or ""
    actor_user_id = str(user.get("user_id", ""))
    
    # 使用新的令牌验证函数
    token_ok, token_mode = validate_and_check_approval_token(
        approval_token,
        actor_user_id,
        _audit,
        request,
        user,
        "admin.user.reset_approval_token"
    )
    
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
```

## 修复 4: admin_reset_user_password (Line 203-259)

**添加令牌验证和改进异常处理**:

```python
@router.post("/users/{user_id}/reset-password", response_model=AdminUserSummary)
@limiter.limit(get_rate_limit("password_reset"))
def admin_reset_user_password(
    user_id: str,
    req: AdminResetPasswordRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    target = auth_service.get_user_profile(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    approval_token = req.approval_token or ""
    actor_user_id = str(user.get("user_id", ""))
    
    # 使用新的令牌验证函数
    token_ok, token_mode = validate_and_check_approval_token(
        approval_token,
        actor_user_id,
        _audit,
        request,
        user,
        "admin.user.reset_password"
    )
    
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
```

## 修复 5: admin_update_user_status (Line 262-281)

**添加自我修改检查和改进异常处理**:

```python
@router.patch("/users/{user_id}/status", response_model=AdminUserSummary)
@limiter.limit(get_rate_limit("status_update"))
def admin_update_user_status(user_id: str, req: AdminStatusUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    
    # 添加自我修改检查
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
```

## 修复 6: admin_update_user_classification (Line 284-325)

**改进异常处理**:

```python
@router.patch("/users/{user_id}/classification", response_model=AdminUserSummary)
def admin_update_user_classification(
    user_id: str,
    req: AdminUserClassificationUpdateRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
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
```

## 修复 7: 添加速率限制到查询端点

```python
@router.get("/users", response_model=list[AdminUserSummary])
@limiter.limit(get_rate_limit("list_users"))
def admin_list_users(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin")
    rows = auth_service.list_users()
    return [AdminUserSummary(**x) for x in rows]

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
```

## 修复 8: 删除旧的令牌验证函数

**删除 `_is_valid_admin_approval_token_for_actor` 函数（Line 21-33）**，因为已被新的 `validate_admin_approval_token` 替代。

## 在 main.py 中注册速率限制器

在 `app/api/main.py` 中添加：

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.services.admin_rate_limit import get_limiter

# 注册速率限制器
limiter = get_limiter()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

## 总结

这些修复解决了以下安全问题：

1. ✅ 防止管理员自我修改（角色、状态、审批令牌）
2. ✅ 实现审批令牌单次使用
3. ✅ 防止信息泄露（统一错误消息）
4. ✅ 改进异常处理和审计日志
5. ✅ 添加速率限制防止暴力破解
6. ✅ 增强输入验证（工单 ID 格式等）
7. ✅ 防止时序攻击（恒定时间比较）
