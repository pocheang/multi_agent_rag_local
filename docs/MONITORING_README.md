# 监控和管理功能 - README补充
# Monitoring & Management Features - README Addendum

本文档是对主README.md的补充，详细说明新增的监控和管理功能。

---

## 🔍 新增功能概览 / New Features Overview

### 1. 增强的健康检查 / Enhanced Health Checks

**新增端点：**

```bash
# 基础健康检查（Kubernetes liveness probe）
GET /health
# 返回: {"status": "ok", "service": "querymind-api", "version": "0.6.1"}

# 综合就绪检查（Kubernetes readiness probe）
GET /ready
# 检查: PostgreSQL, Redis, Ollama, OpenAI, Anthropic, Neo4j, ChromaDB, 嵌入模型

# 熔断器状态监控
GET /circuit-breakers
# 返回所有熔断器的实时状态
```

**Kubernetes配置示例：**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

---

### 2. 业务指标监控 / Business Metrics

**新增指标方法：**

```python
from app.api.dependencies import runtime_metrics

# Agent执行统计（按Agent/状态/路由）
runtime_metrics.inc_agent_execution(
    agent_name="EnhancedRouterAgent",
    status="success",  # or "failed"
    route="vector"
)

# 检索质量分数（按策略）
runtime_metrics.observe_retrieval_quality(
    score=0.92,
    strategy="hybrid"  # or "dense", "bm25", "rerank"
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

**Prometheus查询示例：**
```promql
# Agent成功率
sum(rate(agent_execution_total{status="success"}[5m])) by (agent)
/ sum(rate(agent_execution_total[5m])) by (agent)

# P95检索质量分数
histogram_quantile(0.95, 
  sum(rate(retrieval_quality_score_seconds_bucket[5m])) by (le, strategy)
)

# 每小时LLM成本
sum(rate(llm_api_cost_usd_total[1h])) by (provider)
```

---

### 3. 结构化日志 / Structured Logging

**初始化（在app/main.py）：**

```python
from app.core.logging_config import configure_structured_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 配置结构化日志
    configure_structured_logging(
        log_level="INFO",
        json_output=True,  # 生产环境使用JSON
        include_timestamp=True
    )
    
    yield
```

**使用示例：**

```python
from app.core.logging_config import get_logger, bind_context

logger = get_logger(__name__)

# 简单日志（键值对）
logger.info("query_received", 
    query="What is Docker?",
    user_id="user_123",
    query_length=15
)

# 上下文绑定（自动附加到所有日志）
bind_context(request_id="req_456", user_id="user_123")
logger.info("processing_query")
logger.info("query_completed", duration_ms=450)
clear_context()

# 异常日志（自动包含堆栈跟踪）
try:
    result = dangerous_operation()
except Exception as e:
    logger.exception("operation_failed", operation="dangerous_operation")
```

**JSON输出示例：**
```json
{
  "event": "query_received",
  "query": "What is Docker?",
  "user_id": "user_123",
  "request_id": "req_456",
  "timestamp": "2026-07-06T10:30:45.123Z",
  "level": "info",
  "logger": "app.api.routes.query"
}
```

---

### 4. 熔断器保护 / Circuit Breaker Protection

**LLM API保护：**

```python
from app.services.circuit_breaker_integration import LLMClientWithCircuitBreaker

class EnhancedRouterAgent:
    def __init__(self, llm_client):
        # 包装LLM客户端
        self.llm = LLMClientWithCircuitBreaker(llm_client)
    
    def route_query(self, query: str):
        try:
            response = self.llm.chat_completion(
                messages=[{"role": "user", "content": query}],
                model="gpt-4"
            )
            return self._parse_routing_decision(response)
        except RuntimeError as e:
            if "circuit open" in str(e):
                # 降级到规则路由
                return self._rule_based_routing(query)
```

**向量检索保护：**

```python
from app.services.circuit_breaker_integration import VectorStoreWithCircuitBreaker

vector_store = VectorStoreWithCircuitBreaker(chroma_client)

# 自动降级到BM25
results = vector_store.similarity_search(query, k=10)
```

**装饰器模式：**

```python
from app.services.circuit_breaker_integration import with_circuit_breaker

@with_circuit_breaker("embedding_service")
def get_embedding(text: str) -> list[float]:
    return expensive_embedding_call(text)
```

---

### 5. 动态日志级别 / Dynamic Log Levels

**管理端点（需要admin权限）：**

```bash
# 查看所有logger的当前级别
GET /admin/ops/logging/levels

# 动态调整日志级别（无需重启）
POST /admin/ops/logging/level
{
  "logger": "app.agents.enhanced_router_agent",
  "level": "DEBUG"
}

# 重置所有logger到默认级别
POST /admin/ops/logging/reset
```

**使用场景：**
```bash
# 生产环境临时启用DEBUG排查问题
curl -X POST http://localhost:8000/admin/ops/logging/level \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"logger": "app.agents.enhanced_router_agent", "level": "DEBUG"}'

# 排查完成后恢复
curl -X POST http://localhost:8000/admin/ops/logging/reset \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 📊 监控系统部署 / Monitoring Stack Deployment

### 快速启动

```bash
# 1. 启动监控栈（Prometheus + Grafana + Alertmanager）
docker-compose -f docker-compose.monitoring.yml up -d

# 2. 访问服务
# Grafana: http://localhost:3000 (admin/admin123)
# Prometheus: http://localhost:9090
# Alertmanager: http://localhost:9093

# 3. 导入Grafana仪表盘
# 上传 dashboards/grafana/rag-system-overview.json
```

### 监控面板

Grafana仪表盘包含14个监控面板：

1. **System Health Status** - 系统整体健康状态
2. **Total Query Rate** - 总查询速率
3. **Overall Success Rate** - 整体成功率
4. **P95 Query Latency** - 95分位延迟
5. **Agent Execution Rate** - Agent执行速率（按Agent）
6. **Agent Success Rate** - Agent成功率（按Agent）
7. **Retrieval Quality Score** - 检索质量分数（按策略）
8. **Cache Hit Rate** - 缓存命中率（按层级）
9. **LLM API Cost** - LLM API成本（按提供商/小时）
10. **Circuit Breaker Status** - 熔断器状态
11. **Query Latency Distribution** - 查询延迟分布（P50/P90/P95/P99）
12. **Error Rate by Agent** - Agent错误率
13. **Top LLM Models by Cost** - 最贵的LLM模型
14. **Dependency Health Status** - 依赖服务健康状态

### 告警规则

30+预定义告警规则，覆盖：

**Critical级别：**
- SystemUnhealthy - 系统宕机
- HighAgentErrorRate - Agent错误率>10%
- LLMCostExceeded - LLM成本>$20/h
- AllCircuitBreakersOpen - 多个熔断器打开

**Warning级别：**
- HighLatency - P95延迟>4s
- LowRetrievalQuality - 检索质量<0.6
- LowCacheHitRate - 缓存命中率<50%
- CircuitBreakerOpen - 单个熔断器打开

**Info级别：**
- HighQueryRate - 查询速率高
- LLMCostIncreasing - LLM成本上升
- LongUserSessions - 用户会话时长长

---

## 📚 完整文档 / Complete Documentation

### 核心文档

1. **[监控审计报告](docs/code_monitoring_management_audit.md)**
   - 完整问题分析（15个问题）
   - 优先级矩阵
   - 修复建议

2. **[监控指标使用指南](docs/monitoring_metrics_usage.md)**
   - 业务指标集成
   - Prometheus查询示例
   - Grafana仪表盘配置
   - 告警规则示例

3. **[日志迁移指南](docs/logging_migration_guide.md)**
   - Structlog配置
   - 迁移步骤
   - 5种迁移模式
   - ELK Stack集成

4. **[修复总结](docs/monitoring_fixes_summary.md)**
   - 已完成的修复详情
   - 代码变更统计
   - 验证清单

5. **[快速参考](docs/monitoring_quick_reference.md)**
   - 常用命令
   - API端点
   - Prometheus查询
   - 调试技巧

6. **[部署指南](docs/monitoring_deployment_guide.md)**
   - Docker Compose配置
   - 生产环境配置
   - 故障排查
   - 最佳实践

7. **[实施路线图](docs/monitoring_implementation_roadmap.md)**
   - 5个阶段计划
   - 时间线和里程碑
   - 资源需求
   - 风险缓解

---

## 🚀 快速验证 / Quick Verification

```bash
# 1. 检查健康状态
curl http://localhost:8000/health
curl http://localhost:8000/ready

# 2. 查看Prometheus指标
curl http://localhost:8000/metrics | grep agent_execution_total

# 3. 查看熔断器状态
curl http://localhost:8000/circuit-breakers

# 4. 查看日志级别
curl http://localhost:8000/admin/ops/logging/levels

# 5. 测试Prometheus（如果已部署）
curl http://localhost:9090/api/v1/query?query=up{job="rag-api"}

# 6. 访问Grafana仪表盘
open http://localhost:3000
```

---

## 🎯 关键改进 / Key Improvements

| 指标 | 修复前 | 修复后 | 提升 |
|------|--------|--------|------|
| 健康检查覆盖 | 3个服务 | 8个服务 | +167% |
| 监控指标维度 | 0维 | 多维标签 | ∞ |
| 日志格式 | 文本 | JSON结构化 | 可机器解析 |
| 熔断器集成 | 部分 | 全面 | 100%覆盖 |
| 动态日志调整 | ❌ | ✅ | 新增 |
| 告警规则 | 0个 | 30+个 | 新增 |
| 可视化仪表盘 | 0个 | 14个面板 | 新增 |

---

## 📞 支持和反馈 / Support & Feedback

### 遇到问题？

1. 查看 [故障排查指南](docs/monitoring_deployment_guide.md#故障排查)
2. 检查 [GitHub Issues](https://github.com/your-repo/issues)
3. 联系运维团队

### 贡献

欢迎提交改进建议和PR：
- 新的监控指标
- 告警规则优化
- 仪表盘增强
- 文档改进

---

**版本:** v0.6.1+monitoring  
**最后更新:** 2026-07-06  
**维护者:** DevOps Team
