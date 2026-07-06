# ⚠️ 重要：需要重启后端服务器

**修改时间**: 2026-06-30  
**修改内容**: 后端认证系统支持JWT

---

## 🔧 已完成的修改

### 修改文件
**文件**: `app/api/auth.py`

### 修改内容

将所有权限检查函数从只支持API Key改为同时支持JWT和API Key：

```python
# ✅ 修改1: require_admin
async def require_admin(user: User = Depends(get_current_user)) -> User:

# ✅ 修改2: require_manager  
async def require_manager(user: User = Depends(get_current_user)) -> User:

# ✅ 修改3: require_viewer
async def require_viewer(user: User = Depends(get_current_user)) -> User:

# ✅ 修改4: require_role
async def check_role(user: User = Depends(get_current_user)):
```

**关键点**: `get_current_user` 函数支持两种认证方式：
1. JWT Token（来自Web登录）
2. API Key（来自直接API调用）

---

## 🚀 需要重启后端

### 方法1: 如果使用--reload模式

如果后端是用 `uvicorn app.api.main:app --reload` 启动的，它应该会**自动重启**。

**等待几秒**，然后刷新浏览器测试。

### 方法2: 手动重启

如果后端没有自动重启，手动重启：

```bash
# 1. 找到FastAPI进程
ps aux | grep uvicorn

# 2. 停止进程
# Windows PowerShell:
Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Stop-Process

# 或直接 Ctrl+C 停止

# 3. 重新启动
cd c:/Users/pocheang/Desktop/llm/multi_agent_rag_local_v4
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ✅ 验证后端重启成功

### 测试API

```bash
# 1. 健康检查
curl http://localhost:8000/api/v1/admin/web-activity/health

# 应该返回:
# {"status":"healthy",...}
```

---

## 🌐 验证前端访问

### 步骤

1. **确认后端已重启**
   ```
   查看后端终端输出
   应该看到: "Application startup complete"
   ```

2. **刷新浏览器**
   ```
   http://localhost:5173
   Ctrl+Shift+R (硬刷新)
   ```

3. **重新登录（如需要）**
   ```
   Username: admin
   Password: admin123
   ```

4. **访问Dashboard**
   ```
   Admin → Web Activity
   ```

5. **验证结果**
   - ✅ 不再显示 "Authentication required. Please log in again."
   - ✅ 显示统计数据
   - ✅ 图表正常渲染

---

## 🔍 如果仍然有问题

### 检查1: 后端是否真的重启了

```bash
# 查看后端日志
# 应该看到最新的启动时间
```

### 检查2: JWT Cookie是否存在

在浏览器控制台执行：
```javascript
document.cookie
// 应该看到: token=eyJ...
```

如果没有cookie，重新登录。

### 检查3: 测试API直接调用

在浏览器控制台执行：
```javascript
fetch('/api/v1/admin/web-activity/stats', {
  credentials: 'include'
})
.then(r => r.json())
.then(d => console.log(d))
```

**预期**: 返回统计数据，不是401错误

---

## 📝 修改总结

### 修改前 ❌
```python
require_viewer(user: User = Depends(get_current_user_api_key))
# 只支持API Key认证
# Web登录的JWT token无法使用
```

### 修改后 ✅
```python
require_viewer(user: User = Depends(get_current_user))
# 同时支持:
# 1. JWT Token (Web登录)
# 2. API Key (直接API调用)
```

---

## 🎯 认证流程

### 现在的完整流程

```
用户登录 (admin/admin123)
    ↓
后端返回JWT token (存储在cookie中)
    ↓
用户访问Web Activity Dashboard
    ↓
前端发送请求 (credentials: 'include')
    ↓
浏览器自动携带JWT cookie
    ↓
Vite代理转发请求
    ↓
FastAPI后端接收请求
    ↓
get_current_user() 检查认证
    ├─→ 尝试JWT token ✓
    └─→ (备用: 尝试API Key)
    ↓
require_viewer() 检查权限 ✓
    ↓
返回数据
    ↓
Dashboard显示统计信息 ✓
```

---

## ⏱️ 预计时间

- **自动重启**: 5-10秒
- **手动重启**: 30秒
- **测试验证**: 1分钟

**总计**: 约2分钟即可完成

---

## 🚨 重要提醒

**必须重启后端服务器才能生效！**

修改了 `app/api/auth.py` 文件，这是核心认证模块。

如果使用 `--reload` 模式启动，应该会自动重启。
否则需要手动重启。

---

**修改完成**: 2026-06-30  
**影响范围**: 所有使用require_viewer/require_manager/require_admin的API  
**下一步**: 重启后端服务器！
