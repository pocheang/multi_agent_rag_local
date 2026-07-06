# Agent Quick Reference Guide

快速查找和使用多agent RAG系统的指南。

## Quick Navigation

- [Agent选择决策树](#agent选择决策树)
- [常见使用场景](#常见使用场景)
- [API快速参考](#api快速参考)
- [配置速查](#配置速查)
- [故障排查](#故障排查)

---

## Agent选择决策树

```
用户查询
    │
    ├─ 简单事实查询？
    │   └─ YES → Vector RAG Agent
    │       例：什么是Transformer？
    │
    ├─ 关系/依赖查询？
    │   └─ YES → Graph RAG Agent
    │       例：A和B之间有什么关系？
    │
    ├─ 需要对比分析？
    │   └─ YES → Hybrid (Vector + Graph)
    │       例：比较A和B的优缺点
    │
    ├─ 多步推理/复杂查询？
    │   └─ YES → ReAct Agent
    │       例：分析X，然后基于分析结果推荐Y
    │
    └─ 需要最新信息？
        └─ YES → Vector + Web Fallback
            例：2024年最新的...
```

---

## 常见使用场景

### 1. 简单Q&A
```python
# 场景：查询文档中的事实
# 推荐：Vector RAG

from app.agents.vector_rag_agent import run_vector_rag

result = run_vector_rag(
    question="什么是Docker容器？",
    retrieval_strategy="hybrid"
)

print(result["answer"])
```

### 2. 实体关系查询
```python
# 场景：查询实体间关系
# 推荐：Graph RAG

from app.agents.graph_rag_agent import run_graph_rag

result = run_graph_rag(
    question="Kubernetes和Docker的关系",
)

print(f"实体: {result['entities']}")
print(f"关系: {result['neighbors']}")
```

### 3. 对比分析
```python
# 场景：对比两个概念
# 推荐：Hybrid + compare_entities skill

from app.graph.workflow import run_query

result = run_query(
    question="比较REST API和GraphQL的优缺点",
    use_reasoning=True
)

print(result["answer"])
```

### 4. 多步推理
```python
# 场景：需要多步推理的复杂查询
# 推荐：ReAct Agent

from app.agents.react_agent import run_react_agent

result = run_react_agent(
    question="分析微服务架构的优势，然后推荐适合的技术栈",
    use_reasoning=True,
    max_iterations=5
)

print(f"推理历史: {result['react_history']}")
print(f"答案: {result['answer']}")
```

### 5. 网络搜索增强
```python
# 场景：本地知识库可能不足
# 推荐：Vector + Web Fallback

from app.graph.workflow import run_query

result = run_query(
    question="2024年人工智能领域的最新突破",
    use_web_fallback=True
)

print(f"使用了网络搜索: {result['web_result']['used']}")
print(result["answer"])
```

### 6. 高质量查询（质量保证）
```python
# 场景：关键业务查询，需要质量保证
# 推荐：Enhanced RAG Workflow

from app.agents.enhanced_rag_workflow import EnhancedRAGWorkflow

workflow = EnhancedRAGWorkflow(
    max_route_retries=1,
    max_answer_retries=1,
    enable_context_tracking=True
)

result = await workflow.execute_query(
    query="详细解释零信任安全架构",
    user_id="user123",
    session_id="session456"
)

print(f"质量等级: {result['quality_report'].quality_level}")
print(f"综合分数: {result['quality_report'].overall_score}")
```

---

## API快速参考

### REST API调用

#### 1. 标准查询
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "question": "什么是Kubernetes？",
    "session_id": "session123",
    "use_reasoning": false,
    "use_web_fallback": false,
    "retrieval_strategy": "hybrid"
  }'
```

#### 2. 流式查询
```bash
curl -X POST http://localhost:8000/api/v1/query/stream \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "question=解释Docker容器技术" \
  -F "session_id=session123" \
  -F "use_reasoning=true"
```

#### 3. 增强质量查询
```bash
curl -X POST http://localhost:8000/api/v1/enhanced/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "分析微服务架构的最佳实践",
    "session_id": "session123",
    "enable_context_tracking": true,
    "agent_class_hint": "general"
  }'
```

### Python SDK调用

```python
# 直接调用工作流
from app.graph.workflow import run_query

result = run_query(
    question="你的问题",
    use_web_fallback=False,
    use_reasoning=False,
    memory_context="",
    allowed_sources=None,
    agent_class_hint=None,
    retrieval_strategy="hybrid",
    force_language="zh",
    session_id="session123"
)

# 访问结果
answer = result["answer"]
route = result["route"]
citations = result["vector_result"]["citations"]
```

---

## 配置速查

### 环境变量

```bash
# Router配置
ENABLE_QUERY_DECOMPOSITION=false          # 启用查询分解
ENABLE_CALIBRATION=true                   # 启用置信度校准

# Graph RAG配置
GRAPH_RAG_ENHANCED=true                   # 启用增强图谱
GRAPH_RAG_MIN_PDF_QUALITY=0.3            # 最小PDF质量阈值

# Query Expansion
QUERY_EXPANSION_ENABLED=true              # 启用查询扩展
QUERY_EXPANSION_MAX_RATIO=3.0            # 最大扩展比例

# Consistency Guard
CONSISTENCY_GUARD_ENABLED=true            # 启用一致性守护
CONSISTENCY_GUARD_SIMILARITY_THRESHOLD=0.85

# Performance
QUERY_REQUEST_TIMEOUT_MS=20000           # 查询超时(毫秒)
MAX_CONTEXT_CHUNKS=10                    # 最大上下文块数
```

### Agent参数速查表

| Agent | 关键参数 | 默认值 | 说明 |
|-------|---------|--------|------|
| Vector RAG | `retrieval_strategy` | `"hybrid"` | hybrid/dense/bm25/rerank |
| Vector RAG | `allowed_sources` | `None` | 文档源过滤 |
| Graph RAG | `enable_enhancements` | `True` | 启用PDF感知优化 |
| Graph RAG | `retrieved_docs` | `None` | 用于质量分析 |
| ReAct | `max_iterations` | `5` | 最大推理轮数 |
| ReAct | `use_reasoning` | `False` | 使用推理模型 |
| Synthesis | `force_language` | `""` | 强制语言(zh/en) |
| Router | `use_llm_intent` | `True` | 使用LLM意图分类 |

---

## 检索策略对比

| 策略 | 适用场景 | 优势 | 劣势 |
|------|---------|------|------|
| **hybrid** | 通用查询 | 平衡语义和关键词 | 稍慢 |
| **dense** | 语义理解 | 概念相似度高 | 关键词匹配弱 |
| **bm25** | 精确匹配 | 快速，关键词准确 | 语义理解弱 |
| **rerank** | 高质量要求 | 结果最优 | 最慢 |

---

## Agent性能对比

| Agent | 平均延迟 | 资源消耗 | 适用查询复杂度 |
|-------|---------|---------|---------------|
| Vector RAG | ~200ms | 低 | 简单-中等 |
| Graph RAG | ~300ms | 中 | 中等 |
| Hybrid | ~400ms | 中 | 中等-复杂 |
| ReAct | ~2s | 高 | 复杂 |
| Enhanced | ~500ms | 高 | 关键业务 |

---

## 故障排查

### 问题1: Router置信度过低

**症状**: 日志显示 `Low confidence detected: 0.45`

**原因**:
- 查询模糊或不明确
- Few-shot examples不够覆盖
- 路由模型性能不足

**解决方案**:
```python
# 方案1: 启用reasoning model fallback
result = decide_route(question, use_reasoning=True)

# 方案2: 提供agent_class_hint
result = decide_route(question, agent_class_hint="cybersecurity")

# 方案3: 更新router examples
# 编辑 app/agents/router_examples.py
```

### 问题2: 检索结果为空

**症状**: `retrieved_count: 0`

**原因**:
- allowed_sources过滤太严格
- 文档库中没有相关内容
- 查询词不匹配

**解决方案**:
```python
# 方案1: 检查allowed_sources
result = run_vector_rag(question, allowed_sources=None)  # 不过滤

# 方案2: 启用query expansion
# 在.env中设置 QUERY_EXPANSION_ENABLED=true

# 方案3: 降低相似度阈值
# 编辑 app/agents/agent_config.py
DENSE_SCORE_THRESHOLD = 0.3  # 降低阈值
```

### 问题3: Graph RAG失败

**症状**: `"error": "ServiceUnavailable"`

**原因**:
- Neo4j连接失败
- 图谱数据库未初始化
- 网络问题

**解决方案**:
```bash
# 检查Neo4j状态
docker ps | grep neo4j

# 重启Neo4j
docker restart neo4j

# 验证连接
python -c "from app.tools.graph_tools import graph_lookup; print(graph_lookup('test'))"

# 查看fallback是否正确触发
# 应该看到 "Falling back to vector RAG due to graph lookup error"
```

### 问题4: ReAct不收敛

**症状**: `iterations_used: 5` (达到最大值)

**原因**:
- 查询过于复杂
- 工具返回格式错误
- LLM输出不符合预期

**解决方案**:
```python
# 方案1: 增加max_iterations
result = run_react_agent(question, max_iterations=10)

# 方案2: 启用reasoning model
result = run_react_agent(question, use_reasoning=True)

# 方案3: 查看推理历史
print(result['react_history'])
# 分析哪一步出错

# 方案4: 简化查询
# 将复杂查询拆分为多个简单查询
```

### 问题5: 答案质量低

**症状**: 答案不准确或不完整

**原因**:
- 检索质量差
- 上下文不足
- 合成策略不当

**解决方案**:
```python
# 方案1: 使用Enhanced RAG Workflow
from app.agents.enhanced_rag_workflow import EnhancedRAGWorkflow
workflow = EnhancedRAGWorkflow()
result = await workflow.execute_query(query=question)

# 方案2: 启用reasoning model
result = run_query(question, use_reasoning=True)

# 方案3: 调整检索策略
result = run_query(question, retrieval_strategy="rerank")

# 方案4: 检查retrieval diagnostics
diagnostics = result['vector_result']['retrieval_diagnostics']
print(f"检索质量: {diagnostics}")
```

---

## 调试技巧

### 1. 启用详细日志
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 或在.env中设置
LOG_LEVEL=DEBUG
```

### 2. 查看执行追踪
```python
from app.services.agent_execution_tracker import AgentExecutionTracker

tracker = AgentExecutionTracker.get_instance()
trace = tracker.get_execution_trace(execution_id)

print(f"执行链: {trace['execution_chain']}")
print(f"总耗时: {trace['total_duration_ms']}ms")
```

### 3. 检查路由决策
```python
from app.agents.router_agent import decide_route

decision = decide_route("你的查询")
print(f"路由: {decision.route}")
print(f"原因: {decision.reason}")
print(f"技能: {decision.skill}")
print(f"置信度: {decision.confidence}")
```

### 4. 测试单个Agent
```python
# 测试Vector RAG
from app.agents.vector_rag_agent import run_vector_rag
result = run_vector_rag("测试查询")

# 测试Graph RAG
from app.agents.graph_rag_agent import run_graph_rag
result = run_graph_rag("测试查询")

# 测试ReAct
from app.agents.react_agent import run_react_agent
result = run_react_agent("测试查询", max_iterations=3)
```

---

## 性能优化建议

### 1. 使用缓存
```python
# 查询结果会自动缓存
# 相同查询第二次调用会返回缓存结果

# 清空缓存
from app.api.dependencies import query_result_cache
query_result_cache.clear()
```

### 2. 并行执行
```python
# Vector和Graph可以并行执行
# 工作流会自动处理并行

# 手动并行
import asyncio

async def parallel_retrieval():
    vector_task = asyncio.create_task(run_vector_rag_async(question))
    graph_task = asyncio.create_task(run_graph_rag_async(question))
    
    vector_result, graph_result = await asyncio.gather(
        vector_task, graph_task
    )
    return vector_result, graph_result
```

### 3. 调整超时
```python
# 在.env中设置
QUERY_REQUEST_TIMEOUT_MS=30000  # 30秒

# 或在代码中
from app.services.request_context import request_context

with request_context(timeout_ms=30000):
    result = run_query(question)
```

### 4. 优化检索参数
```python
# 减少top_k
result = run_vector_rag(question, top_k=5)  # 默认10

# 使用更快的策略
result = run_vector_rag(question, retrieval_strategy="dense")
```

---

## 监控和指标

### 关键指标
```python
from app.api.dependencies import runtime_metrics

# 查询成功率
success_rate = runtime_metrics.get("query_success_total")

# 缓存命中率
cache_hits = runtime_metrics.get("query_cache_hit_total")

# 平均响应时间
avg_latency = runtime_metrics.get("query_latency_ms_avg")
```

### Agent执行统计
```python
from app.services.agent_execution_tracker import AgentExecutionTracker

tracker = AgentExecutionTracker.get_instance()
stats = tracker.get_execution_stats()

print(f"总执行次数: {stats['total_executions']}")
print(f"平均耗时: {stats['avg_duration_ms']}ms")
print(f"失败率: {stats['failure_rate']}")
```

---

## 最佳实践总结

### DO ✅
- 为简单查询使用Vector RAG
- 为关系查询使用Graph RAG
- 为复杂推理使用ReAct
- 启用缓存提高性能
- 使用Enhanced Workflow保证质量
- 监控agent执行统计
- 合理设置超时
- 启用日志用于调试

### DON'T ❌
- 对所有查询都使用ReAct（性能开销大）
- 禁用缓存（除非调试）
- 设置过低的超时时间
- 忽略置信度分数
- 不检查retrieval diagnostics
- 对简单查询启用reasoning model
- 过度过滤allowed_sources

---

## 快速命令

```bash
# 测试单个agent
conda activate rag-local
python -c "from app.agents.vector_rag_agent import run_vector_rag; print(run_vector_rag('test'))"

# 运行完整查询
python -c "from app.graph.workflow import run_query; print(run_query('什么是Docker？'))"

# 检查配置
python -c "from app.core.config import get_settings; print(get_settings().model_dump())"

# 清空缓存
python -c "from app.api.dependencies import query_result_cache; query_result_cache.clear()"

# 查看执行追踪
python -c "from app.services.agent_execution_tracker import AgentExecutionTracker; print(AgentExecutionTracker.get_instance().get_execution_stats())"
```

---

## 更多资源

- [完整架构文档](./AGENT_ARCHITECTURE.md)
- [API参考文档](./api-reference.md)
- [质量保证Agent文档](./quality-assurance-agents/)
- [测试示例](../tests/)
