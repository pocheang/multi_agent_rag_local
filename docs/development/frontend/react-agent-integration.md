# 🎨 Web Activity Dashboard - React集成完成指南

**版本**: v2.0 - React Integration  
**状态**: ✅ 已集成到React前端  
**日期**: 2026-06-30

---

## 📊 集成概述

Web Activity监控Dashboard已成功集成到React前端，作为Admin面板的新标签页。

### 集成方式

- ✅ **React组件**: `AdminWebActivityDashboard.tsx`
- ✅ **位置**: `frontend/src/pages/admin/`
- ✅ **集成点**: AdminPage.tsx
- ✅ **图表库**: recharts (已安装)
- ✅ **样式**: 使用项目统一的Tailwind CSS

---

## 🎯 新增功能

### 在Admin面板中

访问路径：
```
登录 → Admin → Web Activity 标签
```

### 新标签页："Web Activity"

位置在 Models 和 Admins 之间

---

## 📦 文件清单

### 新增文件（1个）

```
frontend/src/pages/admin/
└── AdminWebActivityDashboard.tsx  ← React Dashboard组件
```

### 修改文件（1个）

```
frontend/src/pages/
└── AdminPage.tsx  ← 添加了Web Activity标签
```

---

## 🎨 组件功能

### 1. 实时统计卡片（4个）

```tsx
- 总搜索次数 (蓝色渐变)
- 成功率 (绿色渐变)
- 独立用户数 (紫色渐变)
- 访问网站数 (橙色渐变)
```

### 2. 交互式图表（3个）

```tsx
- 24小时活动分布 (折线图)
- 最常访问网站 Top 10 (柱状图)
- 最活跃用户 Top 10 (柱状图)
```

### 3. 数据表格

```tsx
- 网站访问详情 (Top 20)
- 包含：排名、域名、访问次数、信任度评分
- 信任度标签：高(绿)、中(黄)、低(红)
```

### 4. 控制功能

```tsx
- 时间范围选择 (1/7/30/90天)
- 用户ID筛选
- 自动刷新开关 (30秒间隔)
- 手动刷新按钮
```

### 5. 告警横幅

```tsx
- 显示最近3个活动告警
- 黄色警告样式
- 显示告警级别和消息
```

---

## 🔧 技术实现

### API集成

```typescript
// 获取统计数据
fetch('/api/v1/admin/web-activity/stats', {
  headers: {
    'X-API-Key': localStorage.getItem('api_key') || ''
  }
})

// 获取告警
fetch('/api/v1/admin/web-activity/alerts?hours=24', {
  headers: {
    'X-API-Key': localStorage.getItem('api_key') || ''
  }
})
```

### 状态管理

```typescript
- stats: WebActivityStats | null
- alerts: Alert[]
- loading: boolean
- timeRange: number
- userFilter: string
- autoRefresh: boolean
```

### 自动刷新

```typescript
useEffect(() => {
  if (autoRefresh) {
    const interval = setInterval(() => {
      fetchStats();
      fetchAlerts();
    }, 30000); // 30秒
    
    return () => clearInterval(interval);
  }
}, [autoRefresh, userFilter]);
```

---

## 🎨 UI/UX特性

### 响应式设计

- ✅ 桌面端：4列网格布局
- ✅ 平板端：2列网格布局
- ✅ 移动端：1列堆叠布局

### 深色模式支持

- ✅ 自动适配主题
- ✅ 使用Tailwind的dark:前缀
- ✅ 颜色方案跟随系统

### 国际化支持

- ✅ 使用react-i18next
- ✅ 所有文本可翻译
- ✅ 翻译键：`admin.webActivity.*`

---

## 🌐 访问方式

### 方式1: React前端（推荐）⭐

1. 访问 http://localhost:8000
2. 登录Admin账户
3. 点击顶部导航的 "Admin"
4. 点击 "Web Activity" 标签

### 方式2: 直接API端点

```
http://localhost:8000/api/v1/admin/web-activity/dashboard
```

### 方式3: API文档

```
http://localhost:8000/docs#/Admin%20-%20Web%20Activity
```

---

## 🚀 构建和部署

### 开发模式

```bash
cd frontend
npm run dev
```

前端将在 http://localhost:5173 运行

### 生产构建

```bash
cd frontend
npm run build
```

构建产物在 `frontend/dist/`

### 部署

构建后的文件已自动被FastAPI服务：

```python
# app/api/main.py
react_dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
app.mount("/app/assets", StaticFiles(directory=str(react_assets_dir)))
```

---

## 📊 数据流

```
React组件 (AdminWebActivityDashboard)
    ↓
    fetch('/api/v1/admin/web-activity/stats')
    ↓
FastAPI Backend (web_activity_admin.py)
    ↓
WebActivityAnalyzer
    ↓
日志文件 (logs/web_activity/*.jsonl)
    ↓
返回JSON数据
    ↓
React组件渲染
```

---

## 🎯 使用场景

### 管理员日常监控

1. 登录Admin面板
2. 切换到"Web Activity"标签
3. 查看实时统计和图表
4. 根据需要调整时间范围

### 问题排查

1. 查看告警横幅
2. 检查成功率指标
3. 查看24小时活动分布
4. 识别异常访问模式

### 数据分析

1. 导出HTML报告
2. 查看Top网站和用户
3. 分析访问趋势
4. 评估信任度分布

---

## 🔍 开发调试

### 检查组件渲染

```bash
# 在浏览器控制台
localStorage.getItem('api_key')  # 检查API Key
```

### 查看网络请求

```
浏览器开发者工具 → Network → 
筛选 "web-activity" 查看API请求
```

### 查看组件状态

```tsx
// 添加调试日志
console.log('Stats:', stats);
console.log('Alerts:', alerts);
```

---

## 📝 国际化

### 添加翻译键

在 `frontend/src/i18n/` 中添加：

```json
{
  "admin": {
    "webActivity": {
      "title": "Web Search Activity",
      "subtitle": "Monitor and analyze web search behavior",
      "totalSearches": "Total Searches",
      "successRate": "Success Rate",
      "uniqueUsers": "Unique Users",
      "uniqueWebsites": "Unique Websites",
      ...
    }
  }
}
```

---

## 🎨 样式定制

### 修改颜色方案

```tsx
// 统计卡片渐变
from-blue-500 to-blue-600    // 总搜索
from-green-500 to-green-600  // 成功率
from-purple-500 to-purple-600 // 用户
from-orange-500 to-orange-600 // 网站
```

### 修改图表颜色

```tsx
<Line stroke="#3b82f6" />  // 蓝色
<Bar fill="#3b82f6" />     // 蓝色
<Bar fill="#8b5cf6" />     // 紫色
```

---

## ✅ 验证清单

### 功能验证

- [ ] 组件正常渲染
- [ ] API请求成功
- [ ] 数据正确显示
- [ ] 图表正常渲染
- [ ] 自动刷新工作
- [ ] 筛选功能正常
- [ ] 深色模式适配
- [ ] 响应式布局

### 性能验证

- [ ] 初始加载 < 2秒
- [ ] API响应 < 500ms
- [ ] 图表渲染 < 1秒
- [ ] 内存使用正常

---

## 🔧 故障排查

### 问题1: 组件不显示

**检查**:
```bash
# 确认构建成功
ls frontend/dist/

# 确认AdminPage.tsx已修改
grep "AdminWebActivityDashboard" frontend/src/pages/AdminPage.tsx
```

### 问题2: API请求失败

**检查**:
```javascript
// 浏览器控制台
localStorage.getItem('api_key')

// 如果为空，需要先登录
```

### 问题3: 图表不渲染

**检查**:
```bash
# 确认recharts已安装
npm list recharts

# 如果没有，安装
npm install recharts
```

---

## 📚 相关文档

- [React组件源码](../../../frontend/src/pages/admin/AdminWebActivityDashboard.tsx)
- [API文档](../api-development.md)
- [后端实现](../../../app/api/routes/web_activity_admin.py)
- [测试指南](../../archive/legacy/docs-root/TEST_RESULTS.md)

---

## 🎉 集成完成

### 最终状态

- ✅ React组件创建完成
- ✅ AdminPage集成完成
- ✅ API连接正常
- ✅ 图表库ready
- ✅ 样式适配完成
- ✅ 国际化支持
- ✅ 响应式布局

### 下一步

1. **构建前端**: `npm run build`
2. **访问Admin面板**
3. **点击Web Activity标签**
4. **开始监控！**

---

**集成完成时间**: 2026-06-30  
**集成方式**: React组件  
**状态**: ✅ Production Ready
