# QueryMind v0.6.2 Release Notes

**发布日期**: 2026-07-06  
**版本类型**: Minor Release - 项目重命名与监控系统完善

---

## 📋 版本概述

v0.6.2 是一个重要的品牌升级和可观测性增强版本。项目正式更名为 **QueryMind（智询）**，并完善了生产级监控系统，为企业部署提供完整的可观测性支持。

---

## 🎯 核心变更

### 1. 🏷️ 项目重命名

**从 "Multi-Agent RAG Local v4" 更名为 "QueryMind（智询）"**

- ✅ 更新所有Python代码文件（27个）
- ✅ 更新所有配置文件（3个）
- ✅ 更新所有文档文件（48个）
- ✅ 更新项目配置（pyproject.toml）
- ✅ 包名: `querymind`
- ✅ 服务名: `querymind-api`
- ✅ 追踪标识: `querymind`

**关键文件更新:**
- `app/api/main.py` - FastAPI应用标题
- `app/api/routes/health.py` - 健康检查服务名
- `app/__version__.py` - 包信息
- `pyproject.toml` - 项目配置

**保留技术术语:**
- "Multi-Agent System" - 架构描述
- "multi-agent orchestration" - 技术概念
- 术语表中的定义

---

### 2. 📊 监控系统完善

#### 健康检查增强

**新增6个依赖检查函数** (`app/api/routes/health.py`)

```python
# 新增检查项
- PostgreSQL 数据库连接
- Redis 缓存服务
- OpenAI API 可用性
- Anthropic API 可用性
- Neo4j 图数据库
- ChromaDB 向量库
- 嵌入模型加载状态
```

**新增端点:**
- `GET /health` - 基础存活探针（Kubernetes liveness probe）
- `GET /ready` - 综合就绪检查（Kubernetes readiness probe）
- `GET /circuit-breakers` - 熔断器状态监控

#### 业务指标追踪

**新增5个业务指标方法** (`app/services/runtime_metrics.py`)

```python
# Agent执行统计（按Agent/状态/路由）
runtime_metrics.inc_agent_execution(
    agent_name="EnhancedRouterAgent",
    status="success",
    route="vector"
)

# 检索质量分数（按策略）
runtime_metrics.observe_retrieval_quality(
    score=0.92,
    strategy="hybrid"
)

# LLM API成本追踪（按提供商/模型）
runtime_metrics.inc_llm_cost(
    cost_usd=0.0012,
    provider="openai",
    model="gpt-4"
)

# 缓存命中率统计（按层级）
runtime_metrics.inc_cache_operations(
    operation="retrieval",
    hit=True,
    layer="l1"
)

# 用户会话时长（按用户类型）
runtime_metrics.observe_session_duration(
    duration_seconds=1800,
    user_type="premium"
)
```

#### 结构化日志

**新增模块** (`app/core/logging_config.py`)

- Structlog配置和封装
- JSON格式输出
- 上下文传播
- 性能追踪
- 动态日志级别管理

**新增管理端点** (`app/api/routes/admin_ops.py`)

```bash
GET  /admin/ops/logging/levels    # 查看日志级别
POST /admin/ops/logging/level     # 动态调整级别
POST /admin/ops/logging/reset     # 重置到默认
```

#### 熔断器集成

**新增模块** (`app/services/circuit_breaker_integration.py`)

- `LLMClientWithCircuitBreaker` - LLM API保护
- `VectorStoreWithCircuitBreaker` - 向量库保护
- `GraphStoreWithCircuitBreaker` - 图数据库保护
- `@with_circuit_breaker()` - 装饰器模式

**特性:**
- 自动降级策略
- 失败计数器
- 半开状态恢复
- 实时状态监控

---

### 3. 🚨 监控栈部署

#### Docker Compose配置

**新增文件** (`docker-compose.monitoring.yml`)

```yaml
services:
  - Prometheus (http://localhost:9090)
  - Grafana (http://localhost:3000)
  - Alertmanager (http://localhost:9093)
```

**快速启动:**
```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

#### Prometheus配置

**新增配置** (`config/prometheus/`)

- `prometheus.yml` - 抓取配置
- `alert_rules.yml` - 30+告警规则
- 数据保留30天
- 15秒抓取间隔

**告警规则分级:**

**Critical级别:**
- SystemUnhealthy - 系统宕机
- HighAgentErrorRate - Agent错误率>10%
- LLMCostExceeded - LLM成本>$20/h
- AllCircuitBreakersOpen - 多个熔断器打开

**Warning级别:**
- HighLatency - P95延迟>4s
- LowRetrievalQuality - 检索质量<0.6
- LowCacheHitRate - 缓存命中率<50%
- CircuitBreakerOpen - 单个熔断器打开

**Info级别:**
- HighQueryRate - 查询速率高
- LLMCostIncreasing - LLM成本上升
- LongUserSessions - 用户会话时长长

#### Grafana仪表盘

**新增仪表盘** (`dashboards/grafana/rag-system-overview.json`)

**14个监控面板:**
1. System Health Status - 系统整体健康状态
2. Total Query Rate - 总查询速率
3. Overall Success Rate - 整体成功率
4. P95 Query Latency - 95分位延迟
5. Agent Execution Rate - Agent执行速率
6. Agent Success Rate - Agent成功率
7. Retrieval Quality Score - 检索质量分数
8. Cache Hit Rate - 缓存命中率
9. LLM API Cost - LLM API成本
10. Circuit Breaker Status - 熔断器状态
11. Query Latency Distribution - 延迟分布
12. Error Rate by Agent - Agent错误率
13. Top LLM Models by Cost - 成本排名
14. Dependency Health Status - 依赖健康状态

#### Alertmanager配置

**新增配置** (`config/alertmanager/alertmanager.yml`)

- 告警路由规则
- 分组策略
- 抑制规则
- 通知渠道模板（Slack/PagerDuty/Email）

---

## 📚 文档更新

### 新增文档（10个文件，~82页）

1. **[监控审计报告](../code_monitoring_management_audit.md)** (15页)
   - 完整问题分析（15个问题）
   - 优先级矩阵
   - 修复建议

2. **[监控指标使用指南](../monitoring_metrics_usage.md)** (12页)
   - 业务指标集成
   - Prometheus查询示例
   - Grafana仪表盘配置
   - 告警规则示例

3. **[日志迁移指南](../logging_migration_guide.md)** (10页)
   - Structlog配置
   - 迁移步骤
   - 5种迁移模式
   - ELK Stack集成

4. **[监控部署指南](../monitoring_deployment_guide.md)** (15页)
   - Docker Compose配置
   - 生产环境配置
   - 故障排查
   - 最佳实践

5. **[监控实施路线图](../monitoring_implementation_roadmap.md)** (12页)
   - 5个阶段计划
   - 时间线和里程碑
   - 资源需求
   - 风险缓解

6. **[快速参考](../monitoring_quick_reference.md)** (8页)
   - 常用命令
   - API端点
   - Prometheus查询
   - 调试技巧

7. **[MONITORING_README](../MONITORING_README.md)** (10页)
   - 功能概览
   - 快速开始
   - 完整文档索引

### 更新文档

- README.md - 更新版本到v0.6.2，新增特性说明
- CHANGELOG.md - 新增v0.6.2变更日志
- 所有文档中的项目名称更新

---

## 📈 性能与指标

### 监控覆盖率提升

| 维度 | v0.6.1 | v0.6.2 | 提升 |
|------|--------|--------|------|
| 健康检查服务 | 3个 | 8个 | +167% |
| 监控指标维度 | 基础 | 多维标签 | ∞ |
| 日志格式 | 文本 | JSON结构化 | 可机器解析 |
| 熔断器集成 | 部分 | 全面 | 100%覆盖 |
| 动态日志 | ❌ | ✅ | 新增 |
| 告警规则 | 0个 | 30+个 | 新增 |
| 可视化面板 | 0个 | 14个 | 新增 |

### 质量指标（保持v0.6.1水平）

- 路由准确率: >99%
- 幻觉率: <10%
- 引用完整性: >96%
- Precision@5: >0.90
- P95延迟: <4s

---

## 🔄 迁移指南

### 从 v0.6.1 升级到 v0.6.2

**1. 更新代码**

```bash
git pull origin main
git checkout v0.6.2
```

**2. 更新依赖**

```bash
conda activate rag-local
pip install -e .
```

**3. 项目名称变更**

所有代码中的项目引用已自动更新，无需手动修改。

**4. 启用监控（可选）**

```bash
# 启动监控栈
docker-compose -f docker-compose.monitoring.yml up -d

# 访问Grafana
open http://localhost:3000  # admin/admin123
```

**5. 配置结构化日志（可选）**

```python
# 在 app/main.py 中
from app.core.logging_config import configure_structured_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_structured_logging(
        log_level="INFO",
        json_output=True
    )
    yield
```

**6. 集成熔断器（可选）**

```python
from app.services.circuit_breaker_integration import LLMClientWithCircuitBreaker

# 包装现有LLM客户端
llm_client = LLMClientWithCircuitBreaker(your_llm_client)
```

### 破坏性变更

**无破坏性变更** - 本版本完全向后兼容v0.6.1

---

## 🐛 Bug修复

无重大bug修复（本版本专注于功能增强和品牌更新）

---

## 🔮 下一步计划

### v0.6.3 规划（预计2周内）

- 📊 OpenTelemetry分布式追踪集成
- 🔍 ELK Stack日志聚合
- 📈 高级成本分析仪表盘
- 🚨 智能告警降噪
- 📱 移动端监控应用

### 长期路线图

- 📊 实时Agent执行可视化
- 🧪 A/B测试框架
- 🔄 自动扩缩容支持
- 🌍 多区域部署支持

---

## 📞 支持与反馈

### 获取帮助

- 📖 [完整文档](../README.md)
- 🐛 [报告问题](https://github.com/yourorg/querymind/issues)
- 💬 [讨论区](https://github.com/yourorg/querymind/discussions)

### 贡献

欢迎提交PR改进监控系统：
- 新的监控指标
- 告警规则优化
- 仪表盘增强
- 文档改进

---

## 👥 贡献者

感谢所有为本版本做出贡献的开发者！

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](../../LICENSE) 文件。

---

**完整变更日志**: [v0.6.1...v0.6.2](https://github.com/yourorg/querymind/compare/v0.6.1...v0.6.2)
