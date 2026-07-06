# 监控和管理 - 快速参考
# Monitoring & Management - Quick Reference

快速查阅新增的监控和管理功能。

---

## 🔍 健康检查端点 / Health Check Endpoints

### 基础健康检查（存活探针）
```bash
curl http://localhost:8000/health
```

**响应：**
```json
{
  "status": "ok",
  "service": "querymind-api",
  "version": "0.6.1"
}
```

### 综合就绪检查
```bash
curl http://localhost:8000/ready
```

**检查项：** PostgreSQL, Redis, Ollama, OpenAI, Anthropic, Neo4j, ChromaDB, 嵌入模型

### 熔断器状态
```bash
curl http://localhost:8000/circuit-breakers
```

---

## 📊 监控指标 / Metrics

### 查看Prometheus指标
```bash
curl http://localhost:8000/metrics
```

### 记录业务指标
```python
from app.api.dependencies import runtime_metrics

# Agent执行统计
runtime_metrics.inc_agent_execution("RouterAgent", "success", "vector")

# 检索质量
runtime_metrics.observe_retrieval_quality(0.92, "hybrid")

# LLM成本
runtime_metrics.inc_llm_cost(0.0012, "openai", "gpt-4")

# 缓存命中率
runtime_metrics.inc_cache_operations("retrieval", hit=True, layer="l1")

# 会话时长
runtime_metrics.observe_session_duration(1800, "premium")
```

---

## 📝 结构化日志 / Structured Logging

### 配置（在app/main.py）
```python
from app.core.logging_config import configure_structured_logging

configure_structured_logging(
    log_level="INFO",
    json_output=True,
    include_timestamp=True
)
```

### 使用
```python
from app.core.logging_config import get_logger, bind_context

logger = get_logger(__name__)

# 简单日志
logger.info("query_received", query="What is Docker?", user_id="user_123")

# 上下文绑定
bind_context(request_id="req_456", user_id="user_123")
logger.info("processing_query")  # 自动包含上下文
```

---

## 🛡️ 熔断器 / Circuit Breakers

### 使用包装器
```python
from app.services.circuit_breaker_integration import LLMClientWithCircuitBreaker

llm = LLMClientWithCircuitBreaker(openai_client)
response = llm.chat_completion(messages, model="gpt-4")
```

### 使用装饰器
```python
from app.services.circuit_breaker_integration import with_circuit_breaker

@with_circuit_breaker("my_service")
def call_external_service():
    return external_api.call()
```

---

## ⚙️ 动态日志级别 / Dynamic Log Levels

### 查看当前级别
```bash
curl http://localhost:8000/admin/ops/logging/levels
```

### 调整级别（需要admin权限）
```bash
curl -X POST http://localhost:8000/admin/ops/logging/level \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "logger": "app.agents.enhanced_router_agent",
    "level": "DEBUG"
  }'
```

### 重置所有级别
```bash
curl -X POST http://localhost:8000/admin/ops/logging/reset \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 📈 Prometheus查询示例 / Prometheus Queries

### Agent成功率
```promql
sum(rate(agent_execution_total{status="success"}[5m])) by (agent)
/
sum(rate(agent_execution_total[5m])) by (agent)
```

### 检索质量P95
```promql
histogram_quantile(0.95,
  sum(rate(retrieval_quality_score_seconds_bucket[5m])) by (le, strategy)
)
```

### 每小时LLM成本
```promql
sum(rate(llm_api_cost_usd_total[1h])) by (provider)
```

### 缓存命中率
```promql
sum(rate(cache_operations_total{result="hit"}[5m]))
/
sum(rate(cache_operations_total[5m]))
```

---

## 🔔 告警规则示例 / Alert Rules

### 高错误率
```yaml
- alert: HighAgentErrorRate
  expr: |
    sum(rate(agent_execution_total{status="failed"}[5m])) by (agent)
    /
    sum(rate(agent_execution_total[5m])) by (agent)
    > 0.05
  for: 5m
  labels:
    severity: warning
```

### LLM成本超标
```yaml
- alert: HighLLMCost
  expr: sum(rate(llm_api_cost_usd_total[1h])) > 10
  for: 1h
  labels:
    severity: critical
```

---

## 🐛 调试技巧 / Debugging Tips

### 1. 临时启用DEBUG日志
```bash
# 启用特定模块的DEBUG
curl -X POST http://localhost:8000/admin/ops/logging/level \
  -d '{"logger": "app.agents.enhanced_router_agent", "level": "DEBUG"}'

# 排查完成后恢复
curl -X POST http://localhost:8000/admin/ops/logging/reset
```

### 2. 检查熔断器状态
```bash
# 查看哪些熔断器打开了
curl http://localhost:8000/circuit-breakers | jq '.circuits | to_entries[] | select(.value.state == "open")'
```

### 3. 查看最近错误
```bash
# 查看最近的ERROR级别日志
curl http://localhost:8000/ready | jq '.query_runtime'
```

### 4. 监控特定Agent
```bash
# 在Prometheus中查询
curl 'http://localhost:9090/api/v1/query?query=agent_execution_total{agent="RouterAgent"}'
```

---

## 📚 完整文档 / Full Documentation

- [监控审计报告](code_monitoring_management_audit.md) - 完整问题分析
- [监控指标使用](monitoring_metrics_usage.md) - 详细集成指南
- [日志迁移指南](logging_migration_guide.md) - Structlog迁移步骤
- [修复总结](monitoring_fixes_summary.md) - 已完成的修复

---

## 🚀 快速开始 / Quick Start

### 1. 验证健康状态
```bash
curl http://localhost:8000/ready | jq '.status'
```

### 2. 查看指标
```bash
curl http://localhost:8000/metrics | grep agent_execution
```

### 3. 检查日志
```bash
# 如果使用JSON日志
tail -f logs/app.log | jq '.'
```

### 4. 监控熔断器
```bash
watch -n 5 'curl -s http://localhost:8000/circuit-breakers | jq .open_circuits'
```

---

**更新时间 / Last Updated:** 2026-07-06
