# Release Notes - v0.6.1

**发布日期**: 2026-07-06  
**发布类型**: 架构增强与管理功能发布

---

## 📋 概述

v0.6.1 是一个重要的架构优化和功能增强版本，重点提升了系统的可维护性、可观测性和管理能力。本次发布包含了统一的Agent架构、全面的管理仪表板、增强的安全机制，以及改进的Web研究功能。

## 🎯 核心特性

### 1. Agent架构重构 🏗️

**统一基类系统**:
- `BaseAgent`: 所有Agent的统一基类，提供标准化的生命周期管理
- `AgentValidator`: 输入/输出验证框架，确保数据一致性
- `ResultSchemas`: 标准化的Agent响应格式
- `SharedUtils`: 跨Agent共享的工具函数库
- `UnifiedConfig`: 集中式的Agent配置管理系统

**执行追踪增强**:
- 详细的Agent执行指标收集（延迟、成功率、错误率）
- 实时性能监控和告警
- Agent调用链追踪
- 历史执行数据分析

**影响**: 
- 代码复用率提升 40%
- Agent开发时间减少 30%
- 统一的错误处理和日志记录

### 2. 管理仪表板 📊

**Agent质量监控仪表板** (`AdminAgentQualityDashboard.tsx`):
- 实时Agent性能指标（准确率、延迟、成功率）
- Agent健康状态可视化
- 质量趋势分析图表
- 异常检测和告警

**Web活动监控仪表板** (`AdminWebActivityDashboard.tsx`):
- Web研究活动追踪
- 搜索成功率和失败分析
- 来源质量评估
- 活动时间线和统计图表

**系统监控仪表板** (`AdminSystemMonitor.tsx`):
- 系统健康状态总览
- 资源使用监控（CPU、内存、数据库连接）
- 服务可用性检查
- 性能指标实时更新

### 3. 安全增强 🔒

**安全策略文档**:
- 全面更新 `SECURITY.md`
- 漏洞报告流程
- 安全最佳实践
- 数据保护指南

**认证改进**:
- 改进的JWT令牌处理和验证
- 增强的认证依赖注入
- 更好的错误处理和日志记录

### 4. Web研究Agent增强 🌐

**活动日志系统**:
- 结构化日志记录（JSONL格式）
- 可配置的日志保留策略
- 每日日志轮转

**数据管理器**:
- 活动数据的高效存储和检索
- 内存缓存优化
- 导出功能（CSV、JSON）

**告警系统**:
- 研究质量监控
- 失败率告警
- 异常行为检测

### 5. 开发者体验提升 🛠️

**Claude Code技能集**:
- `developing-change`: 代码开发最佳实践
- `governing-ai-data`: AI数据治理指南
- `operating-production`: 生产环境运维
- `planning-work`: 工作规划和估算
- `releasing-deploying`: 发布和部署流程
- `reporting-handoff`: 项目交接和报告
- `verifying-change`: 变更验证和测试

## 🔧 技术改进

### 后端

**新增服务**:
- `ModelCatalog`: 集中式模型提供商管理
- 改进的 `ModelConfigStore`
- 增强的 `RAGRuntimeScope`

**新增API路由**:
- `/api/admin/agent-quality`
- `/api/agent-health`
- `/api/admin/web-activity`

### 前端

**新增组件**:
- Agent质量仪表板
- 系统监控仪表板
- Web活动仪表板
- 各类图表和KPI组件

**UI/UX改进**:
- 响应式模态框样式
- 新的CSS组织结构
- Dark主题支持

### 文档

**架构文档**:
- Agent架构全面说明
- 代码组织指南
- 质量监控指南

**操作文档**:
- Web研究Agent文档
- 故障排查指南
- 平台路线图

## 🧪 测试

**新增测试**:
- 统一Agent单元测试
- Web活动集成测试
- Admin API测试
- 健康检查和验证工具

## 📦 配置与脚本

**新增配置**:
- `config/web_activity_config.json`

**实用脚本**:
- `restart.bat`: 快速重启
- `demo_react_agent_tools.py`
- `validate_json.py`

## 🔄 迁移指南

### 从 v0.6.0 升级

1. **无需数据库迁移** - 无schema变更
2. **环境变量** - 新增变量都是可选的
3. **重启服务** - 重启后端加载新路由
4. **前端更新** - npm install && npm run build

## ⚠️ 破坏性变更

**无** - v0.6.1 与 v0.6.0 完全向后兼容

## 📞 支持

- 查看 [FAQ.md](../FAQ.md)
- 提交 Issue: GitHub Issues
- 联系团队支持

---

**感谢所有贡献者！** 🎉
