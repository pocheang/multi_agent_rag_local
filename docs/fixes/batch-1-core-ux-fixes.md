# 第一批修复 - 核心用户体验问题

**修复日期**: 2026-08-21  
**优先级**: 🔴 严重 - 影响核心功能  
**状态**: ✅ 已完成代码修改，待测试

---

## 修复概览

| 问题 | 影响 | 修复文件 | 状态 |
|------|------|----------|------|
| 问题2: 重复请求409冲突 | 用户无法获得查询结果 | 3个文件 | ✅ 完成 |
| 问题4: Session不存在报错 | 用户体验不连贯 | 1个文件 | ✅ 完成 |
| 问题1: 密码修改后被登出 | 用户困惑 | 1个文件 | ✅ 完成 |

---

## 问题2: 重复请求处理优化

### 🎯 修复目标
将重复请求从返回 **409 冲突** 改为返回 **202 Accepted + 处理中状态**，让用户可以等待或轮询结果。

### 📝 修改文件

#### 1. `app/api/transport/errors.py`
**新增**: `accepted()` 函数用于返回202状态码

```python
def accepted(detail: str = "Request accepted for processing", 
             headers: dict[str, str] | None = None) -> HTTPException:
    """Return a 202 Accepted response (for async operations)."""
    return HTTPException(status_code=202, detail=detail, headers=headers or {})
```

#### 2. `app/api/schemas/http.py`
**新增**: `QueryResponse` 增加状态字段

```python
class QueryResponse(BaseModel):
    # ... 原有字段 ...
    status: str = Field(default="completed", 
                       description="Query status: completed, processing, pending")
    request_id: str | None = Field(default=None, 
                                   description="Request ID for status tracking")
```

#### 3. `app/api/query/request.py`
**修改**: 重复请求处理逻辑

**修改前**:
```python
if not query_result_cache.mark_inflight(cache_key):
    # ... 尝试获取缓存 ...
    raise conflict("duplicate request in progress")  # ❌ 返回409
```

**修改后**:
```python
if not query_result_cache.mark_inflight(cache_key):
    # ... 尝试获取缓存 ...
    # ✅ 返回处理中状态，而非冲突错误
    return QueryResponse(
        answer="查询正在处理中，请稍候...",
        route="processing",
        status="processing",
        request_id=req.request_id or cache_key[:32],
        debug={
            "message": "您的查询正在处理中，这可能是因为重复提交。请稍候片刻后刷新页面查看结果。",
            "suggestion": "请避免重复点击提交按钮",
            "estimated_wait_seconds": 10,
        }
    )
```

#### 4. `app/api/routes/public/query_status.py` (新文件)
**新增**: 查询状态轮询端点

```python
@router.get("/query/status/{request_id}", response_model=QueryResponse)
def get_query_status(request_id: str, ...):
    """
    获取查询状态（用于处理重复请求或长时间运行的查询）
    
    前端使用场景：
    1. 收到 status="processing" 响应
    2. 每2-3秒轮询此端点
    3. 直到收到 status="completed" 或超时
    """
```

### 📊 用户体验改进

**修改前**:
```
用户: 点击"提问" → 网络慢 → 再点一次
系统: ❌ HTTP 409 "duplicate request in progress"
用户: 😕 我的查询失败了吗？需要重试吗？
```

**修改后**:
```
用户: 点击"提问" → 网络慢 → 再点一次
系统: ✅ HTTP 200 "查询正在处理中，请稍候..."
前端: 显示进度条，自动轮询 /query/status/{request_id}
用户: 😊 知道系统在处理，耐心等待
```

---

## 问题4: 自动创建Session

### 🎯 修复目标
当用户发送查询时，如果session不存在，**自动创建**而非报错，提升用户体验的连贯性。

### 📝 修改文件

#### 1. `app/api/deps/sessions.py`
**修改**: `_require_existing_session_for_query()` 函数

**修改前**:
```python
def _require_existing_session_for_query(user, session_id):
    if not session_id:
        return None
    normalized = _require_valid_session_id(session_id)
    history_store = _history_store_for_user(user)
    if history_store.get_session(normalized) is None:
        raise not_found("session not found")  # ❌ 报错
    return normalized
```

**修改后**:
```python
def _require_existing_session_for_query(user, session_id):
    if not session_id:
        return None
    normalized = _require_valid_session_id(session_id)
    history_store = _history_store_for_user(user)
    
    # ✅ Session不存在时自动创建
    if history_store.get_session(normalized) is None:
        try:
            created = history_store.create_session(session_id=normalized)
            logger.info(f"Auto-created session for user query")
            return created["session_id"]
        except Exception as e:
            raise bad_request(f"Failed to create session: {str(e)}")
    
    return normalized
```

### 📊 用户体验改进

**修改前**:
```
用户: 刷新页面后发送查询
系统: ❌ HTTP 404 "session not found"
前端: 需要显式调用 POST /sessions 创建session
用户: 😕 为什么我需要先创建会话？
```

**修改后**:
```
用户: 刷新页面后发送查询
系统: ✅ 自动创建session，正常返回查询结果
前端: 无需额外操作，对用户完全透明
用户: 😊 一切正常工作！
```

### 🎁 额外好处

1. **简化前端逻辑**: 前端不再需要检查session是否存在
2. **提升开发体验**: 测试时可以直接发送查询，无需先创建session
3. **容错性更强**: 即使session被误删，系统也能自动恢复

---

## 问题1: 密码修改后Session处理

### 🎯 修复目标
密码修改后如果token轮换失败，明确告知用户"密码已改，请重新登录"，而非让用户困惑。

### 📝 修改文件

#### 1. `app/api/routes/public/auth.py`
**修改**: `change_password()` 端点的响应逻辑

**修改前**:
```python
@router.post("/change-password")
def change_password(...):
    # ... 修改密码 ...
    new_session = auth_service.change_password(...)
    
    if new_session:
        _set_auth_cookie(response, new_session["token"])
    # ❌ 无论token轮换是否成功，都返回相同消息
    return {"ok": True, "message": "密码已成功更改"}
```

**修改后**:
```python
@router.post("/change-password")
def change_password(...):
    # ... 修改密码 ...
    new_session = auth_service.change_password(...)
    
    if new_session:
        # ✅ Token轮换成功
        _set_auth_cookie(response, new_session["token"])
        return {
            "ok": True,
            "message": "密码已成功更改",
            "token_rotated": True,
        }
    else:
        # ✅ 密码已改但token轮换失败，明确告知
        _clear_auth_cookie(response)
        return {
            "ok": True,
            "message": "密码已成功更改，请重新登录",
            "token_rotated": False,
            "requires_relogin": True,  # 前端可根据此字段跳转
            "reason": "为了安全，密码修改后需要重新认证",
        }
```

### 📊 用户体验改进

**修改前**:
```
用户: 修改密码
系统: "密码已成功更改"
实际: Token轮换失败，用户被登出
用户: 😕 我的密码改了吗？为什么被登出了？
```

**修改后 - 场景1（成功）**:
```
用户: 修改密码
系统: "密码已成功更改" + token_rotated=true
实际: Token轮换成功，用户保持登录
用户: 😊 一切正常！
```

**修改后 - 场景2（需要重登）**:
```
用户: 修改密码
系统: "密码已成功更改，请重新登录" + requires_relogin=true
前端: 显示友好提示，3秒后自动跳转到登录页
用户: 😊 虽然需要重登，但知道密码已改成功
```

### 🎁 额外改进

1. **审计日志更详细**: 区分 `password_changed_token_rotated` 和 `password_changed_token_rotation_failed`
2. **前端可自动化**: 根据 `requires_relogin` 字段自动跳转
3. **安全性提升**: 主动清除cookie，防止使用失效token

---

## 测试计划

### 问题2测试

```bash
# 测试1: 重复请求
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是Python?", "session_id": "test-session"}' &

# 立即发送第二个相同请求
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是Python?", "session_id": "test-session"}'

# 预期: 第二个请求返回 status="processing" 而非409

# 测试2: 状态轮询
curl http://localhost:8000/api/query/status/{request_id} \
  -H "Authorization: Bearer $TOKEN"

# 预期: 返回当前状态或最终结果
```

### 问题4测试

```bash
# 测试1: 不存在的session
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "测试", "session_id": "non-existent-session"}'

# 预期: 成功返回结果，session被自动创建

# 测试2: 验证session已创建
curl http://localhost:8000/api/sessions/non-existent-session \
  -H "Authorization: Bearer $TOKEN"

# 预期: 返回session详情，包含自动创建的消息
```

### 问题1测试

```bash
# 测试: 修改密码
curl -X POST http://localhost:8000/api/auth/change-password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "OldPass123!",
    "new_password": "NewPass456!"
  }'

# 预期响应 (成功轮换):
# {
#   "ok": true,
#   "message": "密码已成功更改",
#   "token_rotated": true
# }

# 预期响应 (需要重登):
# {
#   "ok": true,
#   "message": "密码已成功更改，请重新登录",
#   "token_rotated": false,
#   "requires_relogin": true,
#   "reason": "为了安全，密码修改后需要重新认证"
# }
```

---

## 前端集成指南

### 问题2: 处理重复请求响应

```typescript
// 前端查询处理
async function submitQuery(question: string) {
  const response = await fetch('/api/query', {
    method: 'POST',
    body: JSON.stringify({ question, session_id: currentSessionId }),
    headers: { 'Content-Type': 'application/json' }
  });

  const result = await response.json();

  // 检查是否需要轮询
  if (result.status === 'processing') {
    showMessage('查询正在处理中...');
    
    // 轮询状态
    const finalResult = await pollQueryStatus(result.request_id);
    return finalResult;
  }

  return result;
}

async function pollQueryStatus(requestId: string, maxAttempts = 10) {
  for (let i = 0; i < maxAttempts; i++) {
    await sleep(2000); // 每2秒轮询一次
    
    const status = await fetch(`/api/query/status/${requestId}`);
    const result = await status.json();
    
    if (result.status === 'completed') {
      return result;
    }
  }
  
  throw new Error('查询超时');
}
```

### 问题4: 简化Session管理

```typescript
// 前端代码简化：无需显式创建session
async function sendMessage(message: string) {
  // 直接发送查询，后端会自动创建session（如果需要）
  const response = await fetch('/api/query', {
    method: 'POST',
    body: JSON.stringify({
      question: message,
      session_id: currentSessionId || generateSessionId()
    })
  });
  
  return response.json();
  // 无需担心 "session not found" 错误！
}
```

### 问题1: 处理密码修改响应

```typescript
async function changePassword(oldPassword: string, newPassword: string) {
  const response = await fetch('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
  });

  const result = await response.json();

  if (result.requires_relogin) {
    // 密码已改但需要重新登录
    showNotification({
      type: 'success',
      title: '密码修改成功',
      message: result.message,
      duration: 5000
    });
    
    // 3秒后跳转到登录页
    setTimeout(() => {
      router.push('/login');
    }, 3000);
  } else {
    // 密码已改且保持登录
    showNotification({
      type: 'success',
      message: '密码修改成功'
    });
  }
}
```

---

## 监控指标

### 新增指标

```python
# 重复请求统计
runtime_metrics.inc("query_duplicate_total")  # 重复请求总数
runtime_metrics.inc("query_duplicate_served_from_cache")  # 从缓存命中
runtime_metrics.inc("query_duplicate_returned_processing")  # 返回处理中状态

# Session自动创建统计
runtime_metrics.inc("session_auto_created_total")  # 自动创建总数
runtime_metrics.inc("session_auto_create_failed")  # 创建失败

# 密码修改统计
runtime_metrics.inc("password_change_token_rotated")  # Token轮换成功
runtime_metrics.inc("password_change_needs_reauth")  # 需要重新认证
```

### Grafana仪表盘

```promql
# 重复请求率
rate(query_duplicate_total[5m]) / rate(query_total[5m])

# Session自动创建成功率
rate(session_auto_created_total[5m]) / 
  (rate(session_auto_created_total[5m]) + rate(session_auto_create_failed[5m]))

# 密码修改需要重新认证的比例
rate(password_change_needs_reauth[1h]) / rate(password_change_total[1h])
```

---

## 回滚计划

如果发现问题，可以快速回滚：

### 回滚步骤

```bash
# 1. 恢复问题2的修改（如果有问题）
git checkout HEAD -- app/api/query/request.py
git checkout HEAD -- app/api/schemas/http.py
git checkout HEAD -- app/api/transport/errors.py
rm app/api/routes/public/query_status.py

# 2. 恢复问题4的修改（如果有问题）
git checkout HEAD -- app/api/deps/sessions.py

# 3. 恢复问题1的修改（如果有问题）
git checkout HEAD -- app/api/routes/public/auth.py

# 4. 重启服务
sudo systemctl restart querymind-api
```

### 验证回滚

```bash
# 验证重复请求返回409
curl -X POST http://localhost:8000/api/query ... 
# 应返回 409 Conflict

# 验证session必须存在
curl -X POST http://localhost:8000/api/query \
  -d '{"session_id": "non-existent"}' ...
# 应返回 404 Not Found
```

---

## 后续优化建议

### 短期（1-2周）
- [ ] 添加 `/query/status/{request_id}` 的单元测试
- [ ] 前端集成轮询逻辑和进度显示
- [ ] 监控重复请求的频率和原因

### 中期（1个月）
- [ ] 考虑使用WebSocket替代轮询
- [ ] 优化Session自动创建的性能
- [ ] 添加Session创建失败的详细错误日志

### 长期（3个月）
- [ ] 实现请求去重的分布式锁（Redis）
- [ ] Session持久化到数据库（当前是文件系统）
- [ ] 支持跨设备Session同步

---

## 总结

✅ **完成修复的核心问题**:
1. 重复请求不再返回409冲突，提供处理中状态
2. Session自动创建，用户体验更连贯
3. 密码修改后明确告知是否需要重新登录

📈 **预期效果**:
- 用户投诉减少 50%+
- 支持工单减少（无需解释为何被登出）
- 前端代码更简洁（减少错误处理逻辑）

🎯 **下一步**:
执行测试计划 → 前端集成 → 灰度发布 → 全量上线
