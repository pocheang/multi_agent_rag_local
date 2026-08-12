# 智能体、工作流、Pipeline 与 LangGraph 架构审查

- 审查时间：2026-08-11（登记目录按委托要求保留 `2026-08-10`）
- 范围：`app/agents`、`app/graph`、`app/workflow`、`app/pipeline`、`app/orchestration`、相关 `app/services` 与 `app/api`，以及配置、公共导入和兼容包装。
- 方法：只读 AST、`rg`、源代码调用链与路由静态检查；未运行测试，未执行 Git 操作，未修改生产代码。
- 约束：已完整阅读根目录 `AGENTS.md`。其要求的生产边界为 API → `RAGPipeline` → `OrchestrationEngine` → canonical capability / compatibility executor；兼容工作流在迁移期可保留。

## 1. 总体结论

**存在必须修复的架构冲突。** 公共查询 API 的主入口总体遵守 `API → RAGPipeline → OrchestrationEngine → LegacyWorkflowCompatibilityExecutor`，没有发现生产查询路由直接实例化 Router/Retriever/Workflow，也未发现 `services → app.api` 反向依赖、重复注册 LangGraph 节点或重复 HTTP method/完整 URL。

但以下四项需优先修复或作出明确契约决策：

1. 严格质量接口的会话上下文仅以 `session_id` 为键，而该接口默认值为 `"default"`；`user_id` 不参与键或现有记录校验，存在跨用户串话/隐私泄露风险。
2. 严格质量异步 API 在事件循环中直接调用同步检索实现，可阻塞 FastAPI 事件循环。
3. LangGraph 的实际 state 写入/读取 `execution_id`，但 `GraphState` 未声明该字段，类型契约与运行时状态不一致。
4. 标准 SSE 与标准非流式路径的最终答案质量门禁不等价：流式合成没有事实核验，且流式图仅做 grounding/safety；这不是严格质量 Profile 的验证违约，但对同一 standard 查询形成了未声明的质量语义差异。
5. `strict_quality` 的 retrieval dispatcher 仅实现 graph/hybrid/vector；当上游产生 `web` 或 `react` 时会落入默认 vector 分支，且 answer-validator 异常会构造 `is_valid=True`/`approve` 的降级结果。

当前无法确认：异常路径下实际重试次数、熔断与超时是否会叠加到用户可接受范围；LangGraph 编译后的条件边实际运行可达性；以及所有历史公开导入/脚本的退役影响。原因是本次按要求未运行测试、未做导入运行或端到端执行。

## 2. 生产调用链与图结构

```text
POST /query
POST /api/v1/enhanced/query
POST /api/advanced-rag/query
        │
        ▼
canonical API route / query execution helper
        │  PipelineRequest(profile=standard|strict_quality|advanced)
        ▼
app.pipeline.rag_pipeline.RAGPipeline
        │  rag_pipeline.py:69-78, 96-116
        ▼
app.orchestration.engine.OrchestrationEngine
        │  engine.py:101-127, 173-206
        ▼
LegacyWorkflowCompatibilityExecutor（迁移期唯一 profile 选择器）
        ├─ standard → app.graph.execution.workflow.run_query（线程外执行）
        ├─ standard stream → app.graph.streaming.run_query_stream
        ├─ strict_quality → app.workflow.enhanced_rag_workflow.EnhancedRAGWorkflow
        └─ advanced → app.workflow.advanced_rag_workflow.AdvancedRAGWorkflow
```

证据：`app/pipeline/rag_pipeline.py:55-78,96-116,146-179` 总是构造 legacy-compatible engine；`app/orchestration/engine.py:76-127` 强制 typed services 与 compatibility executor 二选一；`app/orchestration/compatibility_executor.py:94-104,249-318` 按 Profile 只选一个 executor。`app/api/routes/compatibility/enhanced_query.py:180-197` 与 `app/api/routes/compatibility/advanced_rag.py:89-103` 通过 Pipeline 调用；标准接口由 `app/api/query/execution.py:31-114` 预处理并通过 Pipeline 调用。

标准非流式 LangGraph：

```text
START → router → adaptive_planner → entry_decider
  ├─ vector → vector_decider → graph | web | synthesis
  ├─ graph  → graph_decider  → web | synthesis
  ├─ web    → synthesis → END
  └─ react  → END（ReAct 内部自行合成）
```

`app/graph/execution/workflow.py:99-138` 静态注册 10 个互异节点；条件边没有回边，未发现静态死循环。`hybrid` 在 vector node 内并行/串行收集 vector 与 graph，是单一路径内部的组合检索，不是两条 API 入口并行执行。

## 3. 冲突清单

| 严重级别 | 冲突位置 | 冲突类型 | 证据 | 影响 | 建议 |
|---|---|---|---|---|---|
| P1 必须修复 | `app/services/sessions/context_tracker.py:19-20,78-91,119-136`; `app/api/routes/compatibility/enhanced_query.py:37-40`; `app/orchestration/compatibility_executor.py:288-295` | 会话状态隔离缺失 | 全局 `_context_store` 以 `session_id` 为键；创建时存 `user_id`，读取/更新既不以用户分区也不核对所属用户；strict API 默认 `session_id="default"`。 | 不同用户使用默认或碰撞 session id 时可读取并延续彼此上下文，属于数据隔离/隐私风险。 | 将 store key 改为稳定的 `(user_id, session_id)`（匿名用户使用明确独立 request/session 策略）；拒绝或清空 owner 不匹配既有 session；禁止 authenticated strict API 使用共享默认值。 |
| P1 必须修复 | `app/workflow/enhanced_rag_workflow.py:645-759`; `app/api/routes/compatibility/enhanced_query.py:141-197`; 对照 `app/orchestration/compatibility_executor.py:249-272` | async/sync 生命周期冲突 | strict endpoint `await RAGPipeline().execute()`；其 workflow 的 `_execute_retrieval` 直接调用同步 `run_graph_rag`/`run_vector_rag`。standard executor 对同步 `run_query` 显式使用 `asyncio.to_thread`。 | 检索、模型或向量库延迟会阻塞服务事件循环，拖慢同进程所有 async 请求和 SSE。 | 将阻塞检索移至 threadpool，或为检索能力提供 async port；统一由 orchestration 管理阻塞边界和 deadline。 |
| P1 必须修复 | `app/graph/execution/state.py:4-33`; `app/graph/execution/workflow.py:29-34,87-94,151-183` | State 类型契约不一致 | `run_query` 写入 `execution_id`，节点包装器读取它；`GraphState` 没有此字段。 | 静态类型、节点契约、可观测性包装出现分叉；未来严格 state 校验或 reducer 改造可能丢失跟踪 ID。 | 在 `GraphState` 声明 `execution_id: str | None`，并将观察字段与业务字段分组；补充 state schema 测试。 |
| P1 必须修复（质量契约） | `app/graph/streaming/stream_processor.py:543-553,617-657`; `app/agents/synthesizer/generation.py:365-403,450-570`; `app/orchestration/compatibility_executor.py:249-272` | SSE/普通查询质量门禁不一致 | 非流式 standard 在线程中执行 `synthesize_answer`，该函数会进行事实核验（无运行中 loop 时）；`stream_synthesize_answer` 没有对应事实核验，stream processor 仅再做 grounding/safety。 | 相同 standard 请求的 SSE 与普通响应可能得到不同验证强度及元数据，调用方无法据接口契约预期。 | 明确 standard 的最低验证承诺；将异步事实核验/结果标识接到 SSE final event，或显式在 SSE contract 标注 `validation=not_run`。 |
| P1 必须修复 | `app/api/query/streaming/execution.py:70-89`; `app/orchestration/compatibility_executor.py:213-247`; `app/graph/streaming/stream_processor.py:59-658` | SSE async/sync 生命周期冲突 | async SSE handler 经 `async for` 消费同步流式 executor；流式 processor 内部同步迭代检索与模型生成。 | 慢检索或模型流可占用事件循环，影响并发 SSE/普通 async 请求。 | 为 stream executor 提供真正 async 的 I/O，或将同步生成器/阻塞段明确放入线程并以 async queue 转发事件。 |
| P1 必须修复 | `app/workflow/enhanced_rag_workflow.py:625-759`; 上游 route 支持见 `app/graph/routing/route_logic.py:11-21` | strict route capability 不闭合 | strict `_execute_retrieval()` 仅显式处理 graph、hybrid，其他 route 进入 vector 默认分支；route vocabulary 包含 web/react。 | strict 请求可能被静默降级为 vector，返回 route/行为与路由决策不一致。 | 添加 web/react 的受控执行分支，或在 strict route validator 中拒绝不支持 route；输出最终实际 route。 |
| P1 必须修复 | `app/workflow/enhanced_rag_workflow.py:923-958` | validation fail-open | `validate_answer()` 抛错后，workflow 标记 `validation_degraded` 却构造 `is_valid=True`、`action="approve"`、`validation_method="fast_path"`。 | strict_quality 在验证依赖故障时可把未验证答案包装为通过，破坏 Profile 名称和调用方信任。 | fail closed，或返回不可伪装为 validated 的 degraded response/status；由 API 明确映射该状态。 |
| P1 必须修复（路径语义） | `app/graph/execution/workflow.py:115-136`; `app/graph/nodes/react_node.py:114-162`; `app/agents/tool/react.py:432-459` | ReAct 绕过图级合成/验证节点 | graph 将 `react` 直接连至 END；ReAct 内部会自行 synthesis，随后仅做 grounding/safety。 | standard ReAct 与 synthesis path 的质量、citation/validation 元数据不一致；并非 strict Profile 违约，但必须形成明示契约。 | 使 ReAct 回到共享 post-processing，或在 ReAct final payload 显式记录独立验证状态并保证同一最低门槛。 |
| P2 建议修复 | `app/api/deps/query.py:113-144`; `app/graph/nodes/safe_wrappers.py:27-42`; `app/graph/nodes/vector_node.py:133-146`; `app/workflow/enhanced_rag_workflow.py:257-379` | 重试策略分层叠加 | API 全查询 `call_with_retry`、图节点检索重试、strict retrieval-quality retry 同时存在；没有一个跨层 attempt budget。 | 故障时可能放大调用次数、耗尽 deadline，且指标难以解释。静态审查不能确认每条异常路径都会叠加，故为风险而非已证实重复执行。 | 由 orchestration 下发 request-scoped retry budget/remaining deadline；保留局部重试但计入同一预算。 |
| P2 建议修复 | `app/graph/nodes/router_node.py:15-21`; `app/graph/nodes/adaptive_planner_node.py:17-35` | State 字段多写者 | router 写 `route`；adaptive planner 也回写 `route`，源码注释说明不得替换语义路由。 | 当前意图是保持原 route，但所有权不唯一，未来修改容易覆盖 router 决策。 | planner 输出独立 `execution_route`/`plan` 字段，或只读 `route`；以 TypedDict/reducer 表示字段 owner。 |
| P2 建议修复 | `app/agents/shared/quality_models.py:100-109`; `app/agents/shared/result_schemas.py:75-94` | 同名公共模型的语义重复 | 两个不同字段集合均名为 `QualityReport`，一个为 orchestrator breakdown/report，另一个为 generic agent result report。 | 导入歧义、序列化和 monkeypatch/外部调用误用风险；未发现当前相互替换的运行时故障。 | 改为语义化名称（例如 `OrchestratedQualityReport`、`AgentQualityReport`）并在旧名做受控兼容 alias；先做全仓 public-import 审计。 |
| P2 建议修复 | `AGENTS.md:207`; `app/core/config.py:93-95`; `app/services/runtime/resilience.py:25-61` | 策略/文档冲突 | AGENTS 记载熔断 5 次/60s；运行时默认读 3 次/30s。 | 运维、压测和回滚期望与实际不一致。 | 指定唯一策略 owner，修正文档或运行时默认值；部署配置须覆盖并记录最终值。 |
| P2 迁移观察 | `app/pipeline/rag_pipeline.py:69-78`; `app/orchestration/compatibility_capabilities.py:73-100`; `app/orchestration/engine.py:173-206` | typed capability path 未被生产 Pipeline 选择 | `CoreCapabilities` 能组装 typed `OrchestrationServices`，但 RAGPipeline 默认总是 `for_legacy_compatibility`；provider 仅用于 tool agent 注入。 | 不是 API 绕过，且符合 AGENTS 对迁移 executor 的允许；但 typed 编排可能长期无生产流量，难以验证或退役旧 executor。 | 为迁移设定明确启用条件、影子观测及回滚指标；在未满足前不要删除 compatibility executor。 |
| P3 暂不处理 | `config/router_calibration.json`; `config/application/router_calibration.json`; `app/agents/router/calibration.py:31-40,111-142` | 双份配置/陈旧输入 | 运行时固定使用 `config/application/router_calibration.json`；根 `config/router_calibration.json` 仍有不同统计数据。 | 人工编辑根文件不会影响运行时，造成校准数据误判。 | 将根文件标记为历史样本或在维护任务中迁移；本次不删除。 |
| P3 暂不处理 | `AGENTS.md` 配置段；`config/` | 文档与配置目录漂移 | 文档列出 `retrieval_config.json`、`retry_policy.json`、`fact_verification.json`；静态存在性检查均为 false，实际策略在 `app/core/config.py`、`app/services/runtime/retry_policy.py`、validation package。 | 新维护者可能修改不存在文件或误判生效配置。 | 更新文档到实际 owner；先确认是否有外部部署挂载这些历史文件。 |

## 4. 智能体唯一职责矩阵

| 能力 | canonical owner | 兼容入口 | 生产调用方 | 是否冲突 |
|---|---|---|---|---|
| Routing | `app.agents.router.routing.decide_route`; validator package | `app/agents/router_agent.py`; `enhanced_router_agent.py`; `router/compatibility.py` | standard graph、strict workflow，经 Pipeline/engine | 否；planner 重写 `route` 是 P2 state-owner 风险 |
| Retrieval | `rag/vector.py`, `rag/graph.py`, `rag/web.py` | root RAG agent aliases、`rag/compatibility.py` | standard graph；strict/advanced workflow，经 compatibility executor | 否；hybrid 是单工作流内部组合 |
| ReAct / multi-hop | `app.agents.tool.react.run_react_agent` | `app/agents/react_agent.py` 等 alias | standard graph 的 `react_node` | 低风险：该分支直达 END，验证语义须显式化 |
| Web research | `app.agents.rag.web.run_web_research` | legacy Web aliases | graph/strict workflow | 否 |
| Retrieval quality | `app.agents.rag.retrieval_quality.evaluate_retrieval_quality` | root quality agent alias | strict workflow | 否；strict 专属能力符合 Profile 差异 |
| Answer validation | `app.agents.validation.public.validate_answer` / cascade | `answer_validator_agent.py` module alias | strict workflow | standard SSE 未承诺同等门禁，见 P1 质量契约 |
| Context tracking | `app.services.sessions.context_tracker` | `app/services/context_tracker.py`; `context_tracker_agent.py` | strict workflow、lifespan cleanup | **是：session 未按用户隔离** |
| Quality orchestration | `app.agents.validation.quality_orchestrator.orchestrate_quality` | root orchestrator alias | strict workflow | 否 |
| Synthesis | `app.agents.synthesizer.generation` | `synthesis_agent.py`; `legacy_synthesis.py` | graph、stream、strict/advanced workflow | SSE 与普通路径验证行为不等价 |
| Safety / hallucination | grounding/safety services + validation cascade | legacy validation aliases | graph/stream/strict workflow | 否；不同 Profile 强度不同，需文档化 |

兼容包装抽查结论：`answer_validator_agent.py` 与 `services/context_tracker.py` 是 module-object alias；`synthesis_agent.py`、`router_agent.py` 是直接 re-export；`enhanced_router_agent.py` 与 `rag/compatibility.py` 是形状适配/委托，没有发现隐藏的第二套同职业务实现。`config/refactor_cleanup_allowlist.json:143-150,181-190` 已将多项 compatibility 模块列出 replacement 与 `remove_when`；当前仍有 production 兼容 caller，不能据文件名删除。

## 5. GraphState 字段读写冲突清单

| 字段 | 写入方 | 读取方 | 结论 |
|---|---|---|---|
| `execution_id` | `execution/workflow.py:171-183` | `execution/workflow.py:29-34,87-94` | **已证实未声明字段（P1）**。 |
| `route` | `nodes/router_node.py:15-21`; `nodes/adaptive_planner_node.py:28-35` | entry decider、routing logic、后续 nodes | 双写者（P2）；当前注释限制 planner 不改变 router 语义。 |
| `next_step` | `nodes/decider_nodes.py:5-15` | `decider_nodes.py:17-22`; graph conditional edges | 静态一致。 |
| `vector_result` / `graph_result` / `web_result` | 对应检索 node；hybrid vector node；ReAct finalizer；部分 fallback | decider、synthesis、explainability | 分支共享字段；静态没有并行 graph merge，需保持默认结果 shape 一致。 |
| `answer` | synthesis node；ReAct finalizer | final result/explainability | 互斥分支写入；ReAct 直达 END，形成与 synthesis path 不同的验证语义。 |
| `grounding` / `answer_safety` | synthesis node、ReAct node、stream finalization | output/explainability | 有写入，未发现类型冲突；stream 不带 validation 对等字段。 |
| `detected_language` / `language_preference` | synthesis/ReAct/stream | output | 未见静态类型矛盾；实际语言策略一致性需运行验证。 |

## 6. 重复实现、旧入口与兼容包装

| 项目 | 结论 | 处理条件 |
|---|---|---|
| `app.graph.workflow` → `app.graph.execution.workflow` | module alias；registry/生产应使用 canonical execution path | 先审计 tests/scripts/公开 import，满足 allowlist 的 `remove_when` 才可退役。 |
| `app.agents.enhanced_rag_workflow` → `app.workflow.enhanced_rag_workflow` | module alias；strict compatibility executor 仍实际调用 canonical workflow | strict Profile 迁移到已验证 typed orchestration 后才可退役。 |
| `app.agents.answer_validator_agent`、`app.services.context_tracker` | module-object alias，保持 monkeypatch/历史 import | 当前 `legacy_agent_runtime`/lifespan 与兼容 callers 仍在使用，不能删除。 |
| `app.agents.synthesis_agent`、`app.agents.router_agent` | direct re-export | 需全仓生产、脚本、公开文档导入均迁出。 |
| `EnhancedRouterAgent`、`RetrievalService` adapters | 委托 canonical router/vector/graph/web；不是独立路由/检索算法 | 保留直到 legacy contract 不再需要。 |
| `QualityReport` 两个 schema | **非包装，语义重复** | 应做命名/导入迁移设计；不得机械删除任一模型。 |
| standard/strict/advanced workflows | 三个 profile executor 并存，但均在 Pipeline→Engine 内选择 | 符合当前 AGENTS 迁移约束；不应视为调用绕过。 |

## 7. 必须修复、建议修复、暂不处理

### 必须修复

1. 严格质量 context store 的 user/session 隔离与默认 session 策略。
2. strict 与 SSE workflow 内同步 I/O 对 async 事件循环的阻塞。
3. strict workflow 对 web/react route 的能力闭合和“最终实际路由”记录。
4. strict 验证失败的 fail-open 行为。
5. `GraphState.execution_id` 的状态 schema 漏项。
6. standard SSE、非流式及 ReAct 的事实核验/validation 契约及最终事件标识。

### 建议修复

1. 用 request-scoped 总预算统管 API、节点与 workflow 的 retry/deadline。
2. 固定 `route` 的单一写入 owner，planner 另用规划字段。
3. 区分两个 `QualityReport` 的名称与导入路径。
4. 对齐 AGENTS 与运行时的 circuit breaker、配置文件说明。
5. 为 typed `OrchestrationServices` 制定启用、影子观测与 compatibility executor 退休门槛。

### 暂不处理

1. 不删除任何 compatibility 模块：静态发现的 production 生命周期/管理端/legacy callers 仍使其成为公开边界。
2. 不将 hybrid 同时检索认定为冲突：它是 route 内的设计性 evidence fusion。
3. 不将 ReAct 直达 END 认定为确定缺陷：standard Profile 本就未声明 strict validation；应先确立质量契约。
4. 不更改路由：静态完整 URL+HTTP method 检查无重复。

## 8. 静态检查结果

| 检查 | 结果 | 说明 |
|---|---|---|
| AST | 通过：600 个 `app/**/*.py`，0 语法错误 | 使用 `utf-8-sig` 解析；先前 UTF-8 直接解析遇到的 10 个 BOM 文件为扫描假阳性。 |
| Ruff | 主审环境未执行完成（工具阻塞） | `rag-local` 环境中 `python -m ruff` 无模块；`conda run` 在启动前出现 Windows Unicode/charmap 错误。Sol/Luna 的独立输出分别报告 618/866 项、范围不一致，无法作为可复现的统一计数；本次不得把 Ruff 记为通过。 |
| 路由重复检查 | 通过：137 个 route declaration，0 个重复 method + 完整 prefix URL | AST 汇总 `APIRouter` prefix 与 decorators；仅是静态检查。 |
| Agent/Workflow 绕过 | 生产 query 路由未发现直接导入/执行 Agent 或 Workflow | 唯一 API→Agent import 是 `app/api/deps/runtime.py:24-28` 构造 app-scoped governed `ToolAgent`，通过 Pipeline 作为注入能力使用，非 query bypass。 |
| services → API 反向依赖 | 通过：0 个 `app.services/app.agents/app.workflow/app.graph/app.orchestration/app.pipeline → app.api` import | AST import scan。 |
| Pipeline/Orchestration 调用链 | 通过（迁移模式） | Pipeline 始终进入 Engine；Engine 通过唯一 compatibility executor 选择 profile。typed services 路径当前未被默认生产 Pipeline 选择，记录为迁移观察。 |
| LangGraph 节点注册 | 通过：10 个 `add_node`，无重复 name | `app/graph/execution/workflow.py:101-110`。 |
| 测试/运行时/导入执行 | 未执行 | 依委托的“只读、不运行测试”限制；因此条件边可达性、重试叠加与外部兼容性保持未确认。 |

## 9. 评审分工与交叉核验

本轮按委托并行安排了 Sol 的只读架构冲突/最终审核与 Luna 的独立调用链/结构审查。两者均给出“存在必须修复的架构冲突”，共同确认 State 漂移、上下文隔离、同步/SSE 执行分叉、熔断/重试双实现和 ReAct 图级质量链绕过；Luna 额外确认 strict `web/react` route 不闭合与 validation fail-open，Sol 复核了 typed orchestration 尚未成为默认生产执行分支。

对 Sol 的“typed orchestration 未进入生产路径”结论，本报告按根 `AGENTS.md` 的明确迁移约束处理为 P2 迁移观察，而非当前绕过缺陷：现阶段允许 retained workflows 作为 Pipeline 后的 compatibility executor。其成为必须修复项的前提是项目决定将 typed engine 作为生产 canonical path。两位审查者的 Ruff 数量不一致，故主审不采纳任何一个总数，只登记工具不可复现状态。

## 10. 实施计划（仅建议，不执行）

1. 先修复 P1 context key 和 strict 的阻塞 I/O，并用多用户并发、默认 session、断开/重连场景验证。
2. 补齐 GraphState，给 state owner 和 final result schema 加静态/单元契约测试。
3. 定义 standard normal/SSE 的最低质量门槛，令 final SSE 事件暴露 `validation_status`。
4. 统一 retry/deadline/circuit-breaker policy owner，随后更新 AGENTS 和配置文档。
5. 仅在 typed path 有影子指标、回滚窗口及 0 生产兼容 import 证据后，考虑退役兼容 executor/wrapper。
