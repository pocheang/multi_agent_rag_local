# QueryMind 智能体合并与职责规范实施计划

> **状态：** 待实施
> **执行原则：** 合并重复实现与重复编排；保留所有现有业务能力、HTTP 契约、权限边界和降级行为。不得重新实现检索、图谱、网页研究、ReAct、引用、安全或会话能力。

**目标：** 将当前普通查询、增强质量查询、Advanced RAG 三套并存流程收敛为一个可配置的执行管线。每项能力在一次请求中仅有一个实际执行者，使用 Profile 表达现有差异，降低重复 LLM 自审和维护成本。

**架构：** 新增轻量 `RAGPipeline` 作为唯一编排入口，现有 Router、Vector RAG、Graph RAG、Web、ReAct、Synthesis、Validator 等实现先通过适配器接入。`standard`、`strict_quality`、`advanced` Profile 控制已存在的查询拆分、Self-RAG、质量验证和推理开关。旧工作流和 API 在迁移期只负责请求适配和兼容，稳定后再删除无调用的包装层。

**技术栈：** Python 3.11、FastAPI、LangGraph、LangChain、现有 Chroma/Neo4j、pytest、ruff、现有执行追踪与质量门禁。

## 全局约束

- 所有 Python 命令必须使用 `conda run -n rag-local` 或已激活的 `rag-local` 环境。
- 不新增、修改、移动或删除 tests/ 下的任何文件，也不修改 CI 或工作流配置；现有测试和质量门禁仅作为只读回归验证运行。
- 不改变 `/query`、`/api/v1/enhanced/query`、`/api/advanced-rag/query` 的 URL、认证、权限、配额、SSE 和已公开的响应字段。
- 不重新建知识库、不迁移 Chroma、Neo4j 或 PostgreSQL 数据，也不改变来源隔离逻辑。
- 不删除功能：查询拆分、Self-RAG、PDF 图谱增强、网页研究、ReAct、语言控制、引用落地、NLI、事实核验和安全净化必须保留为可配置能力。
- `QualityOrchestrator` 是纯计算组件，不将它视为需要消除的 LLM 智能体。
- 默认路径不得无条件进行多轮 LLM 自审；低置信度时仍可启用一次深度复核与至多一次重生成。
- 旧实现只有在本地/测试环境对比、现有回归验证和直接切换后的回滚观察完成后才能删除；不得用 `git reset` 或覆盖用户已有改动。
- 每个任务完成后运行对应的聚焦测试；仅在最终阶段运行完整测试和检索质量门禁。

---

## 目标职责边界

| 规范组件 | 唯一职责 | 迁入/保留能力 | 不负责 |
|---|---|---|---|
| `RoutingService` | 意图识别与初始路线选择 | 规则/LLM 分类、置信度校准、低置信度回退 | 查询拆分、检索 |
| `QueryDecompositionPolicy` | 复杂问题拆分 | `QueryDecomposer` | 自行实现路由 |
| `VectorRetrievalService` | 唯一向量/混合检索 | 混合检索、重排、动态参数、来源过滤、扩展、可选 Self-RAG | 回答生成 |
| `GraphRetrievalService` | 唯一图谱检索 | 基础图查询、PDF 增强、空结果回退 | 自行维护向量回退实现 |
| `WebResearchService` | 受配额保护的网页补充 | 现有 Web Research | 本地优先路由决策 |
| `ReActService` | 多跳规划与工具调用 | 现有 ReAct | 单跳问答的常规路径 |
| `AnswerService` | 基于证据生成一次答案 | 语言、引用优先、生成降级 | 多轮默认自审 |
| `ValidationService` | 风险分级验证与重生成决策 | 规则、引用、句子落地、安全、NLI、事实核验、深度 LLM 校验 | 第二套生成实现 |
| `QualityReportService` | 汇总质量和执行统计 | 现有 Quality Orchestrator | 调用模型 |
| `ConversationContextService` | 多轮上下文解析与更新 | 现有 Context Tracker | 路由和检索 |

## Profile 规范

| Profile | 对应入口 | 保留行为 | token 规则 |
|---|---|---|---|
| `standard` | `/query` | 当前本地优先检索、可选 Web、ReAct、会话、语言与引用 | 不执行无条件 LLM 自审；确定性校验始终保留 |
| `strict_quality` | `/api/v1/enhanced/query` | 路由复核、检索质量、答案验证、质量报告、上下文 | 仅风险触发 NLI/深度复核；至多一次重生成 |
| `advanced` | `/api/advanced-rag/query` | 显式启用的查询拆分、Self-RAG、图谱/网页/ReAct | 拆分和 Self-RAG 只能由请求参数或配置显式开启 |

---

## 文件地图

### 新建文件

- `app/pipeline/contracts.py`：统一 `PipelineRequest`、`PipelineResult`、检索与验证结果契约。
- `app/pipeline/profiles.py`：三个 Profile 及能力开关的唯一配置点。
- `app/pipeline/rag_pipeline.py`：唯一编排入口；只调用现有服务适配器。
- `app/pipeline/adapters.py`：将现有 agent 函数适配为规范组件，迁移期不复制业务逻辑。

### 主要修改文件

- `app/agents/router_agent.py`、`app/agents/enhanced_router_agent.py`
- `app/agents/vector_rag_agent.py`、`app/agents/enhanced_vector_rag_agent.py`、`app/agents/vector_rag_agent_unified.py`
- `app/agents/graph_rag_agent.py`、`app/agents/graph_rag_agent_enhanced.py`
- `app/agents/synthesis_agent.py`、`app/agents/answer_validator_agent.py`、`app/agents/fact_verification.py`
- `app/agents/enhanced_rag_workflow.py`、`app/workflow/advanced_rag_workflow.py`
- `app/graph/workflow.py`、`app/graph/nodes/adaptive_planner_node.py`
- `app/api/routes/query.py`、`app/api/routes/enhanced_query.py`、`app/api/routes/advanced_rag.py`
- 相关单元、集成、SSE 与 API 契约测试。

### 迁移后删除候选（仅阶段 7）

- `EnhancedRouterAgent` 的独立路由实现（可保留短期弃用包装器）。
- 旧/增强向量检索中的重复编排与返回格式化代码。
- `EnhancedRAGWorkflow`、`AdvancedRAGWorkflow` 中已被 `RAGPipeline` 替代的编排逻辑。
- 合成模块中被 `ValidationService` 取代的默认多轮自审代码。

---

## 任务 1：固化基线与兼容契约

**文件：** 不新增或修改测试文件；仅使用现有 API、检索与质量测试进行回归验证。

- [ ] 使用现有 API、检索与质量测试记录响应字段、引用、语言、来源范围、Graph 空结果回退、Web 配额、超时和降级的基线。
- [ ] 复用现有 mock 与夹具运行回归验证，不修改测试代码。
- [ ] 在执行追踪中记录 `profile`、模型调用次数、输入/输出 token（如 provider 提供）、验证触发原因、重生成次数。
- [ ] 对固定评估集分别跑旧 `standard`、`strict_quality`、`advanced` 路径，记录成功率、P50/P95、Recall@K、Precision@5、引用完整率及每请求 token 基线。

**验收：** 现有回归测试在不访问外部模型的情况下通过；每条旧链路均有可比较基线。

**验证：**

```powershell
conda run -n rag-local pytest tests/agents/test_synthesis_citation.py tests/agents/test_route_validator.py -q
conda run -n rag-local python scripts/ci_quality_gate.py --dataset data/eval/retrieval_eval.jsonl --min-recall 0.35 --report-md audit_output/agent-consolidation-baseline.md
```

## 任务 2：建立统一契约和 Profile，不切换流量

**文件：** 新建 `app/pipeline/contracts.py`、`app/pipeline/profiles.py`。

- [ ] 定义不可变请求契约，包含问题、会话、用户、来源范围、检索策略、推理开关、截止时间和 Profile。
- [ ] 定义统一结果契约，至少包含 `answer`、`citations`、`route`、`contexts`、`quality_report`、`execution_metadata`、`degradation_events`。
- [ ] 将现有三个入口的默认值映射到三个 Profile；Advanced 的拆分/Self-RAG 保持请求级开关，而不是默认开启。
- [ ] 定义能力预算：确定性检查不受限；LLM 深度验证和重生成各最多一次；standard 禁止默认循环自审。
- [ ] Profile 的默认值由配置审查和现有回归结果确认；任何变更均要求更新基线和发布说明。

**验收：** Profile 能完整表达当前三条入口差异；本任务不改变生产路由。

**验证：**

```powershell
conda run -n rag-local pytest -q
conda run -n rag-local ruff check app/pipeline
```

## 任务 3：合并路由与查询拆分职责

**文件：** 修改 `router_agent.py`、`enhanced_router_agent.py`、`adaptive_planner_node.py`、`advanced_rag_workflow.py`；扩展 `app/pipeline/adapters.py`。

- [ ] 将 `router_agent.decide_route` 封装为唯一 `RoutingService` 实现，保留现有 LLM 意图识别、置信度校准、reason/skill/agent_class 字段和低置信度回退。
- [ ] 将 `EnhancedRouterAgent` 改为仅处理 `QueryDecompositionPolicy` 后调用 `RoutingService`；不再拥有第二份路由规则或第二次默认路由调用。
- [ ] 将 `adaptive_planner` 限制为 Top-K、检索策略、Web/Graph 降级等运行参数；除明确的失败回退外，不覆盖 Router 的语义路线。
- [ ] 子问题均通过同一个 `RoutingService`，保留原有顺序与合成结果格式。
- [ ] 添加弃用警告和导入守卫，禁止新代码直接依赖增强路由器。

**验收：** 相同输入下旧/新路由的 `route`、`skill`、`agent_class`、来源过滤结果一致；低置信度仍可复核。

**验证：**

```powershell
conda run -n rag-local pytest tests/agents/test_router_accuracy.py tests/agents/test_router_enhanced.py tests/agents/test_route_validator.py -q
```

## 任务 4：合并向量与图谱检索实现

**文件：** 修改三份 Vector RAG 文件、两份 Graph RAG 文件、`safe_wrappers.py`、图/向量节点和适配器。

- [ ] 以 `UnifiedVectorRAGAgent` 的能力为基础，补齐旧 `run_vector_rag` 所有可见字段、异常与降级语义，使其成为 `VectorRetrievalService` 唯一实现。
- [ ] 将 Enhanced Vector 的 Self-RAG 迁成可选后置评估策略；返回格式统一，不复制检索与引用格式化逻辑。
- [ ] 旧 `run_vector_rag` 保留为薄转发函数；所有新调用只能进入 `VectorRetrievalService`。
- [ ] 将基础 Graph RAG 与 PDF 增强逻辑收进 `GraphRetrievalService`：根据现有 `GRAPH_RAG_ENHANCED`、是否传入文档及文档质量选择策略。
- [ ] 图谱空结果和故障回退必须经统一的 Vector 服务，保留 `fallback_used`、原因、来源权限与诊断字段。
- [ ] 统一所有检索结果的 `context`、`citations`、`retrieved_count`、`effective_hit_count`、`diagnostics`；兼容字段保留一个发布周期。

**验收：** 检索指标和来源隔离不低于基线；运行时没有并行的旧/增强/统一向量检索调用。

**验证：**

```powershell
conda run -n rag-local pytest tests/unit/test_enhanced_vector_rag_agent.py tests/test_retrieval_strategy.py tests/test_graph_rag_agent.py tests/test_graph_rag_agent_enhanced.py -q
conda run -n rag-local python scripts/ci_quality_gate.py --dataset data/eval/retrieval_eval.jsonl --min-recall 0.35 --report-md audit_output/agent-consolidation-retrieval.md
```

## 任务 5：统一回答生成与质量闸门

**文件：** 修改 `synthesis_agent.py`、`answer_validator_agent.py`、`fact_verification.py`、`citation_grounding.py`、`quality_orchestrator_agent.py`、`enhanced_rag_workflow.py`。

- [ ] 将 `AnswerService` 限定为一次生成：保留语言探测、引用优先提示、模型选择和生成失败降级。
- [ ] 将检查顺序固定为：来源/权限确认 → 引用与规则 → 句子证据落地与安全净化 → NLI（中等风险） → 深度 LLM（低置信度） → 至多一次重生成。
- [ ] 把 `_refine_answer` 迁为 `strict_quality` 的可选策略；standard 默认关闭，所有 Profile 的自动迭代上限为一轮。
- [ ] 聚合 FactVerifier、AnswerValidator、citation grounding 的结果，确保同一事实/引用不被无意义地多次扫描。
- [ ] `QualityReportService` 继续仅融合分数，不发起 LLM 调用；保留现有质量等级与对用户的提示。

**验收：** standard 的模型调用数低于基线；strict_quality 的引用完整率、事实一致性和安全测试不低于基线；最多一次自动重生成。

**验证：**

```powershell
conda run -n rag-local pytest tests/agents/test_synthesis_citation.py tests/agents/test_answer_validator.py tests/agents/test_answer_validator_cascade.py tests/agents/test_fact_verification.py tests/agents/test_quality_orchestrator.py -q
```

## 任务 6：收敛三个 API 到唯一编排入口

**文件：** 新建 `rag_pipeline.py`；修改三份 API route、`graph/workflow.py`、`enhanced_rag_workflow.py`、`advanced_rag_workflow.py`、SSE 处理器。

- [ ] `RAGPipeline.execute(request, profile)` 成为唯一业务编排入口；节点与工作流只能调用其适配器，不能重新串联 Router、Retriever、Validator。
- [ ] `/query` 映射 `standard`，增强端点映射 `strict_quality`，Advanced 端点映射 `advanced`；保留各自认证、限流、请求模型和响应模型。
- [ ] SSE 使用相同 Pipeline 事件模型，事件名称和前端消费字段保持兼容。
- [ ] 执行追踪、质量报告、超时、降级事件只由统一管线写入；API 层只负责鉴权、请求转换和序列化。
- [ ] 在本地或测试环境运行新旧管线对比，比较 route、引用集合、质量等级、延迟和 token；不在生产请求中执行影子调用。

**验收：** 三端点兼容测试通过；单次请求追踪中不再出现重复路由或重复质量链；SSE 无前端破坏性变更。

**验证：**

```powershell
conda run -n rag-local pytest tests/test_advanced_rag_workflow.py tests/agents/test_enhanced_workflow.py tests/test_workflow_fixes.py tests/integration/test_multilingual_workflow.py -q
conda run -n rag-local pytest tests/api -q
```

## 任务 7：最终验证、清理和代码审查

**文件：** 删除已无生产 import 的遗留包装逻辑；修改运行时代码和文档，不修改 CI 或测试。

- [ ] 在本地/测试环境记录新旧管线的质量、时延、错误和 token 对比结果；验证通过后直接切换。
- [ ] 完成本地/测试环境对比和现有回归验证后直接切换；错误率、P95、Recall、引用完整率、来源隔离或 token 预算回退时，立即按 API/Profile 切回旧管线。
- [ ] 直接切换后的回滚观察完成后，删除不再被引用的增强路由包装、旧/增强向量重复编排、旧工作流重复编排和默认多轮自审代码。
- [ ] 通过代码审查和现有运行时追踪确认新生产代码不再导入退役模块。
- [ ] 更新 `AGENTS.md` 和开发文档，列出规范组件和 Profile，不再以“11 个必经智能体”描述运行时。

**验收：** 只有一个生产编排入口；遗留模块没有生产 import；运行时追踪与代码审查能发现重复实现回归。

**验证：**

```powershell
conda run -n rag-local pytest tests/ -q
conda run -n rag-local ruff check app tests
conda run -n rag-local python scripts/ci_quality_gate.py --dataset data/eval/retrieval_eval.jsonl --min-recall 0.35 --report-md audit_output/agent-consolidation-final.md
git diff --check
git status --short
```
---

## 执行顺序与回滚

严格按任务编号顺序执行：任务 1 的基线与契约未通过，不开始任务 2；任务 2 至 5 每完成一项，必须通过该项列出的聚焦测试后才能进入下一项；任务 6 只在前述服务均已收敛后开始；任务 7 只在本地或测试环境的新旧结果对比和现有回归验证通过后执行。计划不以周数或日期作为实施前提。

回滚按最小范围执行：先切换 API 的 Profile/管线开关，再回滚单个路由、检索或验证组件；不回滚数据、不修改知识库、不破坏公开接口。