# 前端刷新问题排查指南

## ✅ 后端状态
经过测试，后端 API 和数据刷新功能完全正常：
- ✅ 空状态处理正常
- ✅ 数据添加后刷新正常
- ✅ 多次连续刷新正常
- ✅ 错误数据处理正常
- ✅ 所有字段格式正确

## 🔍 可能的前端问题

### 1. 浏览器控制台错误

打开浏览器开发者工具 (F12)，检查：

**Console 标签**：
```
查找以下错误：
- TypeError: Cannot read property 'xxx' of undefined
- Network error
- CORS error
- 401 Unauthorized
- 500 Internal Server Error
```

**Network 标签**：
```
检查 API 请求：
1. 找到 /api/v1/admin/agent-quality/stats 请求
2. 查看状态码（应该是 200）
3. 查看响应数据
4. 查看请求头（Authorization token）
```

### 2. 常见问题及解决方案

#### 问题 A: 401 未授权错误

**症状**：
- 刷新时提示 "Authentication required"
- Network 标签显示 401 状态码

**解决方案**：
```typescript
// 检查是否已登录
1. 访问 /login 重新登录
2. 确保是管理员账号
3. 清除浏览器缓存和 cookies
4. 重新登录
```

#### 问题 B: CORS 错误

**症状**：
- Console 显示 CORS policy 错误
- 请求被浏览器阻止

**解决方案**：
```bash
# 检查后端 CORS 配置
# 确保前端地址在允许列表中
# app/core/config.py 中的 CORS_ORIGINS
```

#### 问题 C: 数据格式错误

**症状**：
- Console 显示 undefined 错误
- 图表不显示

**解决方案**：
```typescript
// 检查 API 响应格式
// 在 Console 中运行：
fetch('/api/v1/admin/agent-quality/stats', {
  headers: { 'Authorization': 'Bearer ' + yourToken }
})
.then(r => r.json())
.then(data => console.log(data))
```

#### 问题 D: 自动刷新不工作

**症状**：
- 勾选自动刷新但不更新
- 30秒后没有新数据

**可能原因**：
```typescript
// useEffect 依赖问题（已修复）
// 检查以下内容：

1. autoRefresh 状态是否正确切换
2. setInterval 是否正确清理
3. 组件是否卸载导致刷新停止
```

**修复内容**：
- ✅ 已添加错误日志
- ✅ 已修复空值处理
- ✅ 已改进 useEffect 清理逻辑

#### 问题 E: 图表不渲染

**症状**：
- 数据显示但图表空白
- Recharts 组件不显示

**解决方案**：
```typescript
// 检查数据格式
console.log("Agents:", stats?.agents);
console.log("Timeline:", stats?.timeline);
console.log("Error Distribution:", stats?.error_distribution);

// 确保数据不是空数组
if (stats?.agents?.length === 0) {
  // 这是正常的，说明没有数据
}
```

### 3. 调试步骤

#### 步骤 1: 确认后端运行
```bash
# 检查后端状态
curl http://localhost:8000/health

# 应该返回：
{"status": "ok", ...}
```

#### 步骤 2: 测试 API 端点
```bash
# 获取统计数据（需要替换 TOKEN）
curl http://localhost:8000/api/v1/admin/agent-quality/stats \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# 应该返回完整的 JSON 数据
```

#### 步骤 3: 检查前端构建
```bash
cd frontend
npm run dev

# 确保没有编译错误
```

#### 步骤 4: 清除缓存
```
1. 打开开发者工具 (F12)
2. 右键点击刷新按钮
3. 选择 "清空缓存并硬性重新加载"
4. 或使用 Ctrl+Shift+Delete 清除浏览器数据
```

### 4. 前端代码检查清单

✅ **已修复的问题**：

1. **useEffect 依赖**
   ```typescript
   // 修复前：可能导致无限循环或不刷新
   useEffect(() => {
     // ...
   }, [autoRefresh]); // ✅ 正确的依赖

2. **空值处理**
   ```typescript
   // 修复前：
   {new Date(agent.last_execution).toLocaleString()}
   
   // 修复后：✅
   {agent.last_execution ? new Date(agent.last_execution).toLocaleString() : "N/A"}
   ```

3. **错误日志**
   ```typescript
   // 修复后：✅ 添加了详细的错误日志
   console.error("Failed to fetch agent quality stats:", err);
   ```

### 5. 实时调试工具

在浏览器 Console 中运行以下命令：

```javascript
// 1. 检查组件状态（需要 React DevTools）
// 选择 AdminAgentQualityDashboard 组件
// 查看 stats, loading, error, autoRefresh 状态

// 2. 手动触发刷新
// 在 Console 中运行：
fetch('/api/v1/admin/agent-quality/stats', {
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token') // 或实际的 token 存储位置
  }
})
.then(r => r.json())
.then(data => {
  console.log('Stats:', data);
  console.log('Total Agents:', data.summary.total_agents);
  console.log('Total Executions:', data.summary.total_executions);
})
.catch(err => console.error('Error:', err));

// 3. 监控刷新间隔
let refreshCount = 0;
const originalFetch = window.fetch;
window.fetch = function(...args) {
  if (args[0].includes('agent-quality/stats')) {
    refreshCount++;
    console.log(`🔄 Refresh #${refreshCount} at ${new Date().toLocaleTimeString()}`);
  }
  return originalFetch.apply(this, args);
};

// 4. 检查自动刷新
setTimeout(() => {
  console.log(`Total refreshes in 60 seconds: ${refreshCount}`);
  console.log(`Expected: ~2 refreshes (30s interval)`);
}, 60000);
```

### 6. 常见解决方案总结

| 问题 | 快速解决 |
|------|---------|
| 401 错误 | 重新登录管理员账号 |
| CORS 错误 | 检查后端 CORS 配置 |
| 数据不显示 | 先执行查询生成数据 |
| 图表空白 | 检查是否有执行数据 |
| 自动刷新不工作 | 取消勾选再勾选 |
| 页面卡住 | 清除浏览器缓存 |

### 7. 如果问题仍然存在

**收集以下信息**：

1. **浏览器 Console 截图**（包含错误信息）
2. **Network 标签截图**（API 请求和响应）
3. **问题重现步骤**
4. **浏览器版本和操作系统**

**临时解决方案**：

```typescript
// 如果自动刷新有问题，可以使用手动刷新按钮
// 点击 "刷新" 按钮手动更新数据
```

### 8. 后端日志检查

如果前端显示错误，检查后端日志：

```bash
# 查看后端日志
# 日志文件通常在项目根目录或 logs/ 文件夹

# 查找相关错误
grep "agent-quality" logs/*.log
grep "ERROR" logs/*.log
grep "Exception" logs/*.log
```

### 9. 测试用例

运行以下测试确保系统正常：

```bash
# 1. 后端测试
cd c:/Users/pocheang/Desktop/llm/multi_agent_rag_local_v4
conda activate rag-local
pytest tests/test_admin_agent_quality_api.py -v

# 2. 后端验证
python verify_agent_quality.py

# 3. 刷新调试
python debug_refresh.py
```

## 📞 获取帮助

如果以上步骤都无法解决问题，请提供：

1. 浏览器控制台的完整错误信息
2. Network 标签中失败请求的详细信息
3. 后端日志中的相关错误
4. 问题的具体表现（例如：点击刷新后发生什么）

---

**最后更新**: 2026-07-02  
**状态**: 后端功能正常，前端已优化
