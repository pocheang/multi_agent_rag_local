# 🤖 Agent质量监控面板 - 完整文档

## ✅ 新增功能

### Agent质量监控仪表板
**文件**: `AdminAgentQualityDashboard.tsx`

这是一个全新的监控面板，专门用于监控所有RAG Agent的运行质量和性能！

---

## 📊 核心功能

### 1. KPI指标卡片 ✅
显示关键指标：
- **Agent总数**: 系统中配置的所有Agent数量
- **活跃Agent**: 最近有执行记录的Agent数量
- **总执行次数**: 所有Agent的总执行次数
- **成功率**: 整体成功率（带颜色编码）
  - ≥90%: 绿色 (优秀)
  - 70-90%: 黄色 (良好)
  - <70%: 红色 (需要关注)
- **平均响应时间**: 所有Agent的平均执行时间

### 2. 时间线图表 ✅
- **成功/失败时间线**: 折线图
  - 绿色线: 成功次数趋势
  - 红色线: 失败次数趋势
  - 可以看出Agent质量变化趋势

### 3. 错误分布饼图 ✅
- 显示不同类型错误的分布
- 彩色分区，易于识别
- 帮助定位主要问题

### 4. Agent性能详情表 ✅
每个Agent的详细数据：
- Agent名称
- 执行次数
- 成功率（带颜色徽章）
- 平均执行时间
- 平均Token消耗
- 最后执行时间
- 状态（Excellent/Good/Poor）

### 5. Agent健康概览 ✅
- **执行次数统计**: 横向柱状图
  - 显示哪些Agent使用最频繁
- **平均执行时间统计**: 横向柱状图
  - 显示哪些Agent响应最慢

### 6. 过滤功能 ✅
- 下拉菜单选择特定Agent
- 查看单个Agent的详细数据
- "所有Agent"选项查看整体情况

### 7. 数据导出 ✅
- CSV导出：导出所有Agent性能数据
- JSON导出：原始数据格式

### 8. 自动刷新 ✅
- 每30秒自动更新数据
- 可以手动开关

---

## 🎨 监控的Agent列表

根据项目架构，系统包含以下Agent：

### 核心RAG Agent
1. **vector_rag_agent** - 向量检索Agent
2. **web_research_agent** - 网页研究Agent
3. **document_qa_agent** - 文档问答Agent
4. **sql_query_agent** - SQL查询Agent
5. **knowledge_graph_agent** - 知识图谱Agent
6. **multi_modal_agent** - 多模态Agent
7. **reasoning_agent** - 推理Agent
8. **summarization_agent** - 摘要Agent
9. **classification_agent** - 分类Agent
10. **entity_extraction_agent** - 实体提取Agent
11. **sentiment_analysis_agent** - 情感分析Agent

---

## 📈 监控指标说明

### 成功率计算
```python
success_rate = success_count / total_executions
```

### 状态评级标准
| 成功率 | 状态 | 颜色 | 说明 |
|--------|------|------|------|
| ≥90% | Excellent | 绿色 | 运行优秀 |
| 70-90% | Good | 黄色 | 运行良好 |
| <70% | Poor | 红色 | 需要优化 |

### 性能指标
- **平均执行时间**: 反映Agent响应速度
- **平均Token消耗**: 反映成本和复杂度
- **错误类型**: 帮助定位问题根源

---

## 🎯 使用场景

### 1. 日常监控
管理员每天查看：
- 整体成功率是否正常
- 是否有Agent性能下降
- 错误分布是否异常

### 2. 问题排查
当用户报告问题时：
- 查看特定Agent的成功率
- 检查最近的执行时间
- 分析错误类型分布

### 3. 性能优化
定期评估：
- 哪些Agent执行时间过长
- 哪些Agent Token消耗过高
- 哪些Agent需要优化

### 4. 容量规划
基于数据决策：
- 最常用的Agent是哪些
- 是否需要增加资源
- 是否需要调整配置

---

## 🔧 API端点（需要后端实现）

### GET /api/v1/admin/agent-quality/stats
返回Agent质量统计数据

**响应格式**:
```json
{
  "summary": {
    "total_agents": 11,
    "active_agents": 9,
    "total_executions": 15420,
    "overall_success_rate": 0.94,
    "avg_response_time": 2.3
  },
  "agents": [
    {
      "agent_name": "vector_rag_agent",
      "total_executions": 5430,
      "success_count": 5102,
      "failure_count": 328,
      "success_rate": 0.94,
      "avg_execution_time": 1.8,
      "avg_token_usage": 350,
      "last_execution": "2026-07-01T10:30:00Z",
      "error_types": {
        "timeout": 120,
        "api_error": 85,
        "validation_error": 123
      }
    }
  ],
  "timeline": [
    {
      "timestamp": "2026-07-01 09:00",
      "success": 45,
      "failure": 3
    }
  ],
  "error_distribution": {
    "timeout": 450,
    "api_error": 320,
    "validation_error": 180,
    "network_error": 95
  }
}
```

---

## 📊 数据可视化

### 图表类型
| 图表 | 类型 | 用途 |
|------|------|------|
| 成功/失败时间线 | 折线图 | 趋势分析 |
| 错误分布 | 饼图 | 问题定位 |
| 执行次数统计 | 横向柱状图 | 使用频率 |
| 执行时间统计 | 横向柱状图 | 性能分析 |

### KPI卡片
- 5个核心指标
- 颜色编码
- 一眼看出系统状况

---

## 🎨 UI设计特点

### 1. 颜色编码
- **绿色**: 优秀、成功
- **黄色**: 良好、警告
- **红色**: 差、失败

### 2. 响应式布局
- 双列图表布局
- 自适应宽度
- 移动端友好

### 3. 交互功能
- Agent过滤
- 自动刷新开关
- 数据导出

### 4. 信息层次
1. KPI卡片（最重要）
2. 时间线和分布图（趋势）
3. 详细表格（细节）
4. 健康概览（深度分析）

---

## 🚀 集成步骤

### 1. 添加到AdminPage.tsx
```typescript
import { AdminAgentQualityDashboard } from "@/pages/admin/AdminAgentQualityDashboard";

// 在tabs中添加
{state.section === "agentquality" && (
  <AdminAgentQualityDashboard />
)}
```

### 2. 添加导航标签
```typescript
<button
  className={state.section === "agentquality" ? "active" : ""}
  onClick={() => dispatch({ type: "SET_SECTION", section: "agentquality" })}
>
  {t("admin.nav.agentQuality", "AGENT QUALITY")}
</button>
```

### 3. 实现后端API
- 创建 `/app/api/routes/agent_quality.py`
- 从数据库或日志中聚合Agent执行数据
- 返回统计信息

---

## 📈 监控告警建议

### 自动告警条件
1. **成功率低于70%** → 发送告警
2. **某个Agent完全无响应** → 发送告警
3. **平均响应时间超过5秒** → 发送告警
4. **错误率突然上升** → 发送告警

### 告警通知方式
- 浏览器通知
- 邮件通知
- Slack/企业微信通知

---

## 🎯 与其他监控的关系

### 现有监控系统
1. **System OPS** - 系统资源监控（CPU、内存）
2. **Web Activity** - Web搜索活动监控
3. **Agent Quality** - Agent质量监控（新增）✨

### 互补关系
- System OPS: 基础设施层
- Agent Quality: 应用层
- Web Activity: 业务层

三层监控，全面覆盖！

---

## 📊 数据来源

### 可能的数据源
1. **数据库日志表**
   - agent_execution_logs
   - agent_performance_metrics

2. **应用日志**
   - 解析日志文件
   - 提取执行记录

3. **实时追踪**
   - 在Agent执行时记录指标
   - 写入时序数据库

---

## 🎊 最终效果

### 管理员视角
```
┌─────────────────────────────────────────┐
│ Agent质量监控                            │
├─────────────────────────────────────────┤
│ [KPI卡片 x 5]                           │
├─────────────────────────────────────────┤
│ [时间线图]    [错误分布饼图]            │
├─────────────────────────────────────────┤
│ Agent性能详情表                          │
│ ┌──────────────────────────────────┐   │
│ │ vector_rag_agent   │ 5430 │ 94% │   │
│ │ web_research_agent │ 3210 │ 91% │   │
│ │ ...                               │   │
│ └──────────────────────────────────┘   │
├─────────────────────────────────────────┤
│ [执行次数图]  [执行时间图]              │
└─────────────────────────────────────────┘
```

### 价值
- ✅ 一眼看出所有Agent运行状况
- ✅ 快速定位问题Agent
- ✅ 数据驱动的优化决策
- ✅ 完整的质量追踪

---

## 🎯 总结

### 新增内容
- ✅ Agent质量监控面板（全新功能）
- ✅ 5个KPI指标
- ✅ 4个可视化图表
- ✅ 1个详细数据表
- ✅ 完整的中英文翻译
- ✅ 数据导出功能
- ✅ 自动刷新

### 文件信息
- **文件**: `AdminAgentQualityDashboard.tsx`
- **行数**: 约280行
- **状态**: 前端完成，等待后端API

### 下一步
1. 实现后端API (`/api/v1/admin/agent-quality/stats`)
2. 集成到AdminPage.tsx
3. 添加导航标签
4. 测试数据展示

---

**🎉 QueryMind现在拥有完整的三层监控体系！**

- 🖥️ **系统层**: System OPS
- 🤖 **应用层**: Agent Quality（新增）
- 🌐 **业务层**: Web Activity

**符合企业级监控平台标准！** ✨🚀

最后更新：2026-07-01  
版本：v0.6.0+
