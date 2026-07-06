# QueryMind System Architecture

## Overview

这是一个完整的多agent RAG（Retrieval-Augmented Generation）系统，使用LangGraph构建工作流，支持多种检索策略和智能路由。

## Architecture Diagram

```
User Query
    ↓
[Router Agent] ────→ Route Decision (vector/graph/hybrid/react)
    ↓
[Adaptive Planner] ─→ Query Analysis & Strategy Selection
    ↓
[Entry Decider] ────→ Select Entry Point
    ↓
    ├─→ [Vector RAG Agent] ──→ Document Retrieval
    │       ↓
    │   [Vector Decider] ────→ Continue or Synthesize?
    │       ↓
    ├─→ [Graph RAG Agent] ───→ Knowledge Graph Query
    │       ↓
    │   [Graph Decider] ─────→ Need Web Search?
    │       ↓
    ├─→ [Web Research Agent] → Web Search (fallback)
    │       ↓
    ├─→ [ReAct Agent] ───────→ Multi-step Reasoning
    │       ↓
    └─→ [Synthesis Agent] ───→ Final Answer Generation
            ↓
        Final Answer
```

## Core Agents

### 1. Router Agent (`app/agents/router_agent.py`)

**功能**: 查询路由和技能选择

**职责**:
- 分析用户查询意图
- 决定检索路由 (vector/graph/hybrid/react)
- 选择执行技能 (answer_with_citations/compare_entities等)
- 分类agent类别 (cybersecurity/general/pdf_text/ai_knowledge)

**特性**:
- 使用LLM进行智能路由决策
- 支持置信度校准（confidence calibration）
- 缓存路由决策以提高性能
- 低置信度时自动触发reasoning model进行fallback
- Few-shot examples提示优化

**关键函数**:
```python
def decide_route(
    question: str, 
    use_reasoning: bool = False,
    agent_class_hint: str | None = None,
    use_llm_intent: bool = True
) -> RouteDecision
```

**输出**:
```python
RouteDecision(
    route="vector|graph|hybrid|react",
    reason="决策理由",
    skill="技能名称",
    agent_class="agent类别",
    confidence=0.0-1.0
)
```

---

### 2. Enhanced Router Agent (`app/agents/enhanced_router_agent.py`)

**功能**: 带查询分解的增强路由

**职责**:
- 支持复杂查询的自动分解
- 将单个复杂查询拆分为多个子查询
- 对每个子查询独立路由

**使用场景**:
```python
# 示例：复杂查询分解
query = "比较A和B的特点，然后分析它们的应用场景"
# 分解为:
# 1. "A的特点是什么"
# 2. "B的特点是什么"
# 3. "A和B的应用场景"
```

---

### 3. Vector RAG Agent (`app/agents/vector_rag_agent.py`)

**功能**: 基于向量检索的文档查找

**职责**:
- 语义相似度搜索
- 混合检索（dense + BM25）
- 查询扩展（query expansion）
- 动态参数调优
- 证据质量门控（evidence gating）

**检索策略**:
- `hybrid`: 向量+BM25混合（默认）
- `dense`: 纯语义向量搜索
- `bm25`: 纯关键词搜索
- `rerank`: 使用reranker模型重排序

**关键函数**:
```python
def run_vector_rag(
    question: str,
    allowed_sources: list[str] | None = None,
    retrieval_strategy: str | None = None,
    agent_class: str | None = None,
) -> dict
```

**输出**:
```python
{
    "context": "格式化的上下文字符串",
    "citations": [{"source": "...", "content": "...", "metadata": {...}}],
    "retrieved_count": 10,
    "effective_hit_count": 7,
    "retrieval_diagnostics": {...}
}
```

**优化特性**:
- 动态top_k调整（基于查询复杂度）
- 动态权重调整（vector_weight/bm25_weight）
- 查询扩展（同义词/相关词）
- Agent class文档过滤

---

### 4. Graph RAG Agent (`app/agents/graph_rag_agent.py`)

**功能**: 知识图谱查询

**职责**:
- 实体识别和关系查询
- 多跳路径搜索（2-hop paths）
- 邻居关系检索
- PDF上下文感知优化（可选）

**查询类型**:
- Entity lookup: 查找实体及其关系
- Neighbor query: 查询实体的邻居节点
- Path query: 查找实体间的连接路径

**关键函数**:
```python
def run_graph_rag(
    question: str,
    allowed_sources: list[str] | None = None,
    agent_class: str | None = None,
    retrieved_docs: list[dict] | None = None,
    enable_enhancements: bool | None = None,
) -> dict
```

**输出**:
```python
{
    "context": "格式化的图谱上下文",
    "entities": ["实体1", "实体2"],
    "neighbors": [{"entity": "...", "relation": "...", "other": "..."}],
    "paths": [{"source": "...", "middle": "...", "target": "..."}],
    "graph_signal_score": 0.0-1.0,
    "confidence": "high|medium|low"
}
```

**Fallback机制**:
- 图谱查询失败时自动fallback到vector RAG
- 图谱返回空结果时自动fallback
- 低质量文档时跳过图谱查询

---

### 5. ReAct Agent (`app/agents/react_agent.py`)

**功能**: 基于ReAct模式的多步推理agent

**职责**:
- 迭代式思考-行动-观察循环
- 自动选择和组合工具
- 多轮信息收集和综合

**ReAct循环**:
```
1. Think (思考): 分析当前状态，决定下一步
2. Act (行动): 执行工具调用
3. Observe (观察): 分析工具返回结果
4. Repeat: 重复直到信息充分
```

**可用工具**:
- `vector_search`: 调用Vector RAG Agent
- `graph_query`: 调用Graph RAG Agent
- `web_search`: 调用Web Research Agent
- `finish`: 结束并生成答案

**关键函数**:
```python
def run_react_agent(
    question: str,
    memory_context: str = "",
    allowed_sources: list[str] | None = None,
    retrieval_strategy: str | None = None,
    use_reasoning: bool = False,
    max_iterations: int = 5,
) -> dict
```

**输出**:
```python
{
    "answer": "最终答案",
    "react_history": [{"iteration": 1, "thought": {...}, "observation": {...}}],
    "iterations_used": 3,
    "contexts": {"vector": "...", "graph": "...", "web": "..."},
    "vector_result": {...},
    "graph_result": {...},
    "web_result": {...}
}
```

**使用场景**:
- 需要多步推理的复杂查询
- "先比较再分析"类型的查询
- 需要多个数据源的综合查询
- 探索性查询

---

### 6. Synthesis Agent (`app/agents/synthesis_agent.py`)

**功能**: 最终答案生成和综合

**职责**:
- 融合多个数据源（vector/graph/web）
- 生成连贯、准确的答案
- 引用管理和事实验证
- Chain-of-Thought推理
- 语言检测和适配

**引用规则** (Citation-First Generation):
- 每个事实性陈述必须有引用 `[doc_id:page]`
- 无引用的信息必须使用模糊语言
- 不编造或推测上下文中未提供的信息

**关键函数**:
```python
def synthesize_answer(
    question: str,
    skill_name: str,
    memory_context: str = "",
    vector_context: str = "",
    graph_context: str = "",
    web_context: str = "",
    use_reasoning: bool = False,
    force_language: str = "",
    session_id: str = "",
) -> dict
```

**输出**:
```python
{
    "answer": "综合答案（带引用）",
    "detected_language": "zh|en",
    "skill_used": "answer_with_citations",
    "reasoning_used": False
}
```

---

### 7. Web Research Agent (`app/agents/web_research_agent.py`)

**功能**: 互联网搜索补充

**职责**:
- 本地知识库不足时搜索互联网
- 获取最新信息和新闻
- 验证和补充本地信息
- 基于可信度评分过滤搜索结果
- 支持白名单和TLD评分两种安全模式

**关键函数**:
```python
def run_web_research(question: str) -> dict
```

**输出**:
```python
{
    "context": str,           # 格式化的搜索结果 [WEB] 标题\nURL\n摘要
    "citations": list[dict],  # 引用列表（包含source_score可信度评分）
    "used": bool,             # 是否成功检索到符合标准的结果
    "error": str              # 错误信息（可选）
}
```

**可信度评分机制**:

**模式1 - 白名单模式** (配置 `WEB_DOMAIN_ALLOWLIST`):
- 在白名单中: 1.0分 (通过)
- 不在白名单: 0.0分 (拒绝)

**模式2 - TLD评分模式** (未配置白名单):
- `.gov`, `.edu`: 0.9分
- 可信技术域名 (github.com, stackoverflow.com等): 0.8分
- `.org`: 0.7分
- 其他域名: 0.4分
- 默认阈值: 0.6 (可通过 `WEB_MIN_SOURCE_SCORE` 调整)

**使用场景**:
- ✅ 时效性查询（"最新"、"今天"、"当前"）
- ✅ 本地检索结果不足（<3条）
- ✅ 查询关于最新事件/新闻
- ✅ 需要外部验证的信息
- ❌ 内部/专有知识查询
- ❌ 隐私敏感查询

**触发条件**:
1. Graph Decider自动触发（图谱查询失败或低质量）
2. ReAct Agent主动调用web_search工具
3. API参数 `use_web_fallback=true` 显式启用

**配置示例**:
```bash
# 严格白名单模式（高安全）
WEB_DOMAIN_ALLOWLIST="github.com,stackoverflow.com,owasp.org,nvd.nist.gov"

# TLD评分模式（平衡）
WEB_MIN_SOURCE_SCORE=0.6

# 宽松模式（开发测试）
WEB_MIN_SOURCE_SCORE=0.4
```

**性能特性**:
- 最多返回5条结果（控制成本和处理时间）
- 典型响应时间: 1-3秒
- 建议实施缓存（TTL: 1-24小时）
- 支持并行搜索（多查询场景）

**安全特性**:
- 域名过滤（防止访问不可信网站）
- 结果数量限制（防止信息过载）
- 错误隔离（搜索失败不影响整体流程）
- 可信度透明（每个引用包含source_score）

**详细文档**: 参见 [WEB_RESEARCH_AGENT.md](WEB_RESEARCH_AGENT.md)

---

### 8. Enhanced RAG Workflow (`app/agents/enhanced_rag_workflow.py`)

**功能**: 质量保证工作流

**职责**:
- 路由验证和重试
- 检索质量评估
- 答案验证和改进
- 质量报告生成

**质量等级**:
- `high` (≥0.85): 高置信度，可靠答案
- `medium` (0.7-0.85): 中等质量，需验证
- `low` (0.5-0.7): 低质量，谨慎使用
- `very_low` (<0.5): 极低质量，需人工审核

---

## Workflow Execution

### LangGraph工作流 (`app/graph/workflow.py`)

工作流节点顺序:
```
START → router → adaptive_planner → entry_decider
                                    ↓
            ┌───────────────────────┴───────────────────────┐
            ↓                       ↓                       ↓
         vector                  graph                   react
            ↓                       ↓                       ↓
    vector_decider          graph_decider                 END
            ↓                       ↓
            └───────────┬───────────┘
                        ↓
                       web
                        ↓
                   synthesis
                        ↓
                       END
```

### State Management (`app/graph/state.py`)

工作流状态包含:
```python
class GraphState(TypedDict):
    question: str
    memory_context: str
    route: str
    skill: str
    agent_class: str
    confidence: float
    next_step: str
    vector_result: dict
    graph_result: dict
    web_result: dict
    answer: str
    execution_id: str
    # ... 更多字段
```

---

## Agent Integration Points

### 1. API Endpoints

**标准查询**: `/api/v1/query`
```python
POST /api/v1/query
{
    "question": "用户问题",
    "session_id": "会话ID",
    "use_web_fallback": false,
    "use_reasoning": false,
    "agent_class_hint": "general",
    "retrieval_strategy": "hybrid"
}
```

**流式查询**: `/api/v1/query/stream`
```python
POST /api/v1/query/stream
FormData:
  question: "用户问题"
  session_id: "会话ID"
  use_web_fallback: false
  use_reasoning: false
```

**增强查询**: `/api/v1/enhanced/query`
```python
POST /api/v1/enhanced/query
{
    "query": "用户问题",
    "session_id": "会话ID",
    "enable_context_tracking": true
}
```

### 2. Service Integration

**Agent Document Filter** (`app/services/agent_document_filter.py`):
- 根据agent类别自动过滤文档源
- 支持多租户文档隔离

**Agent Execution Tracker** (`app/services/agent_execution_tracker.py`):
- 追踪agent执行历史
- 记录执行时间和结果
- 支持执行链分析

**Query Intent Classifier** (`app/services/llm_intent_classifier.py`):
- 使用LLM分类查询意图
- 自动识别agent类别
- 置信度评估

---

## Configuration

### Environment Variables

```bash
# Router配置
ENABLE_QUERY_DECOMPOSITION=false
ENABLE_CALIBRATION=true

# Graph RAG配置
GRAPH_RAG_ENHANCED=true
GRAPH_RAG_MIN_PDF_QUALITY=0.3

# Query Expansion配置
QUERY_EXPANSION_ENABLED=true
QUERY_EXPANSION_MAX_RATIO=3.0

# Consistency Guard
CONSISTENCY_GUARD_ENABLED=true
CONSISTENCY_GUARD_SIMILARITY_THRESHOLD=0.85

# Web Research配置
WEB_DOMAIN_ALLOWLIST=""  # 白名单域名（逗号分隔），留空则使用TLD评分
WEB_MIN_SOURCE_SCORE=0.6  # 最低可信度阈值（仅在未设置白名单时生效）
```

### Agent Configuration (`app/agents/agent_config.py`)

```python
# Valid routes
VALID_ROUTES = ["vector", "graph", "hybrid", "react", "web"]

# Valid skills
VALID_SKILLS = [
    "answer_with_citations",
    "compare_entities",
    "timeline_builder",
    "web_fact_check",
    "cyber_attack_analysis",
    "cyber_defense_hardening",
    "incident_response_playbook",
    "ai_knowledge_assistant",
    "pdf_text_reader",
]

# Valid agent classes
VALID_AGENT_CLASSES = ["general", "cybersecurity", "pdf_text", "ai_knowledge"]
```

---

## Performance Optimization

### 1. Caching
- Router决策缓存（避免重复路由）
- 查询结果缓存（相同查询直接返回）
- 流式事件重放（Stream replay）

### 2. Parallel Execution
- Vector和Graph检索可并行
- 质量评估并行执行
- 独立子查询并行处理

### 3. Adaptive Parameters
- 动态调整top_k（基于查询复杂度）
- 动态调整检索权重
- 自适应超时设置

### 4. Fallback Strategies
- Graph失败 → Vector fallback
- 低置信度路由 → Reasoning model fallback
- 本地不足 → Web search fallback

---

## Testing

### Unit Tests
```bash
# Test individual agents
pytest tests/unit/test_enhanced_vector_rag_agent.py
pytest tests/unit/test_synthesis_agent.py

# Test router
pytest tests/test_agent_classifier.py
```

### Integration Tests
```bash
# Test full workflow
pytest tests/test_react_agent.py
```

---

## Troubleshooting

### Common Issues

**1. Router低置信度**
- 检查query_examples.py中的few-shot examples
- 启用reasoning model fallback
- 查看router_calibration.py的校准设置

**2. 检索结果不足**
- 检查allowed_sources过滤
- 调整retrieval_strategy
- 启用query_expansion

**3. Graph RAG失败**
- 检查Neo4j连接
- 查看graph_signal_score
- 验证fallback是否正确触发

**4. ReAct循环不收敛**
- 检查max_iterations设置
- 查看ReAct history
- 验证工具返回格式

**5. Web Research失败**
- **搜索API失败**: 检查网络连接、代理设置、API配额
  ```bash
  curl -I https://duckduckgo.com
  tail -f logs/app.log | grep "web_search"
  ```
- **所有结果被过滤**: 白名单过严或阈值过高
  ```bash
  # 临时降低阈值测试
  WEB_MIN_SOURCE_SCORE=0.4
  # 或清空白名单使用TLD评分
  unset WEB_DOMAIN_ALLOWLIST
  ```
- **搜索超时**: 在search_web()中添加timeout参数
- **无返回结果但无错误**: 检查过滤日志，可能所有来源都低于阈值

---

## Best Practices

### 1. Agent Selection
- 简单事实查询 → Vector RAG
- 关系型查询 → Graph RAG
- 对比分析 → Hybrid
- 复杂推理 → ReAct

### 2. Performance
- 使用缓存减少重复计算
- 合理设置超时
- 启用并行执行
- 监控执行追踪

### 3. Quality
- 启用Enhanced RAG Workflow进行关键查询
- 使用reasoning model提高质量
- 配置质量阈值
- 记录和分析失败案例

---

## Future Enhancements

### Planned Features
1. **Agent协作增强**
   - 多agent投票机制
   - 交叉验证
   - 共识算法

2. **自适应学习**
   - 基于反馈的路由优化
   - 动态few-shot examples
   - 个性化agent选择

3. **分布式执行**
   - Agent负载均衡
   - 分布式缓存
   - 跨节点协调

4. **高级推理**
   - Tree-of-Thought
   - Self-consistency
   - Multi-agent debate

---

## References

- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- ReAct Paper: https://arxiv.org/abs/2210.03629
- RAG Survey: https://arxiv.org/abs/2312.10997
