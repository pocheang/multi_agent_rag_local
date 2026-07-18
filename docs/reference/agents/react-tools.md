# ReactAgent 工具使用完整指南

## 📋 目录
1. [架构概览](#架构概览)
2. [工具执行流程](#工具执行流程)
3. [三个核心工具](#三个核心工具)
4. [结果合并机制](#结果合并机制)
5. [完整执行示例](#完整执行示例)
6. [关键代码解析](#关键代码解析)

---

## 🏗️ 架构概览

ReactAgent实现了**ReAct模式**（Reasoning + Acting），是一个真正的智能agent，能够：
- 🧠 **自主思考**：使用LLM分析当前状态并决定下一步行动
- 🛠️ **选择工具**：从3个工具中选择最合适的（vector_search/graph_query/web_search）
- 🔄 **迭代执行**：最多5轮Think-Act-Observe循环
- 📊 **上下文累积**：每轮结果合并到accumulated_context
- ✅ **自主终止**：认为信息充足时主动finish

### ReactAgent vs 普通工作流

| 特性 | ReactAgent（真实Agent） | 普通工作流 |
|------|------------------------|-----------|
| 决策方式 | LLM自主决策每一步 | 预定义执行顺序 |
| 工具选择 | 动态选择需要的工具 | 固定调用所有工具 |
| 迭代能力 | 根据结果调整策略 | 单次执行，无反馈 |
| 终止条件 | 自己判断何时停止 | 固定步骤完成 |
| 上下文管理 | 跨轮累积和融合 | 单次传递 |

---

## 🔄 工具执行流程

```
┌─────────────────────────────────────────────────────────────┐
│                    ReactAgent.run()                         │
│  初始化: history=[], accumulated_context={}, tool_results={}│
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ↓
        ┌───────────────────────────────┐
        │   Iteration Loop (max 5轮)   │
        └───────────────┬───────────────┘
                        │
        ┌───────────────▼────────────────┐
        │  1️⃣ THINK Phase (_think)      │
        │  ┌─────────────────────────┐  │
        │  │ LLM分析当前状态         │  │
        │  │ 输入：                  │  │
        │  │  - question            │  │
        │  │  - memory_context      │  │
        │  │  - history（之前轮次） │  │
        │  │ 输出 JSON:             │  │
        │  │  {                      │  │
        │  │    "thought": "分析...",│  │
        │  │    "action": "工具名",  │  │
        │  │    "action_input": "...",│ │
        │  │    "reasoning": "理由" │  │
        │  │  }                      │  │
        │  └─────────────────────────┘  │
        └───────────────┬────────────────┘
                        │
                        ↓
                 action == "finish"?
                   ├─Yes→ Break Loop
                   │
                   No
                   │
        ┌──────────▼─────────────────────┐
        │  2️⃣ ACT Phase (_act)           │
        │  ┌─────────────────────────┐  │
        │  │ 工具映射表:             │  │
        │  │ {                       │  │
        │  │   "vector_search":      │  │
        │  │      _tool_vector_search│  │
        │  │   "graph_query":        │  │
        │  │      _tool_graph_query  │  │
        │  │   "web_search":         │  │
        │  │      _tool_web_search   │  │
        │  │ }                       │  │
        │  │                         │  │
        │  │ 执行对应工具方法        │  │
        │  └─────────────────────────┘  │
        └───────────────┬────────────────┘
                        │
                        ↓
        ┌───────────────▼────────────────┐
        │  3️⃣ OBSERVE Phase              │
        │  ┌─────────────────────────┐  │
        │  │ 工具返回:               │  │
        │  │  - summary (简短摘要)   │  │
        │  │  - metadata (统计信息)  │  │
        │  │                         │  │
        │  │ 合并结果:               │  │
        │  │  - _merge_*_result()    │  │
        │  │  - accumulated_context  │  │
        │  │  - tool_results         │  │
        │  │                         │  │
        │  │ 记录到 history          │  │
        │  └─────────────────────────┘  │
        └───────────────┬────────────────┘
                        │
                        └─────► 返回 THINK Phase
                        
                        ↓ (循环结束)
                        
        ┌───────────────▼────────────────┐
        │  4️⃣ SYNTHESIS Phase            │
        │  _synthesize_final_answer()    │
        │  ┌─────────────────────────┐  │
        │  │ 输入所有accumulated_    │  │
        │  │ context:                │  │
        │  │  - vector_context       │  │
        │  │  - graph_context        │  │
        │  │  - web_context          │  │
        │  │                         │  │
        │  │ SynthesisAgent生成答案  │  │
        │  └─────────────────────────┘  │
        └───────────────┬────────────────┘
                        │
                        ↓
        ┌───────────────▼────────────────┐
        │  返回最终结果:                  │
        │  {                              │
        │    "answer": "...",             │
        │    "react_history": [...],      │
        │    "iterations_used": 3,        │
        │    "contexts": {...},           │
        │    "vector_result": {...},      │
        │    "graph_result": {...},       │
        │    "web_result": {...}          │
        │  }                              │
        └─────────────────────────────────┘
```

---

## 🛠️ 三个核心工具

### 1. Vector Search Tool

**代码位置**: `react_agent.py:352-383`

```python
def _tool_vector_search(
    self,
    query: str,
    allowed_sources: list[str] | None,
    retrieval_strategy: str | None,
) -> tuple[str, dict[str, Any]]:
    """复用VectorRAGAgent进行向量检索"""
    
    # 1. 调用vector_rag_agent
    result = run_vector_rag(
        question=query,
        allowed_sources=allowed_sources,
        retrieval_strategy=retrieval_strategy,
    )
    
    # 2. 合并结果到累积上下文
    self._merge_vector_result(result)
    self.accumulated_context["vector"] = self.tool_results["vector"]["context"]
    
    # 3. 返回摘要（给LLM看的观察结果）
    summary = (
        f"Found {result['retrieved_count']} vector hits, "
        f"with {result['effective_hit_count']} effective hits.\n"
        f"Top sources: {', '.join(sources[:3])}"
    )
    
    # 4. 返回元数据（统计信息）
    metadata = {
        "retrieved_count": result['retrieved_count'],
        "effective_count": result['effective_hit_count'],
        "citations_count": len(result['citations']),
    }
    
    return summary, metadata
```

**特点**：
- ✅ 复用已有的`VectorRAGAgent`
- 📚 支持混合检索（向量+BM25+重排序）
- 🎯 动态调整top_k（15-30）
- 📊 返回有效命中数作为质量指标

---

### 2. Graph Query Tool

**代码位置**: `react_agent.py:385-414`

```python
def _tool_graph_query(
    self,
    query: str,
    allowed_sources: list[str] | None,
    retrieval_strategy: str | None,
) -> tuple[str, dict[str, Any]]:
    """复用GraphRAGAgent查询知识图谱"""
    
    # 1. 调用graph_rag_agent
    result = run_graph_rag(query, allowed_sources=allowed_sources)
    
    # 2. 合并图谱结果
    self._merge_graph_result(result)
    self.accumulated_context["graph"] = self.tool_results["graph"]["context"]
    
    # 3. 提取实体和关系
    entities = result.get("entities", [])
    relationships = result.get("relationships", [])
    neighbors = result.get("neighbors", [])
    paths = result.get("paths", [])
    
    # 4. 返回摘要
    summary = (
        f"Found {len(entities)} entities and "
        f"{len(relationships)} graph relationships.\n"
        f"Entities: {', '.join(entity_names[:5])}"
    )
    
    metadata = {
        "entities_count": len(entities),
        "relationships_count": len(relationships),
    }
    
    return summary, metadata
```

**特点**：
- 🕸️ 查询Neo4j知识图谱
- 🔗 提取实体、关系、邻居、路径
- 📈 计算graph_signal_score
- ⚠️ 可选功能（Neo4j未配置时会优雅降级）

---

### 3. Web Search Tool

**代码位置**: `react_agent.py:416-437`

```python
def _tool_web_search(
    self,
    query: str,
    allowed_sources: list[str] | None,
    retrieval_strategy: str | None,
) -> tuple[str, dict[str, Any]]:
    """复用WebResearchAgent进行联网搜索"""
    
    # 1. 调用web_research_agent
    result = run_web_research(query)
    
    # 2. 合并网络搜索结果
    self._merge_web_result(result)
    self.accumulated_context["web"] = self.tool_results["web"]["context"]
    
    # 3. 提取来源
    citations = result.get("citations", [])
    sources = [c.get("source", "unknown") for c in citations[:3]]
    
    # 4. 返回摘要
    summary = (
        f"Found {len(citations)} web results.\n"
        f"Sources: {', '.join(sources)}"
    )
    
    metadata = {
        "citations_count": len(citations),
        "used": result.get("used", False),
    }
    
    return summary, metadata
```

**特点**：
- 🌐 搜索互联网（作为本地知识库补充）
- 🔍 使用DuckDuckGo或其他搜索引擎
- ⏱️ 有超时保护
- 🎯 仅在本地信息不足时使用

---

## 🔗 结果合并机制

### 累积上下文数据结构

```python
# 初始化（react_agent.py:29-52）
accumulated_context = {
    "vector": "",    # 向量检索的文本上下文
    "graph": "",     # 图谱查询的文本上下文
    "web": ""        # 网络搜索的文本上下文
}

tool_results = {
    "vector": {
        "context": "",
        "citations": [],           # 所有轮次的引用累积
        "retrieved_count": 0,      # 总检索数
        "effective_hit_count": 0,  # 高质量命中累积
    },
    "graph": {
        "context": "",
        "entities": [],            # 所有实体累积
        "neighbors": [],           # 所有邻居累积
        "paths": [],               # 所有路径累积
        "graph_signal_score": 0.0, # 最大信号分数
    },
    "web": {
        "context": "",
        "citations": [],           # 所有网络来源累积
        "used": False,             # 是否使用过
    },
}
```

### 合并策略

**代码位置**: `react_agent.py:133-172`

#### Vector结果合并
```python
def _merge_vector_result(self, result: dict[str, Any]) -> None:
    merged = self.tool_results["vector"]
    
    # 1. 上下文追加（用\n\n分隔）
    merged["context"] = self._append_context(
        merged.get("context", ""), 
        result.get("context", "")
    )
    
    # 2. 引用列表扩展（去重在后续处理）
    merged["citations"].extend(result.get("citations", []))
    
    # 3. 计数累加
    merged["retrieved_count"] += result.get("retrieved_count", 0)
    merged["effective_hit_count"] += result.get("effective_hit_count", 0)
    
    # 4. 诊断信息覆盖（保留最新）
    if "retrieval_diagnostics" in result:
        merged["retrieval_diagnostics"] = result["retrieval_diagnostics"]
```

#### Graph结果合并
```python
def _merge_graph_result(self, result: dict[str, Any]) -> None:
    merged = self.tool_results["graph"]
    
    # 1. 上下文追加
    merged["context"] = self._append_context(
        merged.get("context", ""), 
        result.get("context", "")
    )
    
    # 2. 实体、邻居、路径列表扩展
    merged["entities"].extend(result.get("entities", []))
    merged["neighbors"].extend(result.get("neighbors", []))
    merged["paths"].extend(result.get("paths", []))
    
    # 3. 信号分数取最大值（最强信号）
    merged["graph_signal_score"] = max(
        merged.get("graph_signal_score", 0.0),
        result.get("graph_signal_score", 0.0),
    )
    
    # 4. 错误信息覆盖
    if result.get("error"):
        merged["error"] = result["error"]
```

#### Web结果合并
```python
def _merge_web_result(self, result: dict[str, Any]) -> None:
    merged = self.tool_results["web"]
    
    # 1. 上下文追加
    merged["context"] = self._append_context(
        merged.get("context", ""), 
        result.get("context", "")
    )
    
    # 2. 引用列表扩展
    merged["citations"].extend(result.get("citations", []))
    
    # 3. 使用标记或运算（只要用过一次就是true）
    merged["used"] = merged.get("used", False) or result.get("used", False)
    
    # 4. 错误信息覆盖
    if result.get("error"):
        merged["error"] = result["error"]
```

### _append_context辅助函数

```python
@staticmethod
def _append_context(existing: str, new: str) -> str:
    """智能追加上下文（避免空行）"""
    existing_text = str(existing or "").strip()
    new_text = str(new or "").strip()
    
    if not existing_text:
        return new_text
    if not new_text:
        return existing_text
    
    # 用两个换行符分隔不同轮次的上下文
    return f"{existing_text}\n\n{new_text}"
```

---

## 📖 完整执行示例

### 场景：用户问"Transformer的自注意力机制是什么，它与传统RNN有什么区别？"

#### 第1轮：Vector Search

**Think阶段（LLM输出）:**
```json
{
  "thought": "用户问的是Transformer的概念和对比，需要先从本地文档检索基础信息",
  "action": "vector_search",
  "action_input": "Transformer自注意力机制原理",
  "reasoning": "先获取Transformer的基本定义和自注意力机制的原理"
}
```

**Act阶段（工具执行）:**
```python
# 调用 _tool_vector_search("Transformer自注意力机制原理", ...)
result = run_vector_rag(
    question="Transformer自注意力机制原理",
    allowed_sources=None,
    retrieval_strategy="hybrid",
)
# 返回15个相关文档片段

_merge_vector_result(result)
# accumulated_context["vector"] 现在包含15个文档片段
```

**Observe阶段（返回给LLM的摘要）:**
```
Found 15 vector hits, with 12 effective hits.
Top sources: attention_is_all_you_need.pdf, transformer_tutorial.pdf, nlp_architectures.pdf
```

---

#### 第2轮：Vector Search（查询对比信息）

**Think阶段:**
```json
{
  "thought": "已经获取了Transformer的基础信息，现在需要获取RNN的对比信息",
  "action": "vector_search",
  "action_input": "Transformer与RNN的区别 并行计算",
  "reasoning": "需要对比性信息来完整回答用户问题"
}
```

**Act阶段:**
```python
result = run_vector_rag(
    question="Transformer与RNN的区别 并行计算",
    ...
)
# 返回10个对比性文档

_merge_vector_result(result)
# accumulated_context["vector"] 现在累积了 15 + 10 = 25 个片段
# tool_results["vector"]["retrieved_count"] = 25
# tool_results["vector"]["effective_hit_count"] = 20
```

**Observe阶段:**
```
Found 10 vector hits, with 8 effective hits.
Top sources: rnn_vs_transformer.pdf, deep_learning_book.pdf
```

---

#### 第3轮：Finish决策

**Think阶段:**
```json
{
  "thought": "已经收集到足够的信息：Transformer的自注意力机制原理、与RNN的对比，可以生成完整答案",
  "action": "finish",
  "action_input": "",
  "reasoning": "信息充足，包含定义、原理、对比三个维度"
}
```

**Synthesis阶段（最终答案生成）:**
```python
final_answer = synthesize_answer(
    question="Transformer的自注意力机制是什么，它与传统RNN有什么区别？",
    skill_name="react_agent",
    memory_context="",
    vector_context=accumulated_context["vector"],  # 25个片段的完整上下文
    graph_context="",
    web_context="",
    use_reasoning=False,
)

# SynthesisAgent 使用所有累积的上下文生成带引用的答案
```

**最终返回:**
```json
{
  "answer": "Transformer的自注意力机制是一种并行计算注意力权重的方法...[doc1:p3]...与RNN相比，Transformer可以并行处理所有位置...[doc5:p7]",
  "detected_language": "zh",
  "react_history": [
    {
      "iteration": 1,
      "thought": {...},
      "observation": {"tool": "vector_search", "result": "Found 15 vector hits..."}
    },
    {
      "iteration": 2,
      "thought": {...},
      "observation": {"tool": "vector_search", "result": "Found 10 vector hits..."}
    },
    {
      "iteration": 3,
      "thought": {"action": "finish", ...},
      "observation": null
    }
  ],
  "iterations_used": 3,
  "contexts": {
    "vector": "...(25个片段的完整文本)...",
    "graph": "",
    "web": ""
  },
  "vector_result": {
    "context": "...",
    "citations": [...25个引用...],
    "retrieved_count": 25,
    "effective_hit_count": 20
  },
  "graph_result": {...},
  "web_result": {...}
}
```

---

## 🔍 关键代码解析

### 1. ReAct System Prompt

**位置**: `react_agent.py:80-108`

```python
REACT_SYSTEM_PROMPT = """你是一个使用ReAct模式（Reasoning + Acting）的智能助手。

你需要通过多轮思考和行动来回答问题：
1. Thought: 分析当前状态，决定下一步做什么
2. Action: 选择并执行一个工具
3. Observation: 观察工具返回的结果
4. 重复上述过程，直到收集到足够信息

可用工具：
- vector_search: 搜索本地文档库，适合查找具体信息、政策、技术文档
- graph_query: 查询知识图谱，适合查找实体关系、依赖关系、网络拓扑
- web_search: 搜索互联网，适合查找最新信息、新闻、公开资料
- finish: 当收集到足够信息时，生成最终答案

输出格式（JSON）：
{
    "thought": "当前思考...",
    "action": "vector_search|graph_query|web_search|finish",
    "action_input": "工具的输入查询",
    "reasoning": "为什么选择这个行动"
}

重要规则：
1. 每次只执行一个action
2. 基于observation结果调整策略
3. 避免重复相同的查询
4. 信息足够时及时finish
5. 最多进行5轮迭代
"""
```

**设计亮点**：
- ✅ 明确的角色定义（ReAct模式）
- 🛠️ 清晰的工具列表和适用场景
- 📝 结构化输出格式（JSON）
- 🎯 行为约束（避免重复、及时finish）

---

### 2. History格式化（上下文构建）

**位置**: `react_agent.py:445-460`

```python
def _format_history(self) -> str:
    """将执行历史格式化为提示文本"""
    if not self.history:
        return ""
    
    lines = []
    for step in self.history:
        lines.append(f"\n第{step.iteration}轮:")
        lines.append(f"  思考: {step.thought.thought}")
        lines.append(f"  行动: {step.thought.action}({step.thought.action_input})")
        lines.append(f"  推理: {step.thought.reasoning}")
        
        if step.observation:
            lines.append(f"  观察: {step.observation.result}")
    
    return "\n".join(lines)
```

**示例输出**：
```
第1轮:
  思考: 用户问的是Transformer的概念和对比
  行动: vector_search(Transformer自注意力机制原理)
  推理: 先获取Transformer的基本定义
  观察: Found 15 vector hits, with 12 effective hits.

第2轮:
  思考: 已经获取了Transformer的基础信息
  行动: vector_search(Transformer与RNN的区别)
  推理: 需要对比性信息
  观察: Found 10 vector hits, with 8 effective hits.
```

---

### 3. JSON提取（鲁棒性处理）

**位置**: `react_agent.py:492-513`

```python
@staticmethod
def _extract_json(text: str) -> dict[str, Any]:
    """从LLM响应中提取JSON（支持多种格式）"""
    text = str(text or "").strip()
    
    # 尝试1: 从markdown代码块提取
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试2: 直接查找JSON对象
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    logger.warning("Failed to extract JSON from response")
    return {}
```

**容错设计**：
- 📦 支持markdown代码块包裹的JSON
- 📄 支持纯文本中的JSON
- ⚠️ 解析失败返回空dict而非崩溃

---

## 🎯 关键特性总结

### 1. **真正的自主决策**
- ❌ 不是固定工作流（先vector再graph再web）
- ✅ 每轮LLM动态决定：用哪个工具、查什么、何时停止

### 2. **智能迭代策略**
- 第1轮可能用vector_search获取基础信息
- 第2轮可能用graph_query补充关系信息
- 第3轮可能再用vector_search深挖细节
- 第4轮认为信息足够，finish

### 3. **上下文累积**
- 每轮工具调用结果不会丢失
- `accumulated_context`和`tool_results`贯穿整个流程
- 最终答案生成使用所有累积的上下文

### 4. **工具复用**
- 不重新实现检索逻辑
- 直接复用`VectorRAGAgent`、`GraphRAGAgent`、`WebResearchAgent`
- 只负责编排和决策

### 5. **完整的执行追踪**
- `react_history`记录每轮的think-act-observe
- 可追溯整个推理过程
- 便于调试和质量评估

---

## 🚀 使用建议

### 何时使用ReactAgent？

✅ **适合场景**：
- 复杂的多步骤问题（需要分步骤收集信息）
- 对比类问题（需要分别检索不同实体）
- 信息来源不明确（需要尝试多个工具）
- 需要深度推理的场景

❌ **不适合场景**：
- 简单的单步查询（直接用VectorRAG更快）
- 已知最佳工具的场景（直接调用对应agent）
- 延迟敏感的场景（ReAct需要多次LLM调用）

### 性能考虑

| 指标 | 典型值 | 说明 |
|------|--------|------|
| 平均轮数 | 2-3轮 | 简单问题2轮，复杂问题3-4轮 |
| 总延迟 | 4-8秒 | 每轮LLM调用~1-2秒 + 工具执行时间 |
| Token消耗 | 5000-15000 tokens | 包括system prompt + history + 工具结果 |

---

## 📚 相关文件

- **ReactAgent实现**: `app/agents/react_agent.py`
- **VectorRAG工具**: `app/agents/vector_rag_agent.py`
- **GraphRAG工具**: `app/agents/graph_rag_agent.py`
- **WebResearch工具**: `app/agents/web_research_agent.py`
- **Synthesis答案生成**: `app/agents/synthesis_agent.py`
- **工作流集成**: `app/agents/enhanced_rag_workflow.py`

---

## 🔗 参考资料

- **ReAct论文**: [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- **LangChain ReAct文档**: https://python.langchain.com/docs/modules/agents/agent_types/react
- **项目架构文档**: `CLAUDE.md`

---

**文档版本**: v1.0  
**最后更新**: 2026-07-05  
**作者**: Kiro AI Assistant
