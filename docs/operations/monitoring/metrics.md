# 监控指标使用指南
# Monitoring Metrics Usage Guide

本文档描述如何使用增强版的RuntimeMetrics来跟踪业务指标。

This document describes how to use the enhanced RuntimeMetrics to track business metrics.

---

## 基础用法 / Basic Usage

### 导入 / Import

```python
from app.api.dependencies import runtime_metrics
```

---

## 业务指标 / Business Metrics

### 1. Agent执行统计 / Agent Execution Stats

跟踪每个Agent的执行次数和成功率。

Track execution count and success rate for each agent.

```python
# 在Agent执行后调用
runtime_metrics.inc_agent_execution(
    agent_name="EnhancedRouterAgent",
    status="success",  # or "failed"
    route="vector"     # optional
)
```

**Prometheus查询示例：**
```promql
# Agent成功率
sum(rate(agent_execution_total{status="success"}[5m])) by (agent)
  / 
sum(rate(agent_execution_total[5m])) by (agent)

# 按路由的Agent执行量
sum(rate(agent_execution_total[5m])) by (route)
```

---

### 2. 检索质量分数 / Retrieval Quality Score

跟踪不同检索策略的质量分数。

Track quality scores for different retrieval strategies.

```python
# 在检索后记录质量分数
runtime_metrics.observe_retrieval_quality(
    score=0.92,
    strategy="hybrid"  # or "dense", "bm25", "rerank"
)
```

**Prometheus查询示例：**
```promql
# P95检索质量分数
histogram_quantile(0.95, 
  sum(rate(retrieval_quality_score_seconds_bucket[5m])) by (le, strategy)
)

# 平均质量分数
avg(retrieval_quality_score_seconds_sum / retrieval_quality_score_seconds_count) by (strategy)
```

---

### 3. LLM API成本 / LLM API Cost

跟踪LLM API调用成本，按提供商和模型分类。

Track LLM API costs by provider and model.

```python
# 在LLM调用后记录成本
runtime_metrics.inc_llm_cost(
    cost_usd=0.0012,
    provider="openai",  # or "anthropic", "ollama"
    model="gpt-4"
)
```

**Prometheus查询示例：**
```promql
# 每小时LLM成本
sum(rate(llm_api_cost_usd_total[1h])) by (provider)

# 按模型的成本分布
topk(5, sum(llm_api_cost_usd_total) by (model))
```

---

### 4. 缓存命中率 / Cache Hit Rate

跟踪多层缓存的命中率。

Track cache hit rate across multiple layers.

```python
# 在缓存操作后调用
runtime_metrics.inc_cache_operations(
    operation="retrieval",
    hit=True,          # or False
    layer="l1"         # or "l2", "redis", etc.
)
```

**Prometheus查询示例：**
```promql
# 缓存命中率
sum(rate(cache_operations_total{result="hit"}[5m])) by (layer)
  /
sum(rate(cache_operations_total[5m])) by (layer)

# 缓存未命中趋势
rate(cache_operations_total{result="miss"}[5m])
```

---

### 5. 用户会话时长 / User Session Duration

跟踪用户会话时长分布。

Track user session duration distribution.

```python
# 在会话结束时调用
runtime_metrics.observe_session_duration(
    duration_seconds=1800,  # 30分钟
    user_type="premium"     # or "free", "trial"
)
```

**Prometheus查询示例：**
```promql
# P95会话时长
histogram_quantile(0.95,
  sum(rate(user_session_duration_seconds_bucket[1h])) by (le, user_type)
)

# 平均会话时长
avg(user_session_duration_seconds_sum / user_session_duration_seconds_count) by (user_type)
```

---

## 集成到Agent / Integration into Agents

### 示例：在EnhancedRouterAgent中集成

```python
from app.api.dependencies import runtime_metrics
import time

class EnhancedRouterAgent:
    def process(self, query: str):
        start = time.time()
        
        try:
            # 路由逻辑
            result = self._route_query(query)
            
            # 记录成功
            runtime_metrics.inc_agent_execution(
                agent_name="EnhancedRouterAgent",
                status="success",
                route=result["route"]
            )
            
            return result
            
        except Exception as e:
            # 记录失败
            runtime_metrics.inc_agent_execution(
                agent_name="EnhancedRouterAgent",
                status="failed",
                route="unknown"
            )
            raise
        finally:
            # 记录延迟
            duration = time.time() - start
            runtime_metrics.observe("agent_duration", duration, {
                "agent": "EnhancedRouterAgent"
            })
```

---

### 示例：在Vector RAG Agent中集成

```python
from app.api.dependencies import runtime_metrics

class VectorRAGAgent:
    def retrieve(self, query: str, strategy: str = "hybrid"):
        # 执行检索
        results = self._do_retrieval(query, strategy)
        
        # 计算质量分数
        quality_score = self._calculate_quality(results)
        
        # 记录质量指标
        runtime_metrics.observe_retrieval_quality(
            score=quality_score,
            strategy=strategy
        )
        
        return results
```

---

### 示例：跟踪LLM成本

```python
from app.api.dependencies import runtime_metrics

class LLMClient:
    def generate(self, prompt: str, model: str):
        response = self.client.generate(prompt, model)
        
        # 计算成本（示例）
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost_usd = (input_tokens * 0.00001) + (output_tokens * 0.00003)
        
        # 记录成本
        runtime_metrics.inc_llm_cost(
            cost_usd=cost_usd,
            provider="openai",
            model=model
        )
        
        return response
```

---

## Grafana仪表盘示例 / Grafana Dashboard Example

### 关键指标面板 / Key Metrics Panels

```yaml
# Panel 1: Agent成功率
- title: "Agent Success Rate"
  type: graph
  query: |
    sum(rate(agent_execution_total{status="success"}[5m])) by (agent)
    /
    sum(rate(agent_execution_total[5m])) by (agent)

# Panel 2: 检索质量趋势
- title: "Retrieval Quality Trend"
  type: graph
  query: |
    avg(retrieval_quality_score_seconds_sum / retrieval_quality_score_seconds_count) by (strategy)

# Panel 3: LLM成本（每小时）
- title: "LLM Cost per Hour"
  type: singlestat
  query: |
    sum(rate(llm_api_cost_usd_total[1h]))

# Panel 4: 缓存命中率
- title: "Cache Hit Rate"
  type: gauge
  query: |
    sum(rate(cache_operations_total{result="hit"}[5m]))
    /
    sum(rate(cache_operations_total[5m]))
```

---

## 告警规则示例 / Alerting Rules Example

### Prometheus告警配置

```yaml
groups:
  - name: rag_system_alerts
    rules:
      # 高错误率告警
      - alert: HighAgentErrorRate
        expr: |
          sum(rate(agent_execution_total{status="failed"}[5m])) by (agent)
          /
          sum(rate(agent_execution_total[5m])) by (agent)
          > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate for {{ $labels.agent }}"
          description: "Agent {{ $labels.agent }} has {{ $value | humanizePercentage }} error rate"

      # 检索质量下降告警
      - alert: LowRetrievalQuality
        expr: |
          avg(retrieval_quality_score_seconds_sum / retrieval_quality_score_seconds_count) by (strategy)
          < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low retrieval quality for {{ $labels.strategy }}"
          description: "Retrieval quality score is {{ $value }}"

      # LLM成本超标告警
      - alert: HighLLMCost
        expr: |
          sum(rate(llm_api_cost_usd_total[1h])) > 10
        for: 1h
        labels:
          severity: critical
        annotations:
          summary: "LLM cost exceeds $10/hour"
          description: "Current rate: ${{ $value }}/hour"

      # 缓存命中率过低告警
      - alert: LowCacheHitRate
        expr: |
          sum(rate(cache_operations_total{result="hit"}[5m]))
          /
          sum(rate(cache_operations_total[5m]))
          < 0.5
        for: 15m
        labels:
          severity: info
        annotations:
          summary: "Cache hit rate below 50%"
          description: "Current hit rate: {{ $value | humanizePercentage }}"
```

---

## 最佳实践 / Best Practices

1. **标签基数控制** / Control Label Cardinality
   - 避免使用用户ID作为标签（基数过高）
   - 使用user_type而非user_id
   - 限制标签值的数量

2. **采样策略** / Sampling Strategy
   - 高频操作考虑采样（如每100次记录1次）
   - 关键指标不采样

3. **命名规范** / Naming Convention
   - 使用snake_case命名
   - 包含单位（_seconds, _bytes, _total）
   - 描述性命名（retrieval_quality_score而非score）

4. **性能考虑** / Performance Considerations
   - 指标记录应该<1ms
   - 使用批量记录减少锁竞争
   - 定期清理旧数据（已实现5000条限制）

---

## 验证指标 / Verify Metrics

### 通过Prometheus端点查看

```bash
# 查看所有指标
curl http://localhost:8000/metrics

# 筛选特定指标
curl http://localhost:8000/metrics | grep agent_execution_total

# 查看标签
curl http://localhost:8000/metrics | grep 'agent_execution_total{agent="EnhancedRouterAgent"'
```

### 通过Python验证

```python
from app.api.dependencies import runtime_metrics

# 模拟一些指标
runtime_metrics.inc_agent_execution("RouterAgent", "success", "vector")
runtime_metrics.observe_retrieval_quality(0.92, "hybrid")
runtime_metrics.inc_llm_cost(0.0012, "openai", "gpt-4")

# 查看快照
snapshot = runtime_metrics.snapshot()
print(snapshot["labeled_counters"])
print(snapshot["labeled_hist"])
```

---

## 相关资源 / Related Resources

- [Prometheus查询语法](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana仪表盘设计](https://grafana.com/docs/grafana/latest/dashboards/)
- [监控最佳实践](https://sre.google/sre-book/monitoring-distributed-systems/)
