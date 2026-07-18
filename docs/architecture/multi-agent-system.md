# 多智能体系统 (Multi-Agent System)

本文档详细介绍基于 LangGraph 的多智能体协同系统的设计、实现和使用。

## 目录

- [快速参考](#快速参考)
- [概述](#概述)
- [LangGraph 基础](#langgraph-基础)
- [工作流架构](#工作流架构)
- [智能体详解](#智能体详解)
- [状态管理](#状态管理)
- [路由逻辑](#路由逻辑)
- [执行追踪](#执行追踪)
- [性能优化](#性能优化)

---

## 快速参考

### 智能体速查

| 智能体 | 功能 | 输入 | 输出 |
|--------|------|------|------|
| **Router** | 分析查询意图 | question | route, skill, agent_class |
| **Adaptive Planner** | 自适应规划 | question | adaptive_level, min_hits |
| **Entry Decider** | 入口决策 | route | next_step |
| **Vector** | 向量检索 | question | vector_result |
| **Vector Decider** | 向量决策 | vector_result | next_step |
| **Graph** | 图检索 | question | graph_result |
| **Graph Decider** | 图决策 | graph_result | next_step |
| **Web** | 网络搜索 | question | web_result |
| **Synthesis** | 答案合成 | all_results | answer |

### 路由策略速查

| Route | 说明 | 执行路径 | 适用场景 |
|-------|------|---------|---------|
| `vector` | 仅向量检索 | Router → Vector → Synthesis | 简单事实查询 |
| `graph` | 仅图检索 | Router → Graph → Synthesis | 实体关系查询 |
| `hybrid` | 向量+图 | Router → Vector → Graph → Synthesis | 复杂推理查询 |

### GraphState 核心字段

```python
class GraphState(TypedDict, total=False):
    # 输入
    question: str                    # 用户问题
    session_id: str                  # 会话 ID
    use_web_fallback: bool          # 是否启用网络搜索
    
    # 路由决策
    route: str                       # vector/graph/hybrid
    skill: str                       # 技能类型
    agent_class: str                # 智能体类别
    
    # 检索结果
    vector_result: dict             # 向量检索结果
    graph_result: dict              # 图检索结果
    web_result: dict                # 网络搜索结果
    
    # 输出
    answer: str                     # 最终答案
    next_step: str                  # 下一步操作
```

### 工作流构建速查

```python
from langgraph.graph import StateGraph, START, END

# 1. 创建图
graph = StateGraph(GraphState)

# 2. 添加节点
graph.add_node("router", router_node)
graph.add_node("vector", vector_node)
graph.add_node("synthesis", synthesis_node)

# 3. 添加边
graph.add_edge(START, "router")
graph.add_edge("router", "vector")
graph.add_edge("vector", "synthesis")
graph.add_edge("synthesis", END)

# 4. 编译
workflow = graph.compile()

# 5. 运行
result = workflow.invoke({"question": "什么是 RAG？"})
```

### 条件路由速查

```python
# 条件路由函数
def route_after_vector(state: GraphState) -> str:
    route = state.get("route")
    
    if route == "hybrid":
        return "graph"  # 继续执行图检索
    elif evidence_sufficient(state["vector_result"]):
        return "synthesis"  # 证据充分，生成答案
    else:
        return "web"  # 证据不足，网络搜索

# 添加条件边
graph.add_conditional_edges(
    "vector",
    route_after_vector,
    {
        "graph": "graph",
        "web": "web",
        "synthesis": "synthesis"
    }
)
```

### 常用操作速查

**运行查询**:
```python
from app.graph.workflow import run_query

result = run_query(
    question="什么是 RAG？",
    session_id="session_123",
    use_web_fallback=True,
    use_reasoning=False
)

print(result["answer"])
```

**流式运行**:
```python
async for event in run_query_stream(question="什么是 RAG？"):
    if event["type"] == "token":
        print(event["content"], end="")
```

**自定义智能体**:
```python
def custom_node(state: GraphState) -> GraphState:
    """自定义节点函数"""
    question = state["question"]
    
    # 处理逻辑
    result = process(question)
    
    # 返回更新
    return {
        "custom_result": result,
        "next_step": "synthesis"
    }

# 添加到工作流
graph.add_node("custom", custom_node)
```

### 调试速查

**打印工作流图**:
```python
from app.graph.workflow import build_workflow

workflow = build_workflow()
print(workflow.get_graph().draw_ascii())
```

**查看执行追踪**:
```python
from app.services.agent_execution_tracker import get_tracker

tracker = get_tracker()
executions = tracker.list_executions(limit=10)

for exec in executions:
    print(f"{exec['agent']}: {exec['duration_ms']}ms")
```

**调试单个节点**:
```python
from app.graph.nodes import router_node

state = {"question": "什么是 RAG？"}
result = router_node(state)
print(result)
```

### 性能优化速查

**并行执行**:
```python
# Hybrid 模式自动并行
if route == "hybrid":
    # Vector 和 Graph 并行执行
    pass
```

**超时控制**:
```python
# 在 .env 中设置
QUERY_REQUEST_TIMEOUT_MS=30000  # 30秒
```

**熔断器**:
```python
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_BREAKER_FAIL_THRESHOLD=3
CIRCUIT_BREAKER_COOLDOWN_SECONDS=30
```

### 常见问题速查

**Q: 如何添加新智能体？**
1. 在 `app/agents/` 创建智能体文件
2. 在 `app/graph/nodes/` 创建节点包装
3. 在 `workflow.py` 中添加节点和边

**Q: 如何修改路由逻辑？**
编辑 `app/graph/routing/route_logic.py` 中的路由函数

**Q: 如何查看执行流程？**
启用追踪：`enable_tracking=True`

**Q: 智能体执行超时？**
增大 `QUERY_REQUEST_TIMEOUT_MS` 或优化智能体逻辑

---

## 概述

QueryMind（智询） 系统采用 **LangGraph** 框架实现多智能体协同工作流。系统包含 9 个核心节点，通过智能路由实现动态的查询处理。

### 核心智能体

1. **Router** - 路由决策
2. **Adaptive Planner** - 自适应规划
3. **Entry Decider** - 入口决策
4. **Vector** - 向量检索
5. **Vector Decider** - 向量决策
6. **Graph** - 图检索
7. **Graph Decider** - 图决策
8. **Web** - 网络搜索
9. **Synthesis** - 答案合成

### 设计目标

- ✅ **灵活路由**: 根据查询特征动态选择执行路径
- ✅ **并发执行**: 向量和图检索可并行执行
- ✅ **错误恢复**: 节点失败时自动降级或重试
- ✅ **可观测性**: 完整的执行追踪和监控
- ✅ **可扩展性**: 易于添加新的智能体节点

---

## LangGraph 基础

### 什么是 LangGraph？

LangGraph 是 LangChain 的图编排框架，用于构建有状态的多智能体应用。

### 核心概念

#### 1. State (状态)

```python
from typing import TypedDict

class GraphState(TypedDict, total=False):
    question: str                    # 用户问题
    route: str                       # 路由策略 (vector/graph/hybrid)
    vector_result: dict             # 向量检索结果
    graph_result: dict              # 图检索结果
    web_result: dict                # 网络搜索结果
    answer: str                     # 最终答案
    next_step: str                  # 下一步操作
```

#### 2. Node (节点)

节点是处理函数，接收状态并返回更新后的状态：

```python
def router_node(state: GraphState) -> GraphState:
    # 分析查询，决定路由
    decision = decide_route(state["question"])
    return {
        "route": decision.route,
        "skill": decision.skill
    }
```

#### 3. Edge (边)

连接节点的路径：

**固定边**：
```python
graph.add_edge("router", "adaptive_planner")
```

**条件边**：
```python
graph.add_conditional_edges(
    "vector_decider",
    route_by_next_step,
    {
        "graph": "graph",
        "web": "web",
        "synthesis": "synthesis"
    }
)
```

---

## 工作流架构

### 完整工作流图

```
START
  │
  ↓
┌─────────────┐
│   Router    │  ← 分析查询意图
└──────┬──────┘
       │
       ↓
┌─────────────┐
│  Adaptive   │  ← 自适应规划
│  Planner    │
└──────┬──────┘
       │
       ↓
┌─────────────┐
│   Entry     │  ← 入口决策
│  Decider    │
└──────┬──────┘
       │
       ├─→ vector ──→ Vector ──→ Vector Decider ┐
       │                                          │
       ├─→ graph  ──→ Graph  ──→ Graph Decider  ├→ Synthesis → END
       │                                          │
       ├─→ web    ──→ Web     ──────────────────┘
       │
       └─→ synthesis → Synthesis → END
```

### 工作流构建代码

```python
from langgraph.graph import StateGraph, START, END

def build_workflow():
    graph = StateGraph(GraphState)
    
    # 添加节点
    graph.add_node("router", router_node)
    graph.add_node("adaptive_planner", adaptive_planner_node)
    graph.add_node("entry_decider", entry_decider_node)
    graph.add_node("vector", vector_node)
    graph.add_node("vector_decider", vector_decider_node)
    graph.add_node("graph", graph_node)
    graph.add_node("graph_decider", graph_decider_node)
    graph.add_node("web", web_node)
    graph.add_node("synthesis", synthesis_node)
    
    # 添加固定边
    graph.add_edge(START, "router")
    graph.add_edge("router", "adaptive_planner")
    graph.add_edge("adaptive_planner", "entry_decider")
    graph.add_edge("vector", "vector_decider")
    graph.add_edge("graph", "graph_decider")
    graph.add_edge("web", "synthesis")
    graph.add_edge("synthesis", END)
    
    # 添加条件边
    graph.add_conditional_edges(
        "entry_decider",
        route_by_next_step,
        {
            "vector": "vector",
            "graph": "graph",
            "web": "web",
            "synthesis": "synthesis"
        }
    )
    
    graph.add_conditional_edges(
        "vector_decider",
        route_by_next_step,
        {"graph": "graph", "web": "web", "synthesis": "synthesis"}
    )
    
    graph.add_conditional_edges(
        "graph_decider",
        route_by_next_step,
        {"web": "web", "synthesis": "synthesis"}
    )
    
    return graph.compile()
```

---

## 智能体详解

### 1. Router Agent (路由智能体)

**职责**: 分析查询意图，决定执行策略

**输入**:
- `question`: 用户问题
- `agent_class_hint`: 可选的智能体类别提示

**输出**:
- `route`: vector | graph | hybrid
- `skill`: 技能类型
- `agent_class`: 智能体类别
- `reason`: 决策原因

**路由策略**:

| Route | 适用场景 | 示例 |
|-------|---------|------|
| `vector` | 文本检索足够 | "什么是 RAG？" |
| `graph` | 需要实体关系 | "A 和 B 有什么关系？" |
| `hybrid` | 需要文本+关系 | "分析 X 的影响因素" |

**实现代码**:

```python
def decide_route(question: str, use_llm_intent: bool = True) -> RouteDecision:
    # 使用 LLM 进行意图分类
    if use_llm_intent:
        intent_result = classify_intent_with_llm(question)
        agent_class = intent_result["agent_class"]
    else:
        # 回退到基于规则的分类
        agent_class = classify_agent_class(question)
    
    # 根据智能体类别选择技能
    skill = pick_cyber_skill(question, agent_class)
    
    # 决定路由
    if "关系" in question or "依赖" in question:
        route = "graph"
    elif needs_hybrid(question):
        route = "hybrid"
    else:
        route = "vector"
    
    return RouteDecision(
        route=route,
        skill=skill,
        agent_class=agent_class,
        reason=f"Based on intent classification"
    )
```

---

### 2. Adaptive Planner (自适应规划器)

**职责**: 根据查询特征和系统负载，调整检索参数

**自适应策略**:

```python
# 简单查询 - 快速策略
if is_simple_query(question):
    adaptive_level = "fast"
    adaptive_min_vector_hits = 2
    adaptive_prefer_graph = False
    adaptive_prefer_web = False

# 复杂查询 - 深度策略
elif is_complex_query(question):
    adaptive_level = "deep"
    adaptive_min_vector_hits = 5
    adaptive_prefer_graph = True
    adaptive_prefer_web = True

# 默认 - 平衡策略
else:
    adaptive_level = "balanced"
    adaptive_min_vector_hits = 3
    adaptive_prefer_graph = False
    adaptive_prefer_web = False
```

**负载感知降级**:

```python
system_load = get_system_load()
if system_load > 0.8:
    # 系统负载高，降级到更快的策略
    if adaptive_level == "deep":
        adaptive_level = "balanced"
    elif adaptive_level == "balanced":
        adaptive_level = "fast"
```

---

### 3. Vector Node (向量检索节点)

**职责**: 执行混合检索（向量 + BM25 + 重排序）

**检索流程**:

```python
def vector_node(state: GraphState) -> GraphState:
    question = state["question"]
    
    # 1. 查询重写和扩展
    queries = rewrite_query(question)
    
    # 2. 并行执行向量和 BM25 检索
    vector_results, bm25_results = await asyncio.gather(
        vector_store.search(queries),
        bm25_retriever.search(queries)
    )
    
    # 3. 倒数排名融合
    fused_results = rrf_fusion(vector_results, bm25_results)
    
    # 4. 重排序
    if ENABLE_RERANKER:
        reranked_results = reranker.rerank(question, fused_results)
    else:
        reranked_results = fused_results
    
    # 5. 返回结果
    return {
        "vector_result": {
            "documents": reranked_results,
            "count": len(reranked_results),
            "sources": extract_sources(reranked_results)
        }
    }
```

---

### 4. Graph Node (图检索节点)

**职责**: 查询 Neo4j 知识图谱

**查询类型**:

**实体属性查询**:
```cypher
MATCH (e:Entity {name: $entity_name})
RETURN e
```

**关系查询**:
```cypher
MATCH (e1:Entity {name: $entity1})-[r]-(e2:Entity {name: $entity2})
RETURN type(r), properties(r)
```

**多跳查询**:
```cypher
MATCH path = (e1:Entity {name: $entity1})-[*1..3]-(e2:Entity {name: $entity2})
RETURN path
LIMIT 10
```

---

### 5. Synthesis Node (合成节点)

**职责**: 综合所有信息，生成最终答案

**合成流程**:

```python
def synthesis_node(state: GraphState) -> GraphState:
    question = state["question"]
    vector_result = state.get("vector_result", {})
    graph_result = state.get("graph_result", {})
    web_result = state.get("web_result", {})
    
    # 1. 整合上下文
    context = merge_context(vector_result, graph_result, web_result)
    
    # 2. 检查一致性
    consistency = check_consistency(context)
    
    # 3. 生成答案
    answer = llm.generate(
        prompt=synthesis_prompt,
        question=question,
        context=context
    )
    
    # 4. 提取引用
    citations = extract_citations(answer, context)
    
    # 5. 安全检查
    safety = check_answer_safety(answer)
    
    # 6. 返回结果
    return {
        "answer": answer,
        "grounding": {
            "citations": citations,
            "consistency": consistency
        },
        "answer_safety": safety
    }
```

---

## 状态管理

### GraphState 完整定义

```python
class GraphState(TypedDict, total=False):
    # 输入
    question: str                       # 用户问题
    session_id: str                     # 会话 ID
    memory_context: str                 # 记忆上下文
    use_web_fallback: bool              # 是否启用网络回退
    use_reasoning: bool                 # 是否使用推理模型
    allowed_sources: list[str]          # 允许的来源
    agent_class_hint: str | None        # 智能体类别提示
    retrieval_strategy: str | None      # 检索策略
    force_language: str                 # 强制语言
    
    # 路由决策
    route: str                          # vector | graph | hybrid
    skill: str                          # 技能类型
    agent_class: str                    # 智能体类别
    reason: str                         # 决策原因
    
    # 自适应参数
    adaptive_level: str                 # fast | balanced | deep
    adaptive_min_vector_hits: int       # 最小向量命中数
    adaptive_prefer_graph: bool         # 偏好图检索
    adaptive_prefer_web: bool           # 偏好网络搜索
    
    # 检索结果
    vector_result: dict[str, Any]       # 向量检索结果
    graph_result: dict[str, Any]        # 图检索结果
    web_result: dict[str, Any]          # 网络搜索结果
    
    # 输出
    answer: str                         # 最终答案
    grounding: dict[str, Any]           # 引用和一致性
    answer_safety: dict[str, Any]       # 安全检查结果
    
    # 控制
    next_step: str                      # 下一步操作
    detected_language: str              # 检测到的语言
```

---

## 路由逻辑

### 条件路由函数

```python
def route_by_next_step(state: GraphState) -> str:
    """通用路由函数，根据 next_step 字段决定下一步"""
    return state.get("next_step", "synthesis")
```

### 完整路由表

| 当前节点 | 条件 | 下一节点 |
|---------|------|---------|
| entry_decider | 闲聊 | synthesis |
| entry_decider | route=vector | vector |
| entry_decider | route=graph | graph |
| entry_decider | route=hybrid | vector |
| vector_decider | route=hybrid | graph |
| vector_decider | 证据不足 + web_fallback | web |
| vector_decider | 其他 | synthesis |
| graph_decider | 证据不足 + web_fallback | web |
| graph_decider | 其他 | synthesis |
| web | 总是 | synthesis |

---

## 执行追踪

### 智能体追踪装饰器

```python
@track_agent_execution(agent_name="vector")
def vector_node(state: GraphState, execution_id: str = None):
    # 执行逻辑
    pass
```

### 追踪信息

```python
{
    "execution_id": "exec_123",
    "agent": "vector",
    "status": "completed",
    "start_time": "2026-06-19T10:00:00",
    "end_time": "2026-06-19T10:00:02",
    "duration_ms": 2000,
    "input": {"question": "..."},
    "output": {"documents": [...]},
    "metadata": {
        "docs_count": 5,
        "reranked": true
    }
}
```

---

## 性能优化

### 1. 并行执行

```python
# Hybrid 模式：向量和图并行执行
if route == "hybrid":
    vector_result, graph_result = await asyncio.gather(
        execute_vector_node(state),
        execute_graph_node(state)
    )
```

### 2. 超时控制

```python
@timeout(seconds=5)
def vector_node(state: GraphState):
    # 如果超过 5 秒，抛出 TimeoutError
    pass
```

### 3. 缓存

```python
@cached(ttl=300)
def vector_search(query: str):
    # 结果缓存 5 分钟
    pass
```

---

## 最佳实践

1. **保持节点纯函数**: 避免副作用
2. **使用类型提示**: 确保类型安全
3. **添加日志**: 记录关键决策点
4. **错误处理**: 每个节点都应有错误处理
5. **性能监控**: 追踪每个节点的执行时间
6. **文档化**: 清晰说明每个节点的职责

---

## 下一步

了解多智能体系统后，建议继续阅读：

1. **[检索系统](retrieval-system.md)** - 详解混合检索算法
2. **[数据存储](data-storage.md)** - ChromaDB、Neo4j 使用
3. **[API 开发](../development/api-development.md)** - 如何调用工作流

---

**更新日期**: 2026-06-19  
**文档版本**: 1.0
