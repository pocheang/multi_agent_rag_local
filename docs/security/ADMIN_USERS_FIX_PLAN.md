# admin_users.py 安全漏洞修复计划

**版本**: v0.3.1.2 (Security Patch)  
**优先级**: 🔴 CRITICAL  
**预计时间**: 2-3 天  
**负责人**: 开发团队 + 安全团队

## 漏洞总结

在 `app/api/routes/admin_users.py` 中发现 **10 个安全漏洞**：

| 严重程度 | 数量 | 漏洞 |
|---------|------|------|
| 🔴 严重 | 3 | 自我权限修改、令牌重复使用、已禁用管理员绕过 |
| 🟠 高危 | 3 | 竞态条件、信息泄露、审计绕过 |
| 🟡 中危 | 4 | 无速率限制、弱验证、时序攻击 |

**最严重的问题**:
1. 管理员可以修改自己的角色和状态
2. 单个审批令牌可创建无限管理员账户
3. 已禁用的管理员仍可执行所有操作

---

## 修复阶段

### 阶段 1: 紧急修复（立即 - 1 天）

#### 1.1 添加自我修改检查

**文件**: `app/api/routes/admin_users.py`

**修改端点**:
- `admin_update_user_role` (Line 51)
- `admin_update_user_status` (Line 262)
- `admin_reset_user_approval_token` (Line 137)

**修复代码**:

```python
# 在每个敏感端点的开头添加
def admin_update_user_role(user_id: str, req: AdminRoleUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    
    # 添加自我修改检查
    if user_id == user.get("user_id"):
        _audit(
            request,
            action="admin.user.role_update",
            resource_type="user",
            result="blocked_self_modification",
            user=user,
            resource_id=user_id,
            detail="attempted to modify own role"
        )
        raise HTTPException(status_code=403, detail="cannot modify your own role")
    
    # 其余代码保持不变...
```

**测试**:
```bash
pytest tests/test_admin_security.py::test_admin_cannot_modify_own_role -v
pytest tests/test_admin_security.py::test_admin_cannot_disable_self -v
```

---

#### 1.2 强制用户状态检查

**文件**: `app/api/dependencies.py`

**修改函数**: `_require_user`

**修复代码**:

```python
def _require_user(request: Request, token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """验证用户令牌并返回用户信息"""
    try:
        user = auth_service.verify_session_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="invalid or expired token")
        
        # 添加状态检查
        user_status = str(user.get("status", "")).lower()
        if user_status != "active":
            _audit(
                request,
                action="auth.access_denied",
                resource_type="session",
                result="blocked_inactive_user",
                user=user,
                detail=f"status={user_status}"
            )
            raise HTTPException(status_code=403, detail="account is not active")
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="authentication failed")
```

**测试**:
```bash
pytest tests/test_admin_security.py::test_disabled_admin_cannot_act -v
```

---

#### 1.3 统一错误消息

**文件**: `app/api/routes/admin_users.py`

**修改位置**: Lines 79-96, 152-170, 216-234

**修复代码**:

```python
# 替换所有详细错误消息
if not token_ok or token_mode == "missing":
    _audit(
        request,
        action="admin.user.create_admin",
        resource_type="user",
        result="failed",
        user=user,
        detail=f"approval_failed; mode={token_mode}; ticket={ticket_id or '-'}"
    )
    # 统一错误消息，不泄露配置信息
    raise HTTPException(status_code=403, detail="unauthorized")
```

---

### 阶段 2: 高优先级修复（1-2 天）

#### 2.1 实现令牌单次使用

**新增文件**: `app/services/admin_token_tracker.py`

```python
"""管理员审批令牌跟踪服务"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional

class AdminTokenTracker:
    """跟踪审批令牌使用情况"""
    
    def __init__(self):
        self._used_tokens: dict[str, dict] = {}  # token_hash -> {used_at, used_by}
        self._token_expiry_hours = 24
    
    def is_token_used(self, token_hash: str) -> bool:
        """检查令牌是否已被使用"""
        if token_hash in self._used_tokens:
            used_info = self._used_tokens[token_hash]
            used_at = used_info.get("used_at")
            
            # 检查是否过期（24小时后清理）
            if used_at and (datetime.utcnow() - used_at).total_seconds() < self._token_expiry_hours * 3600:
                return True
            else:
                # 过期，清理
                del self._used_tokens[token_hash]
        
        return False
    
    def mark_token_used(self, token_hash: str, user_id: str) -> None:
        """标记令牌为已使用"""
        self._used_tokens[token_hash] = {
            "used_at": datetime.utcnow(),
            "used_by": user_id
        }
    
    def cleanup_expired(self) -> int:
        """清理过期的令牌记录"""
        now = datetime.utcnow()
        expired = [
            token_hash for token_hash, info in self._used_tokens.items()
            if (now - info["used_at"]).total_seconds() >= self._token_expiry_hours * 3600
        ]
        for token_hash in expired:
            del self._used_tokens[token_hash]
        return len(expired)

# 全局实例
token_tracker = AdminTokenTracker()
```

**修改**: `app/api/routes/admin_users.py`

```python
from app.services.admin_token_tracker import token_tracker

def _is_valid_admin_approval_token_for_actor(token: str, actor_user_id: str) -> tuple[bool, str]:
    """验证审批令牌并检查是否已使用"""
    candidate = str(token or "").strip()
    configured_hash = str(getattr(settings, "admin_create_approval_token_hash", "") or "").strip().lower()
    
    if not configured_hash:
        return False, "missing"
    if not candidate:
        return False, "empty"
    
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest().lower()
    
    # 检查令牌是否已被使用
    if token_tracker.is_token_used(digest):
        return False, "already_used"
    
    is_valid = hmac.compare_digest(digest, configured_hash)
    
    if is_valid:
        # 标记令牌为已使用
        token_tracker.mark_token_used(digest, actor_user_id)
    
    return is_valid, "hash"
```

**测试**:
```bash
pytest tests/test_admin_security.py::test_approval_token_single_use -v
```

---

#### 2.2 添加速率限制

**安装依赖**:
```bash
pip install slowapi
```

**修改**: `app/api/routes/admin_users.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/users/create-admin", response_model=AdminUserSummary)
@limiter.limit("1/hour")  # 每小时最多创建1个管理员
def admin_create_user_as_admin(req: AdminCreateAdminRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    # ... 代码

@router.post("/users/{user_id}/reset-approval-token", response_model=AdminUserSummary)
@limiter.limit("3/hour")  # 每小时最多重置3次
def admin_reset_user_approval_token(...):
    # ... 代码

@router.post("/users/{user_id}/reset-password", response_model=AdminUserSummary)
@limiter.limit("5/hour")  # 每小时最多重置5次密码
def admin_reset_user_password(...):
    # ... 代码
```

**在 `app/api/main.py` 中注册**:
```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

---

#### 2.3 改进异常处理和审计

**修改**: `app/api/routes/admin_users.py`

**所有端点添加全面异常处理**:

```python
@router.patch("/users/{user_id}/role", response_model=AdminUserSummary)
def admin_update_user_role(user_id: str, req: AdminRoleUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    
    if user_id == user.get("user_id"):
        _audit(request, action="admin.user.role_update", resource_type="user", result="blocked_self_modification", user=user, resource_id=user_id)
        raise HTTPException(status_code=403, detail="cannot modify your own role")
    
    if str(req.role or "").strip().lower() == "admin":
        raise HTTPException(status_code=400, detail="admin role promotion is restricted; use /admin/users/create-admin")
    
    try:
        row = auth_service.update_user_role(user_id=user_id, role=req.role)
    except Exception as e:
        # 捕获所有异常并审计
        _audit(
            request,
            action="admin.user.role_update",
            resource_type="user",
            result="failed",
            user=user,
            resource_id=user_id,
            detail=f"{type(e).__name__}: {str(e)}"
        )
        if isinstance(e, ValueError):
            raise HTTPException(status_code=400, detail=str(e))
        logger.error(f"Unexpected error in admin_update_user_role: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="operation failed")
    
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

---

### 阶段 3: 中优先级改进（3-5 天）

#### 3.1 工单 ID 格式验证

```python
import re

TICKET_ID_PATTERN = re.compile(r'^[A-Z]+-\d+$')  # 例如: JIRA-123, TICKET-456

def validate_ticket_id(ticket_id: str) -> None:
    """验证工单 ID 格式"""
    if not TICKET_ID_PATTERN.match(ticket_id):
        raise HTTPException(
            status_code=400,
            detail="invalid ticket format (expected: PROJECT-NUMBER, e.g., JIRA-123)"
        )

# 在所有需要 ticket_id 的端点中使用
if len(ticket_id) < 3:
    raise HTTPException(status_code=400, detail="ticket_id is required")
validate_ticket_id(ticket_id)  # 添加格式验证
```

---

#### 3.2 修复时序攻击

```python
def _is_valid_admin_approval_token_for_actor(token: str, actor_user_id: str) -> tuple[bool, str]:
    """验证审批令牌（防时序攻击）"""
    candidate = str(token or "").strip()
    configured_hash = str(getattr(settings, "admin_create_approval_token_hash", "") or "").strip().lower()
    
    # 始终执行比较以保持恒定时间
    if configured_hash:
        digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest().lower()
        
        # 检查令牌是否已被使用
        if token_tracker.is_token_used(digest):
            # 仍然执行比较以保持恒定时间
            hmac.compare_digest(digest, configured_hash)
            return False, "already_used"
        
        is_valid = hmac.compare_digest(digest, configured_hash)
        
        if is_valid:
            token_tracker.mark_token_used(digest, actor_user_id)
        
        return is_valid, "hash"
    else:
        # 执行虚拟比较以保持恒定时间
        dummy_digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest().lower()
        hmac.compare_digest(dummy_digest, "0" * 64)  # 虚拟哈希
        return False, "missing"
```

---

## 测试计划

### 新增测试文件

**文件**: `tests/test_admin_security.py`

```python
"""管理员安全测试"""
import pytest
from fastapi.testclient import TestClient
from unittest import mock

def test_admin_cannot_modify_own_role(client, admin_headers, admin_user_id):
    """严重: 防止自我权限提升"""
    response = client.patch(
        f"/admin/users/{admin_user_id}/role",
        json={"role": "super_admin"},
        headers=admin_headers
    )
    assert response.status_code == 403
    assert "cannot modify your own role" in response.json()["detail"]

def test_admin_cannot_disable_self(client, admin_headers, admin_user_id):
    """严重: 防止自我禁用"""
    response = client.patch(
        f"/admin/users/{admin_user_id}/status",
        json={"status": "disabled"},
        headers=admin_headers
    )
    assert response.status_code == 403

def test_approval_token_single_use(client, admin_headers):
    """严重: 防止令牌重复使用"""
    token = "test-approval-token-12345678"
    
    # 第一次使用成功
    response1 = client.post("/admin/users/create-admin", json={
        "username": "testadmin1",
        "password": "SecurePass123!",
        "approval_token": token,
        "ticket_id": "JIRA-123",
        "reason": "legitimate business need",
        "new_admin_approval_token": "new-token-1234567890"
    }, headers=admin_headers)
    assert response1.status_code == 200
    
    # 第二次使用同一令牌失败
    response2 = client.post("/admin/users/create-admin", json={
        "username": "testadmin2",
        "password": "SecurePass123!",
        "approval_token": token,  # 重复使用
        "ticket_id": "JIRA-124",
        "reason": "another reason",
        "new_admin_approval_token": "new-token-0987654321"
    }, headers=admin_headers)
    assert response2.status_code == 403

def test_disabled_admin_cannot_act(client, auth_service, admin_user_id, admin_headers):
    """严重: 强制状态检查"""
    # 禁用管理员
    auth_service.update_user_status(admin_user_id, "disabled")
    
    # 尝试管理员操作
    response = client.get("/admin/users", headers=admin_headers)
    assert response.status_code == 403
    assert "not active" in response.json()["detail"]

def test_rate_limiting_on_admin_creation(client, admin_headers):
    """中危: 防止暴力破解"""
    # 快速连续创建多个管理员
    responses = []
    for i in range(3):
        response = client.post("/admin/users/create-admin", json={
            "username": f"admin{i}",
            "password": "SecurePass123!",
            "approval_token": f"token-{i}",
            "ticket_id": f"JIRA-{i}",
            "reason": "test",
            "new_admin_approval_token": f"new-token-{i}"
        }, headers=admin_headers)
        responses.append(response)
    
    # 至少有一个应该被速率限制阻止
    assert any(r.status_code == 429 for r in responses)

def test_audit_log_on_exception(client, admin_headers, auth_service):
    """高危: 确保所有失败都被审计"""
    user_id = "test-user-123"
    
    # 触发异常
    with mock.patch.object(auth_service, 'update_user_role', side_effect=Exception("database error")):
        response = client.patch(
            f"/admin/users/{user_id}/role",
            json={"role": "analyst"},
            headers=admin_headers
        )
    
    # 检查审计日志
    logs = auth_service.list_audit_logs(action_keyword="role_update", result="failed")
    assert len(logs) > 0
    assert "Exception" in logs[0]["detail"] or "database error" in logs[0]["detail"]

def test_ticket_id_format_validation(client, admin_headers):
    """中危: 验证工单 ID 格式"""
    response = client.post("/admin/users/create-admin", json={
        "username": "testadmin",
        "password": "SecurePass123!",
        "approval_token": "valid-token",
        "ticket_id": "invalid",  # 无效格式
        "reason": "test reason",
        "new_admin_approval_token": "new-token-123"
    }, headers=admin_headers)
    assert response.status_code == 400
    assert "invalid ticket format" in response.json()["detail"]
```

**运行测试**:
```bash
pytest tests/test_admin_security.py -v --cov=app/api/routes/admin_users
```

---

## 部署检查清单

### 部署前

- [ ] 所有修复代码已审查
- [ ] 所有测试通过（单元测试 + 集成测试）
- [ ] 安全测试通过
- [ ] 代码覆盖率 > 90%
- [ ] 文档已更新

### 部署时

- [ ] 创建数据库备份
- [ ] 在测试环境验证
- [ ] 准备回滚计划
- [ ] 通知所有管理员用户

### 部署后

- [ ] 验证所有端点正常工作
- [ ] 检查审计日志记录正确
- [ ] 监控错误率
- [ ] 验证速率限制生效
- [ ] 进行渗透测试

---

## 回滚计划

如果部署后发现问题：

1. **立即回滚**: 恢复到 v0.3.1.1
2. **保留审计日志**: 不要删除新的审计记录
3. **分析问题**: 确定失败原因
4. **修复并重新测试**: 在测试环境修复
5. **重新部署**: 使用修复后的版本

---

## 时间表

| 阶段 | 任务 | 时间 | 负责人 |
|------|------|------|--------|
| 阶段 1 | 紧急修复 | 1 天 | 开发团队 |
| 阶段 2 | 高优先级修复 | 1-2 天 | 开发团队 |
| 阶段 3 | 中优先级改进 | 2-3 天 | 开发团队 |
| 测试 | 全面测试 | 1 天 | QA 团队 |
| 部署 | 生产部署 | 0.5 天 | DevOps 团队 |
| **总计** | | **5-7 天** | |

---

## 相关文档

- [安全审计报告](./ADMIN_USERS_SECURITY_AUDIT.md)
- [测试计划](../tests/test_admin_security.py)
- [部署指南](../operations/DEPLOYMENT_GUIDE.md)
- [回滚流程](../operations/ROLLBACK_PROCEDURE.md)
