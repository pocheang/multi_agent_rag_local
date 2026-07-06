# 🔧 Web Activity Dashboard - 故障排查和修复指南

**更新时间**: 2026-06-30  
**问题**: API 401认证错误 + 错误日志显示问题

---

## 🐛 发现的问题

### 问题1: API 401 认证错误 ❌

**症状**:
```
Error Loading Data
API Error: 401
```

**原因**:
- Dashboard使用`localStorage.getItem("api_key")`获取API Key
- 但Admin用户登录时使用的是JWT认证，不是API Key
- API端点需要`Depends(require_viewer)`认证

**解决方案**: ✅
```tsx
// 修改前
headers: {
  "X-API-Key": localStorage.getItem("api_key") || ""
}

// 修改后
credentials: 'include'  // 使用JWT cookie认证
```

---

### 问题2: 错误堆栈显示在表格中 ❌

**症状**:
- 在"最近产错误选"表格中显示大量Python错误堆栈
- 堆栈信息过长，不适合表格显示

**原因**:
- 这不是Web Activity的问题
- 是系统日志表格显示的后端错误信息

**不需要在Web Activity中修复**

---

## ✅ 已实施的修复

### 1. 修改认证方式

**文件**: `frontend/src/pages/admin/AdminWebActivityDashboard.tsx`

**修改内容**:
```tsx
// fetchStats函数
const response = await fetch(
  `/api/v1/admin/web-activity/stats?${params}`,
  {
    credentials: 'include', // 使用JWT认证
  }
);

// fetchAlerts函数
const response = await fetch(
  `/api/v1/admin/web-activity/alerts?hours=24`,
  {
    credentials: 'include', // 使用JWT认证
  }
);
```

### 2. 改进错误提示

```tsx
if (response.status === 401) {
  setError("Authentication required. Please log in again.");
} else {
  setError(`API Error: ${response.status} - ${response.statusText}`);
}
```

---

## 🔍 认证流程说明

### Admin登录流程

```
1. 用户在登录页输入: admin / admin123
   ↓
2. 前端发送POST /auth/login
   ↓
3. 后端验证密码
   ↓
4. 后端返回JWT token (存储在httpOnly cookie中)
   ↓
5. 浏览器自动保存cookie
   ↓
6. 后续请求自动携带cookie (credentials: 'include')
```

### Web Activity API认证

```
用户访问Dashboard
   ↓
fetch('/api/v1/admin/web-activity/stats', {
  credentials: 'include'  // 自动发送JWT cookie
})
   ↓
Vite代理转发到后端 (127.0.0.1:8000)
   ↓
后端验证JWT token
   ↓
require_viewer() 检查权限
   ↓
返回数据
```

---

## 🛠️ Vite代理配置

### 当前配置

**文件**: `frontend/vite.config.mjs`

```js
proxy: {
  "/api": createBackendProxy(),
  // ...
}

function createBackendProxy(rewriteAppBase = false) {
  return {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
    timeout: 600000,
    proxyTimeout: 600000,
    rewrite: rewriteAppBase ? (path) => path.replace(/^\/app/, "") : undefined,
  };
}
```

**工作原理**:
- 前端请求 `/api/v1/admin/web-activity/stats`
- Vite代理转发到 `http://127.0.0.1:8000/api/v1/admin/web-activity/stats`
- Cookie自动随请求发送

---

## 🧪 测试步骤

### 1. 检查登录状态

在浏览器控制台执行:
```javascript
// 检查是否有JWT cookie
document.cookie

// 应该看到类似：
// "token=eyJ..."
```

### 2. 手动测试API

在浏览器控制台执行:
```javascript
fetch('/api/v1/admin/web-activity/stats', {
  credentials: 'include'
})
.then(r => r.json())
.then(d => console.log(d))
```

**预期结果**:
```json
{
  "summary": {
    "total_searches": 1,
    "success_rate": 100.0,
    ...
  },
  "top_websites": [],
  "top_users": [...]
}
```

### 3. 检查网络请求

1. 打开浏览器开发者工具
2. 切换到 Network 标签
3. 刷新Dashboard页面
4. 找到 `/api/v1/admin/web-activity/stats` 请求
5. 检查:
   - Request Headers 是否包含 Cookie
   - Response Status 应该是 200
   - Response 包含数据

---

## 🔧 如果仍然401错误

### 检查1: 确认已登录

```
访问: http://localhost:5173
如果自动跳转到登录页，说明未登录
登录: admin / admin123
```

### 检查2: 检查后端API端点

```bash
# 使用API Key直接测试（绕过JWT）
curl -H "X-API-Key: admin-api-key-12345" \
  http://localhost:8000/api/v1/admin/web-activity/stats

# 应该返回数据
```

### 检查3: 查看后端日志

```bash
# 查看FastAPI日志
# 应该看到请求日志和任何认证错误
```

### 检查4: 清除浏览器缓存

```
1. 打开开发者工具
2. Application → Storage → Clear site data
3. 重新登录
4. 再次访问Dashboard
```

---

## 📝 备用方案：使用API Key

如果JWT认证仍有问题，可以临时使用API Key：

### 方案1: 在登录后设置API Key

**修改**: `frontend/src/pages/LoginPage.tsx` (登录成功后)

```tsx
// 登录成功后
localStorage.setItem('api_key', 'admin-api-key-12345');
```

### 方案2: 在Dashboard初始化时设置

**修改**: `AdminWebActivityDashboard.tsx`

```tsx
useEffect(() => {
  // 确保有API Key
  if (!localStorage.getItem('api_key')) {
    localStorage.setItem('api_key', 'admin-api-key-12345');
  }
  fetchStats();
  fetchAlerts();
}, []);
```

---

## ✅ 验证修复

### 步骤

1. **重新构建前端**
   ```bash
   cd frontend
   npm run build
   ```

2. **刷新浏览器**
   ```
   Ctrl+Shift+R (硬刷新)
   ```

3. **访问Dashboard**
   ```
   http://localhost:5173
   → 登录
   → Admin → Web Activity
   ```

4. **验证结果**
   - ✅ 不再显示401错误
   - ✅ 显示统计数据
   - ✅ 图表正常渲染

---

## 🎯 预期效果

### 修复后应该看到

```
┌─────────────────────────────────────┐
│  Web Search Activity     🔄 刷新    │
├─────────────────────────────────────┤
│  [时间范围▼] [用户筛选____]        │
├─────────────────────────────────────┤
│  📊 统计卡片                        │
│  ┌──────┬──────┬──────┬──────┐    │
│  │ 1次  │ 100% │  1人 │  0站 │    │
│  └──────┴──────┴──────┴──────┘    │
├─────────────────────────────────────┤
│  📈 24小时活动图表                 │
├─────────────────────────────────────┤
│  🌐 Top网站  │  👥 Top用户        │
└─────────────────────────────────────┘
```

**而不是**:
```
❌ Error Loading Data
API Error: 401
[ Retry ]
```

---

## 📚 相关文档

- [前端访问指南](./FINAL_ACCESS_GUIDE.md)
- [UI优化指南](./UI_OPTIMIZATION_GUIDE.md)
- [API文档](http://localhost:8000/docs)

---

## 🚀 快速修复命令

```bash
# 1. 确保后端运行
curl http://localhost:8000/api/v1/admin/web-activity/health

# 2. 重新构建前端
cd frontend && npm run build

# 3. 访问并测试
# 浏览器: http://localhost:5173
```

---

**修复完成时间**: 2026-06-30  
**状态**: ✅ 认证方式已修正  
**下一步**: 重启前端开发服务器并测试
