# 🔐 安全方案 - 使用JWT认证（需要重启后端）

**方案**: JWT认证（更安全）  
**需要**: 重启后端服务器  
**时间**: 约1分钟

---

## ✅ 已完成的修改

### 1. 后端修改 ✅

**文件**: `app/api/auth.py`

修改了4个权限函数，从只支持API Key改为同时支持JWT和API Key：

```python
✅ require_admin: Depends(get_current_user)
✅ require_manager: Depends(get_current_user)
✅ require_viewer: Depends(get_current_user)
✅ require_role: Depends(get_current_user)
```

### 2. 前端修改 ✅

**文件**: `AdminWebActivityDashboard.tsx`

使用JWT认证（通过cookie）：

```tsx
credentials: 'include'  // 自动发送JWT cookie
```

### 3. 前端构建 🔄

正在构建中...

---

## 🚀 重启后端服务器

### 方法1: 如果使用了 --reload 模式

后端应该**自动检测到auth.py的修改并重启**。

**查看后端终端**，应该看到：
```
Watching for file changes...
Detected file change in: app/api/auth.py
Reloading...
Application startup complete.
```

✅ 如果看到以上信息，说明**已自动重启，无需手动操作**！

### 方法2: 手动重启

如果后端没有自动重启：

**步骤**:

1. **停止后端** (在后端终端按 `Ctrl+C`)

2. **重新启动**:
   ```bash
   cd c:/Users/pocheang/Desktop/llm/multi_agent_rag_local_v4
   uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **等待启动完成**，看到:
   ```
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

---

## ✅ 验证步骤

### 1. 确认后端已重启

```bash
# 测试健康检查
curl http://localhost:8000/api/v1/admin/web-activity/health

# 应该返回:
# {"status":"healthy",...}
```

### 2. 等待前端构建完成

前端正在构建中，完成后会通知您。

### 3. 刷新浏览器

```
http://localhost:5173
Ctrl+Shift+R (硬刷新)
```

### 4. 重新登录（如需要）

```
Username: admin
Password: admin123
```

### 5. 访问Dashboard

```
Admin → Web Activity
```

### 6. 验证成功

**应该看到**:
- ✅ 统计卡片显示数据
- ✅ 图表正常渲染
- ✅ 不显示401错误

---

## 🔐 为什么选择JWT认证

### 安全优势

| 特性 | API Key（硬编码） | JWT认证 |
|------|------------------|---------|
| **暴露风险** | 🔴 高 - 在代码中可见 | 🟢 低 - 存储在httpOnly cookie |
| **可撤销性** | 🔴 无法撤销 | 🟢 可以撤销 |
| **有效期** | ⚠️ 永久有效 | 🟢 可设置过期时间 |
| **跟踪用户** | ⚠️ 共享同一Key | 🟢 每个用户独立token |
| **最佳实践** | ❌ 不推荐 | ✅ 推荐 |

### JWT的优势

1. ✅ **安全存储** - cookie使用httpOnly标志，JavaScript无法访问
2. ✅ **自动过期** - token有有效期，定期需要重新登录
3. ✅ **用户追踪** - 每个用户有独立的token
4. ✅ **可撤销** - 可以让特定token失效
5. ✅ **行业标准** - 符合安全最佳实践

---

## 🎯 认证流程

### 完整流程

```
1. 用户登录
   POST /auth/login
   Body: {username: "admin", password: "admin123"}
   ↓
2. 后端验证密码
   验证成功 ✓
   ↓
3. 生成JWT token
   token = jwt.encode({user_id, role, exp}, secret)
   ↓
4. 设置httpOnly cookie
   Set-Cookie: token=...; HttpOnly; Path=/; SameSite=Lax
   ↓
5. 浏览器自动存储cookie
   ↓
6. 访问Dashboard
   fetch('/api/...', {credentials: 'include'})
   ↓
7. 浏览器自动发送cookie
   Cookie: token=...
   ↓
8. 后端验证JWT
   get_current_user() → 解码token → 验证签名 → 检查过期
   ↓
9. require_viewer() 检查权限
   ↓
10. 返回数据 ✓
```

---

## 📋 检查清单

**后端**:
- [ ] auth.py已修改（require_* 函数使用get_current_user）
- [ ] 后端服务器已重启（自动或手动）
- [ ] 健康检查通过

**前端**:
- [ ] Dashboard使用credentials: 'include'
- [ ] 前端构建完成
- [ ] 浏览器已刷新

**测试**:
- [ ] 可以登录
- [ ] Dashboard不显示401错误
- [ ] 数据正常显示

---

## ⏱️ 预计时间

- **后端自动重启**: 5-10秒
- **或手动重启**: 30秒
- **前端构建**: 30-60秒
- **测试验证**: 1分钟

**总计**: 约1-2分钟

---

## 🎉 完成后的效果

### Dashboard正常显示

```
┌────────────────────────────────────┐
│  Web Search Activity     🔄 刷新   │
├────────────────────────────────────┤
│  📊 统计卡片                       │
│  ┌──────┬──────┬──────┬──────┐   │
│  │🔍 1  │✅100%│👥 1  │🌐 0  │   │
│  └──────┴──────┴──────┴──────┘   │
├────────────────────────────────────┤
│  📈 图表和数据正常显示            │
└────────────────────────────────────┘
```

### 安全保障

- 🔐 JWT token存储在httpOnly cookie中
- 🔐 前端代码中没有硬编码的密钥
- 🔐 Token会自动过期（需要重新登录）
- 🔐 每个用户有独立的token

---

## 📝 重要提醒

**必须重启后端服务器！**

修改了 `app/api/auth.py`，这是认证核心模块。

✅ **检查后端是否使用 --reload 模式**
- 如果是，应该自动重启
- 如果不是，需要手动重启

✅ **确认重启成功**
```bash
curl http://localhost:8000/api/v1/admin/web-activity/health
```

---

**方案**: JWT认证（安全）  
**状态**: 等待后端重启 + 前端构建  
**下一步**: 重启后端，等待前端构建完成
