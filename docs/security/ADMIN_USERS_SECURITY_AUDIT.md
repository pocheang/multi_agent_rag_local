# admin_users.py 安全审计报告

**审计日期**: 2026-04-28  
**文件**: `app/api/routes/admin_users.py`  
**审计人**: Claude Code Security Review  
**严重程度**: 🔴 CRITICAL

## 执行摘要

在 `admin_users.py` 中发现了 **3 个严重漏洞**、**3 个高危漏洞**和 **4 个中危漏洞**。最严重的问题包括：

1. **管理员可以修改自己的权限** - 无自我修改检查
2. **审批令牌可重复使用** - 单个令牌可创建无限管理员账户
3. **已禁用的管理员仍可操作** - 状态字段未在认证流程中检查

这些漏洞可能导致权限提升、后门账户创建和审计绕过。

---

## 🔴 严重漏洞 (Critical)

### 1. 自我权限修改漏洞

**严重程度**: 🔴 CRITICAL  
**CVSS 评分**: 9.1 (Critical)  
**影响范围**: 所有管理员操作端点

#### 问题描述

管理员可以修改自己的角色、状态和审批令牌，没有任何自我修改检查。

#### 受影响的端点

```python
# Line 51-72: admin_update_user_role
PATCH /admin/users/{user_id}/role
# 管理员可以修改自己的角色

# Line 262-281: admin_update_user_status  
PATCH /admin/users/{user_id}/status
# 管理员可以禁用/启用自己

# Line 137-200: admin_reset_user_approval_token
POST /admin/users/{user_id}/reset-approval-token
# 管理员可以重置自己的审批令牌
```

#### 攻击场景

```python
# 场景 1: 管理员降级自己以绕过审计
admin_user_id = "admin-123"
PATCH /admin/users/admin-123/role
Body: {"role": "viewer"}
# 现在以 viewer 身份执行恶意操作，审计日志显示 viewer 而非 admin

# 场景 2: 管理员禁用自己以逃避调查
PATCH /admin/users/admin-123/status
Body: {"status": "disabled"}
# 声称账户被入侵，逃避责任

# 场景 3: 管理员重置自己的审批令牌
POST /admin/users/admin-123/reset-approval-token
# 获得新的审批令牌，可以创建更多管理员
```

#### 影响

- ✗ 权限提升和降级
- ✗ 审计追踪绕过
- ✗ 职责分离失效
- ✗ 后门账户创建

#### 修复方案

```python
# 在所有敏感端点添加自我修改检查

@router.patch("/users/{user_id}/role", response_model=AdminUserSummary)
def admin_update_user_role(user_id: str, req: AdminRoleUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    
    # 添加自我修改检查
    if user_id == user.get("user_id"):
        _audit(request, action="admin.user.role_update", resource_type="user", result="blocked_self_modification", user=user, resource_id=user_id)
        raise HTTPException(status_code=403, detail="cannot modify your own role")
    
    if str(req.role or "").strip().lower() == "admin":
        raise HTTPException(status_code=400, detail="admin role promotion is restricted; use /admin/users/create-admin")
    # ... 其余代码
```

**需要添加检查的端点**:
- `admin_update_user_role` (Line 51)
- `admin_update_user_status` (Line 262)
- `admin_reset_user_approval_token` (Line 137)

---

### 2. 审批令牌重复使用漏洞

**严重程度**: 🔴 CRITICAL  
**CVSS 评分**: 9.3 (Critical)  
**影响范围**: 管理员创建和令牌重置

#### 问题描述

同一个审批令牌可以被多次使用来创建无限数量的管理员账户。没有令牌失效或单次使用强制机制。

#### 受影响的端点

```python
# Line 75-134: admin_create_user_as_admin
POST /admin/users/create-admin
# 可以用同一个令牌创建多个管理员

# Line 137-200: admin_reset_user_approval_token
POST /admin/users/{user_id}/reset-approval-token
# 令牌轮换不会使旧令牌失效
```

#### 攻击场景

```python
# 攻击者获得一次审批令牌（通过社会工程、内部泄露等）
approval_token = "leaked-token-12345"

# 创建多个后门管理员账户
for i in range(10):
    POST /admin/users/create-admin
    Body: {
        "username": f"backdoor-admin-{i}",
        "password": "secret",
        "approval_token": approval_token,  # 重复使用同一令牌
        "ticket_id": f"FAKE-{i}",
        "reason": "legitimate reason",
        "new_admin_approval_token": f"new-token-{i}"
    }
# 所有请求都成功！
```

#### 影响

- ✗ 单个令牌泄露 = 无限管理员账户
- ✗ 无速率限制
- ✗ 令牌轮换无效
- ✗ 无法撤销已泄露的令牌

#### 修复方案

**方案 1: 单次使用令牌（推荐）**

```python
# 在数据库中跟踪令牌使用情况
# 新增表: admin_approval_tokens
# 字段: token_hash, used_at, used_by_user_id, created_at

def _is_valid_admin_approval_token_for_actor(token: str, actor_user_id: str) -> tuple[bool, str]:
    """验证审批令牌并标记为已使用"""
    candidate = str(token or "").strip()
    configured_hash = str(getattr(settings, "admin_create_approval_token_hash", "") or "").strip().lower()
    
    if not configured_hash:
        return False, "missing"
    if not candidate:
        return False, "empty"
    
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest().lower()
    is_valid = hmac.compare_digest(digest, configured_hash)
    
    if is_valid:
        # 检查令牌是否已被使用
        if auth_service.is_token_used(digest):
            return False, "already_used"
        
        # 标记令牌为已使用
        auth_service.mark_token_used(digest, actor_user_id)
    
    return is_valid, "hash"
```

**方案 2: 速率限制**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/users/create-admin", response_model=AdminUserSummary)
@limiter.limit("1/hour")  # 每小时最多创建 1 个管理员
def admin_create_user_as_admin(req: AdminCreateAdminRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    # ... 代码
```

**方案 3: 令牌过期**

```python
# 在配置中添加令牌过期时间
ADMIN_APPROVAL_TOKEN_EXPIRES_HOURS = 24

def _is_valid_admin_approval_token_for_actor(token: str, actor_user_id: str) -> tuple[bool, str]:
    # ... 验证逻辑
    
    # 检查令牌是否过期
    token_created_at = auth_service.get_token_created_at(digest)
    if token_created_at:
        age_hours = (datetime.utcnow() - token_created_at).total_seconds() / 3600
        if age_hours > ADMIN_APPROVAL_TOKEN_EXPIRES_HOURS:
            return False, "expired"
    
    return is_valid, "hash"
```

---

### 3. 已禁用管理员仍可操作

**严重程度**: 🔴 CRITICAL  
**CVSS 评分**: 8.7 (High)  
**影响范围**: 所有管理员端点

#### 问题描述

没有验证执行操作的管理员用户的 `status='active'`。已禁用的管理员如果有有效会话令牌，仍可执行所有管理员操作。

#### 受影响的端点

所有 `/admin/*` 端点都受影响，因为 `_require_user` 依赖项不检查用户状态。

#### 攻击场景

```python
# 1. 管理员因不当行为被禁用
PATCH /admin/users/admin-123/status
Body: {"status": "disabled"}

# 2. 但该管理员的会话令牌仍然有效
# 3. 已禁用的管理员继续执行操作
GET /admin/users  # 成功！
POST /admin/users/create-admin  # 成功！
PATCH /admin/users/other-user/role  # 成功！

# 状态字段实际上毫无意义
```

#### 影响

- ✗ 已禁用的管理员保留完全权限
- ✗ 状态字段对访问控制无效
- ✗ 无法立即撤销管理员访问权限
- ✗ 合规性问题（无法强制执行访问撤销）

#### 修复方案

**在 `app/api/dependencies.py` 中修复 `_require_user`**:

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
    except Exception as e:
        raise HTTPException(status_code=401, detail="authentication failed")
```

---

## 🟠 高危漏洞 (High)

### 4. 令牌验证中的竞态条件

**严重程度**: 🟠 HIGH  
**CVSS 评分**: 7.2 (High)

#### 问题描述

令牌验证从设置中读取而不加锁。如果在验证期间更新设置，可能出现不一致状态。

#### 代码位置

```python
# Line 21-33: _is_valid_admin_approval_token_for_actor
def _is_valid_admin_approval_token_for_actor(token: str, actor_user_id: str) -> tuple[bool, str]:
    candidate = str(token or "").strip()
    configured_hash = str(getattr(settings, "admin_create_approval_token_hash", "") or "").strip().lower()
    configured_plain = str(getattr(settings, "admin_create_approval_token", "") or "").strip()
    # 竞态窗口：settings 可能在这两次读取之间改变
```

#### 修复方案

```python
# 在启动时缓存令牌哈希
class AdminTokenCache:
    _token_hash: str | None = None
    _lock = threading.Lock()
    
    @classmethod
    def get_token_hash(cls) -> str:
        with cls._lock:
            if cls._token_hash is None:
                cls._token_hash = str(getattr(settings, "admin_create_approval_token_hash", "") or "").strip().lower()
            return cls._token_hash
    
    @classmethod
    def refresh(cls):
        with cls._lock:
            cls._token_hash = None

def _is_valid_admin_approval_token_for_actor(token: str, actor_user_id: str) -> tuple[bool, str]:
    candidate = str(token or "").strip()
    configured_hash = AdminTokenCache.get_token_hash()
    # ... 其余逻辑
```

---

### 5. 错误消息中的信息泄露

**严重程度**: 🟠 HIGH  
**CVSS 评分**: 6.8 (Medium)

#### 问题描述

错误消息透露审批令牌是"缺失"、"空"还是"无效"，帮助攻击者了解配置状态。

#### 代码位置

```python
# Line 79-83, 152-156, 216-220
if token_mode == "missing":
    raise HTTPException(
        status_code=500,
        detail="approval token is not configured (set ADMIN_CREATE_APPROVAL_TOKEN_HASH or ADMIN_CREATE_APPROVAL_TOKEN)",
    )
```

#### 修复方案

```python
# 统一所有错误消息
if not token_ok or token_mode == "missing":
    _audit(
        request,
        action="admin.user.create_admin",
        resource_type="user",
        result="failed",
        user=user,
        detail=f"approval_failed; mode={token_mode}",  # 仅记录在审计日志中
    )
    raise HTTPException(status_code=403, detail="unauthorized")  # 通用错误消息
```

---

### 6. 异常导致的审计日志绕过

**严重程度**: 🟠 HIGH  
**CVSS 评分**: 7.1 (High)

#### 问题描述

如果 `auth_service` 方法抛出异常，审计日志可能不会被写入。只捕获了显式的 `ValueError`。

#### 代码位置

```python
# Line 55-60
try:
    row = auth_service.update_user_role(user_id=user_id, role=req.role)
except ValueError as e:
    _audit(..., result="failed", ...)
    raise HTTPException(status_code=400, detail=str(e))
# 如果发生 DatabaseError 或其他异常，没有审计日志！
```

#### 修复方案

```python
try:
    row = auth_service.update_user_role(user_id=user_id, role=req.role)
except Exception as e:
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
    raise HTTPException(status_code=500, detail="operation failed")
```

---

## 🟡 中危漏洞 (Medium)

### 7. 敏感操作无速率限制

**严重程度**: 🟡 MEDIUM  
**修复方案**: 添加速率限制装饰器

```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@router.post("/users/create-admin")
@limiter.limit("1/hour")
def admin_create_user_as_admin(...):
    # ...
```

---

### 8. 工单 ID 验证薄弱

**严重程度**: 🟡 MEDIUM  
**修复方案**: 添加格式验证

```python
import re
TICKET_PATTERN = re.compile(r'^[A-Z]+-\d+$')  # 例如 JIRA-1234

if not TICKET_PATTERN.match(ticket_id):
    raise HTTPException(status_code=400, detail="invalid ticket format (expected: PROJ-123)")
```

---

### 9. 无需当前密码的密码重置

**严重程度**: 🟡 MEDIUM  
**修复方案**: 对管理员账户要求额外批准

```python
def admin_reset_user_password(...):
    target = auth_service.get_user_profile(user_id)
    
    # 重置其他管理员的密码需要超级管理员批准
    if target.get("role") == "admin" and user_id != user.get("user_id"):
        if not req.super_admin_approval_token:
            raise HTTPException(status_code=403, detail="super admin approval required for admin password reset")
```

---

### 10. 令牌比较中的时序攻击

**严重程度**: 🟡 MEDIUM  
**修复方案**: 始终执行比较以保持恒定时间

```python
def _is_valid_admin_approval_token_for_actor(token: str, actor_user_id: str) -> tuple[bool, str]:
    candidate = str(token or "").strip()
    configured_hash = str(getattr(settings, "admin_create_approval_token_hash", "") or "").strip().lower()
    
    # 始终执行比较以避免时序攻击
    if configured_hash:
        digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest().lower()
        is_valid = hmac.compare_digest(digest, configured_hash)
        return is_valid, "hash"
    else:
        # 执行虚拟比较以保持恒定时间
        hmac.compare_digest(candidate, "dummy_token_to_maintain_constant_timing")
        return False, "missing"
```

---

## 边缘情况分析

### 自我修改场景

| 操作 | user_id == actor_user_id | 当前行为 | 预期行为 |
|------|-------------------------|----------|----------|
| 角色更新 | ✓ | **允许** ❌ | 阻止 |
| 状态更新 | ✓ | **允许** ❌ | 阻止 |
| 密码重置 | ✓ | **允许** ✓ | 允许（需要当前密码） |
| 审批令牌重置 | ✓ | **允许** ❌ | 阻止 |
| 分类更新 | ✓ | **允许** ✓ | 允许（低风险） |

### 已禁用管理员场景

| 场景 | 当前行为 | 预期行为 |
|------|----------|----------|
| 已禁用管理员有有效会话 | **可以操作** ❌ | 阻止 |
| 已禁用管理员创建新管理员 | **成功** ❌ | 阻止 |
| 管理员禁用自己 | **成功** ❌ | 阻止或警告 |

### 令牌重复使用场景

| 场景 | 当前行为 | 预期行为 |
|------|----------|----------|
| 使用同一令牌两次 | **成功** ❌ | 阻止（单次使用） |
| 轮换后使用令牌 | **成功** ❌ | 阻止（已失效） |
| 并发令牌使用 | **成功** ❌ | 阻止（竞态检测） |

---

## 修复优先级

### 立即修复（1-2 天）

1. ✅ 添加自我修改检查到所有敏感端点
2. ✅ 在 `_require_user` 中验证用户状态
3. ✅ 统一错误消息以防止信息泄露

### 短期修复（1 周）

4. ✅ 实现令牌使用跟踪和单次使用强制
5. ✅ 添加速率限制到所有管理员端点
6. ✅ 添加全面的异常处理和审计日志

### 中期改进（2-4 周）

7. ✅ 实现令牌过期机制
8. ✅ 添加工单 ID 格式验证
9. ✅ 为管理员密码重置要求额外批准
10. ✅ 修复时序攻击漏洞

---

## 测试用例

```python
# tests/test_admin_security.py

def test_admin_cannot_modify_own_role():
    """严重: 防止自我权限提升"""
    response = client.patch(
        f"/admin/users/{admin_user_id}/role",
        json={"role": "super_admin"},
        headers=admin_headers
    )
    assert response.status_code == 403
    assert "cannot modify your own role" in response.json()["detail"]

def test_admin_cannot_disable_self():
    """严重: 防止自我禁用"""
    response = client.patch(
        f"/admin/users/{admin_user_id}/status",
        json={"status": "disabled"},
        headers=admin_headers
    )
    assert response.status_code == 403

def test_approval_token_single_use():
    """严重: 防止令牌重复使用"""
    token = "test-approval-token"
    
    # 第一次使用成功
    response1 = client.post("/admin/users/create-admin", json={
        "username": "admin1",
        "password": "password123",
        "approval_token": token,
        "ticket_id": "JIRA-123",
        "reason": "legitimate reason",
        "new_admin_approval_token": "new-token-1"
    })
    assert response1.status_code == 200
    
    # 第二次使用同一令牌失败
    response2 = client.post("/admin/users/create-admin", json={
        "username": "admin2",
        "password": "password123",
        "approval_token": token,  # 重复使用
        "ticket_id": "JIRA-124",
        "reason": "another reason",
        "new_admin_approval_token": "new-token-2"
    })
    assert response2.status_code == 403
    assert "already_used" in response2.json()["detail"] or "unauthorized" in response2.json()["detail"]

def test_disabled_admin_cannot_act():
    """严重: 强制状态检查"""
    # 禁用管理员
    auth_service.update_user_status(admin_user_id, "disabled")
    
    # 尝试管理员操作
    response = client.get("/admin/users", headers=admin_headers)
    assert response.status_code == 403
    assert "not active" in response.json()["detail"]

def test_rate_limiting_on_admin_creation():
    """中危: 防止暴力破解"""
    # 快速连续创建多个管理员
    for i in range(5):
        response = client.post("/admin/users/create-admin", json={...})
    
    # 应该被速率限制阻止
    assert response.status_code == 429

def test_audit_log_on_exception():
    """高危: 确保所有失败都被审计"""
    # 触发数据库错误
    with mock.patch('auth_service.update_user_role', side_effect=DatabaseError("connection lost")):
        response = client.patch(f"/admin/users/{user_id}/role", json={"role": "analyst"})
    
    # 检查审计日志是否记录了失败
    logs = auth_service.list_audit_logs(action_keyword="role_update", result="failed")
    assert len(logs) > 0
    assert "DatabaseError" in logs[0]["detail"]
```

---

## 合规性影响

这些漏洞可能违反以下合规性要求：

- **SOC 2**: 访问控制和审计日志要求
- **ISO 27001**: 访问管理和职责分离
- **GDPR**: 访问撤销和审计追踪
- **PCI DSS**: 管理员账户管理和审计日志

---

## 建议的后续行动

1. **立即**: 实施严重漏洞修复
2. **本周**: 添加全面的安全测试
3. **本月**: 进行渗透测试
4. **持续**: 实施安全代码审查流程

---

## 参考资料

- [OWASP Top 10 - Broken Access Control](https://owasp.org/Top10/A01_2021-Broken_Access_Control/)
- [CWE-284: Improper Access Control](https://cwe.mitre.org/data/definitions/284.html)
- [CWE-863: Incorrect Authorization](https://cwe.mitre.org/data/definitions/863.html)
- [NIST SP 800-53: Access Control](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
