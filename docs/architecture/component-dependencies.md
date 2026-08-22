# QueryMind 组件依赖关系图

## 概览

QueryMind RAG 系统采用**分层架构**，从 HTTP 入口到最终答案生成，共分为 5 层：

```
HTTP 层 → Pipeline 层 → Orchestration 层 → Agent Services 层 → Implementation 层
```

---

## 完整依赖关系图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           HTTP API 层                                    │
│  app/api/routes/compatibility/enhanced_query.py                         │
│  app/api/routes/public/sessions.py                                      │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Pipeline 层 (公共接口)                           │
│  RAGPipeline (app/pipeline/rag_pipeline.py)                             │
│  - execute()                                                             │
│  - execute_stream()                                                      │
│  - 负责请求转换和结果规范化                                              │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Orchestration 层 (编排核心)                         │
│  OrchestrationEngine (app/orchestration/engine.py)                      │
│  - 顺序执行 6 个阶段                                                     │
│  - 管理超时和预算控制                                                    │
│  - 发布执行事件                                                          │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     CoreCapabilities (能力注册)                          │
│  app/orchestration/capabilities.py                                      │
│  - 组装所有 Agent Services                                               │
│  - 提供 OrchestrationServices 实例                                       │
└──────────────────┬──────────────────────────────────────────────────────┘
                   │
                   ├─────────────────┬─────────────────┬──────────────────┐
                   ▼                 ▼                 ▼                  ▼
┌──────────────────────┐  ┌──────────────────┐  ┌─────────────────┐  ┌──────────────────┐
│ RouterAgentService   │  │ PlannerAgent     │  │ RAGAgentService │  │ ToolAgentService │
│ (路由选择)           │  │ Service          │  │ (证据检索)      │  │ (工具执行)       │
│                      │  │ (任务分解)       │  │                 │  │                  │
└──────────────────────┘  └──────────────────┘  └─────────────────┘  └──────────────────┘
         │                         │                      │                     │
         │                         │                      │                     │
         ▼                         ▼                      ▼                     ▼
┌──────────────────────┐  ┌──────────────────┐  ┌─────────────────┐  ┌──────────────────┐
│ routing.py           │  │ planning.py      │  │ retrieval.py    │  │ LangGraph tools  │
│ (路由逻辑)           │  │ (规划逻辑)       │  │ (检索逻辑)      │  │                  │
└──────────────────────┘  └──────────────────┘  └─────────────────┘  └──────────────────┘
                                                         │
                                                         ▼
                                            ┌─────────────────────────┐
                                            │ HybridRetriever         │
                                            │ (混合检索)              │
                                            │ - Vector (ChromaDB)     │
                                            │ - BM25                  │
                                            │ - Reranker              │
                                            └─────────────────────────┘
                   
                   ├─────────────────┬──────────────────┐
                   ▼                 ▼                  ▼
┌────────────────────────┐  ┌──────────────────┐  ┌─────────────────────┐
│ SynthesizerAgent       │  │ FinalizationSvc  │  │ Domain Contracts    │
│ Service                │  │ (验证和质量)     │  │ (共享类型)          │
│ (答案合成)             │  │                  │  │                     │
└────────────────────────┘  └──────────────────┘  └─────────────────────┘
         │                           │                      │
         ▼                           ▼                      ▼
┌────────────────────────┐  ┌──────────────────┐  ┌─────────────────────┐
│ generation.py          │  │ finalization.py  │  │ RouteDecision       │
│ (生成逻辑)             │  │                  │  │ EvidenceBundle      │
│                        │  │                  │  │ FinalAnswer         │
└────────────────────────┘  └──────────────────┘  └─────────────────────┘
```

---

## 执行流程详解

### 阶段 1: Route (路由) - **必须执行**

```
OrchestrationEngine
    ↓
RouterAgentService.route()
    ↓
app/agents/router/routing.py
    ↓
LLM 调用 (OpenAI GPT-4)
    ↓
返回: RouteDecision
    - intent: "knowledge_retrieval" | "web_search" | "tool_call" | "hybrid"
    - confidence: 0.0 - 1.0
    - requires_plan: bool
    - allowed_capabilities: frozenset["rag", "web", "tool"]
```

**依赖:**
- 输入: `OrchestrationRequest`
- 输出: `RouteDecision`
- 配置: `config/router_calibration.json`

---

### 阶段 2: Plan (规划) - **条件执行**

**触发条件:** `route.requires_plan == True`

```
OrchestrationEngine
    ↓ (如果 policy.should_plan(route))
PlannerAgentService.plan()
    ↓
app/agents/planner/planning.py
    ↓
LLM 调用 (GPT-4)
    ↓
返回: TaskPlan
    - tasks: tuple[PlannedTask, ...]
    - 每个任务包含依赖关系 (depends_on)
```

**依赖:**
- 输入: `OrchestrationRequest`, `RouteDecision`
- 输出: `TaskPlan` (可选)
- 仅在复杂查询时激活

---

### 阶段 3: Retrieval (检索) - **必须执行**

```
OrchestrationEngine
    ↓
RAGAgentService.retrieve()
    ↓
app/agents/rag/retrieval.py
    ↓
┌─────────────────────────────────────┐
│ HybridRetriever (并发执行)          │
│  ├─ Vector Search (ChromaDB)        │
│  ├─ BM25 Search (Rank-BM25)         │
│  ├─ Knowledge Graph (Neo4j) [可选] │
│  └─ Web Search (Tavily) [可选]     │
└─────────────────────────────────────┘
    ↓
Reciprocal Rank Fusion (RRF)
    ↓
Reranking (Reranking (BAAI/bge-reranker-v2-m3))
    ↓
Quality Scoring (Claude Haiku 批量打分) [可选]
    ↓
返回: EvidenceBundle
    - items: tuple[EvidenceItem, ...]
    - citations: tuple[str, ...]
```

**依赖:**
- 输入: `OrchestrationRequest`, `RouteDecision`, `TaskPlan | None`
- 输出: `EvidenceBundle`
- 外部依赖:
  - ChromaDB (向量存储)
  - Neo4j (知识图谱, 可选)
  - Tavily API (网络搜索, 可选)

---

### 阶段 4: Tool Execution (工具执行) - **条件执行**

**触发条件:** `route.intent == "tool_call"` 且 `plan.requires_tools == True`

```
OrchestrationEngine
    ↓ (如果 policy.should_run_tools(route, plan))
ToolAgentService.run()
    ↓
LangGraph ReAct Agent
    ↓
执行授权工具 (搜索、计算器等)
    ↓
返回: tuple[ToolResult, ...]
```

**依赖:**
- 输入: `OrchestrationRequest`, `RouteDecision`, `TaskPlan`, `EvidenceBundle`
- 输出: `tuple[ToolResult, ...]`
- 仅在 `react` 路由时激活

---

### 阶段 5: Synthesis (合成) - **必须执行**

```
OrchestrationEngine
    ↓
SynthesizerAgentService.synthesize()
    ↓
app/agents/synthesizer/generation.py
    ↓
LLM 调用 (GPT-4) + Citation-First Prompt
    ↓
返回: FinalAnswer
    - answer: str (带内联引用 [doc_id:page])
    - citations: tuple[str, ...]
    - evidence: EvidenceBundle
```

**依赖:**
- 输入: `OrchestrationRequest`, `RouteDecision`, `TaskPlan | None`, `EvidenceBundle`, `tuple[ToolResult, ...]`
- 输出: `FinalAnswer`
- 核心原则: **Citation-First** (引用优先)

---

### 阶段 6: Finalization (终结验证) - **条件执行**

**触发条件:** Profile 设置 (如 `strict_quality`)

```
OrchestrationEngine
    ↓ (如果 finalizer 已注入)
FinalizationService.finalize()
    ↓
app/orchestration/finalization.py
    ↓
执行验证层:
    ├─ Citation Completeness (引用完整性)
    ├─ Hallucination Detection (幻觉检测)
    ├─ NLI Check (自然语言推理)
    ├─ Safety Filter (安全过滤)
    └─ Quality Scoring (质量评分)
    ↓
返回: FinalAnswer (已验证)
    - validation: ValidationStatus
    - quality_report: OrchestratedQualityReport
```

**依赖:**
- 输入: `OrchestrationRequest`, `EvidenceBundle`, `FinalAnswer`, `ExecutionPolicy`
- 输出: `FinalAnswer` (增强验证字段)
- 在 `standard` profile 中**禁用**，在 `strict_quality` 中**启用**

---

## 数据流 (Domain Contracts)

所有组件间通信使用 **不可变、类型安全** 的契约 (Pydantic Models):

| 契约类型 | 文件位置 | 用途 |
|---------|---------|------|
| `RouteDecision` | `app/domain/contracts.py:31` | 路由决策结果 |
| `TaskPlan` | `app/domain/contracts.py:78` | 任务分解计划 |
| `EvidenceBundle` | `app/domain/contracts.py:139` | 检索到的证据 |
| `ToolResult` | `app/domain/contracts.py:160` | 工具执行结果 |
| `FinalAnswer` | `app/domain/contracts.py:171` | 最终答案 |
| `ValidationStatus` | `app/domain/contracts.py:206` | 验证状态 |

**关键特性:**
- 所有契约继承自 `ImmutableContract` (frozen=True)
- 强制字段验证 (Pydantic validators)
- 拒绝额外字段 (extra="forbid")

---

## 配置依赖

| 配置文件 | 消费者 | 用途 |
|---------|--------|------|
| `config/router_calibration.json` | RouterAgentService | Few-shot 样例、置信度阈值 |
| `config/retrieval_config.json` | RAGAgentService | Top-K、相似度阈值 |
| `config/fact_verification.json` | FinalizationService | NLI 阈值、幻觉模式 |
| `.env` | CoreCapabilities | API Keys、数据库连接 |
| `app/agents/shared/config.py` | 所有 Services | 组件特定常量 (正在简化中) |

---

## 外部依赖

```
┌─────────────────────────────────────────────────────────────────┐
│                      外部服务依赖图                              │
└─────────────────────────────────────────────────────────────────┘

RAGAgentService ──────┬──→ ChromaDB (向量存储)
                      ├──→ Neo4j (知识图谱, 可选)
                      └──→ Tavily API (网络搜索, 可选)

RouterAgentService ───┬──→ OpenAI GPT-4 API
PlannerAgentService ──┤
SynthesizerAgentService ─┘

FinalizationService ──→ Anthropic Claude Haiku API (批量评分)

ToolAgentService ─────→ LangGraph + 工具注册表
```

---

## Profile 影响的执行路径

### Standard Profile (标准模式)
```
Route → Retrieval → Synthesis
```
- **跳过:** Plan, Tool, Finalization
- **适用:** 90% 的日常查询

### Strict Quality Profile (严格质量模式)
```
Route → Retrieval → Synthesis → Finalization
```
- **启用:** 所有验证层
- **适用:** 关键业务查询

### Advanced Profile (高级模式)
```
Route → Plan → Retrieval (多源) → Tool → Synthesis → Finalization
```
- **启用:** 多跳推理、网络搜索
- **适用:** 复杂研究任务

---

## 关键设计原则

### 1. 单向依赖流
```
HTTP → Pipeline → Orchestration → Services → Implementation
```
- 上层依赖下层，下层**不知道**上层存在
- 通过 `OrchestrationServices` 实现依赖注入

### 2. 契约驱动
- 所有组件通信通过 `app/domain/contracts.py` 中的不可变类型
- 强制编译时类型检查

### 3. 服务适配器模式
- `*Service` 类 (`service.py`) 是**适配器层**
- 实际逻辑在 `routing.py`, `generation.py` 等实现模块
- 适配器提供统一接口给编排层

### 4. 可选阶段
- 仅 Route, Retrieval, Synthesis 是必须的
- Plan, Tool, Finalization 根据 Profile 和 Route 条件执行

---

## 性能监控注入点

```
OrchestrationEngine
    ├─ _monitor.measure_async("orchestration_route")
    ├─ _monitor.measure_async("orchestration_plan")
    ├─ _monitor.measure_async("orchestration_retrieval")
    ├─ _monitor.measure_async("orchestration_synthesis")
    └─ _monitor.measure_async("orchestration_finalization")
```

监控服务 (`app/services/performance/monitor.py`) 通过依赖注入在引擎初始化时注入。

---

## 总结

**QueryMind 依赖关系的核心特征:**

1. **分层清晰**: 5 层架构，职责分离
2. **类型安全**: Pydantic 契约确保编译时检查
3. **灵活编排**: Profile 控制执行路径
4. **适配器隔离**: 服务层解耦接口和实现
5. **并发检索**: 多源检索并发执行，RRF 融合
6. **条件执行**: 仅在需要时激活 Plan/Tool/Finalization

**依赖方向:**
```
┌──────────────────────────────────────────────────┐
│ 所有依赖单向向下流动，无循环依赖                 │
│                                                  │
│ HTTP API → Pipeline → Engine → Services → Logic │
│                        ↓                         │
│                   Contracts (共享类型)           │
└──────────────────────────────────────────────────┘
```
