# QueryMind 智能体合并实施计划

> **对应规格：** `docs/superpowers/specs/2026-07-28-agent-consolidation-spec.md`
> **状态：** 待实施
> **执行方式：** 按任务顺序执行；每项验收通过前不得开始下一项。

**目标：** 在不重做现有功能、不破坏 API 契约和不迁移数据的前提下，消除重复智能体实现与重复工作流编排。

## 执行约束

- 全部 Python 命令使用 `conda run -n rag-local`。
- 不新增、修改、移动或删除 tests/ 下的任何文件，也不修改 CI 或工作流配置；现有测试和质量门禁仅作为只读回归验证运行。
- 保留现有 Router、查询拆分、向量/图谱/网页检索、ReAct、Self-RAG、引用、NLI、事实核验、安全、会话上下文能力。
- 保留 `/query`、`/api/v1/enhanced/query`、`/api/advanced-rag/query` 的请求和响应兼容性。
- 迁移期旧实现只能作为兼容适配器；未完成本地/测试环境对比、现有回归验证和直接切换后的回滚观察前不得删除。
- 每个任务仅提交本任务范围的改动，并运行列出的验证命令。

## 任务 1：建立行为基线与契约测试

**修改：** 仅修改运行时代码；不修改任何测试文件。

- [ ] 锁定三条 API 的响应字段、引用、语言、来源过滤、超时和降级行为。
- [ ] 为 Router、Retriever、Validator 注入 mock，保证测试不依赖真实模型。
- [ ] 在执行追踪中记录 Profile、模型调用数、token、验证触发原因和重生成次数。
- [ ] 记录旧链路的检索质量、引用完整率、时延和 token 基线。

**验收：** 三条旧链路都有可自动比较的基线，契约测试不访问外部模型。

```powershell
conda run -n rag-local pytest tests/agents/test_synthesis_citation.py tests/agents/test_route_validator.py -q
conda run -n rag-local python scripts/ci_quality_gate.py --dataset data/eval/retrieval_eval.jsonl --min-recall 0.35 --report-md audit_output/agent-consolidation-baseline.md
```

## 任务 2：定义统一管线契约和 Profile

**新增：** `app/pipeline/contracts.py`、`app/pipeline/profiles.py`。

- [ ] 定义统一 `PipelineRequest` 和 `PipelineResult`。
- [ ] 定义 `standard`、`strict_quality`、`advanced` Profile，映射三个现有 API 的默认能力。
- [ ] 锁定模型调用预算：standard 不进行无条件 LLM 自审；深度验证和重生成均最多一次。
- [ ] 保持 Advanced 的查询拆分和 Self-RAG 为显式开关。

**验收：** Profile 可以表达旧入口差异，但尚不切换任何请求流量。

```powershell
conda run -n rag-local pytest -q
conda run -n rag-local ruff check app/pipeline
```

## 任务 3：收敛路由与查询拆分

**修改：** `app/agents/router_agent.py`、`app/agents/enhanced_router_agent.py`、`app/graph/nodes/adaptive_planner_node.py`、`app/workflow/advanced_rag_workflow.py`。

- [ ] 将 `router_agent.decide_route` 封装为唯一 RoutingService。
- [ ] 将 EnhancedRouter 收敛为“可选拆分 + 调用 RoutingService”的兼容包装器。
- [ ] 将 adaptive planner 限制为检索参数与失败降级；不得随意覆盖语义路由。
- [ ] 所有子问题经同一 RoutingService 路由。

**验收：** 新旧路由的 route、skill、agent_class、低置信度回退结果一致。

```powershell
conda run -n rag-local pytest tests/agents/test_router_accuracy.py tests/agents/test_router_enhanced.py tests/agents/test_route_validator.py -q
```

## 任务 4：收敛向量与图谱检索

**修改：** 三份 Vector RAG 文件、两份 Graph RAG 文件、图节点、`safe_wrappers.py`。

- [ ] 以 UnifiedVectorRAG 的能力作为唯一 VectorRetrievalService 实现。
- [ ] 旧 Vector 和 Enhanced Vector 改为薄转发；Self-RAG 成为可选评估策略。
- [ ] 合并基础与 PDF 增强 Graph RAG 为统一 GraphRetrievalService 的内部策略。
- [ ] Graph 空结果/故障通过统一 VectorRetrievalService 回退。
- [ ] 统一所有检索结果字段及诊断信息。

**验收：** 质量门禁不低于基线，来源隔离保持，生产调用不再直接进入重复检索实现。

```powershell
conda run -n rag-local pytest tests/unit/test_enhanced_vector_rag_agent.py tests/test_retrieval_strategy.py tests/test_graph_rag_agent.py tests/test_graph_rag_agent_enhanced.py -q
conda run -n rag-local python scripts/ci_quality_gate.py --dataset data/eval/retrieval_eval.jsonl --min-recall 0.35 --report-md audit_output/agent-consolidation-retrieval.md
```

## 任务 5：收敛回答生成与质量验证

**修改：** `synthesis_agent.py`、`answer_validator_agent.py`、`fact_verification.py`、`citation_grounding.py`、`quality_orchestrator_agent.py`。

- [ ] AnswerService 只负责一次生成，保留语言、引用优先和生成降级。
- [ ] 统一验证顺序：规则/引用 → 证据落地与安全 → NLI → 低置信度深度 LLM → 最多一次重生成。
- [ ] 将 synthesis 的多轮自审改为 strict_quality 可选策略；standard 默认关闭。
- [ ] 合并事实核验、答案验证、句子证据落地的结果，避免重复扫描。

**验收：** standard token 低于基线；strict_quality 的事实性、引用完整率和安全测试不回退。

```powershell
conda run -n rag-local pytest tests/agents/test_synthesis_citation.py tests/agents/test_answer_validator.py tests/agents/test_answer_validator_cascade.py tests/agents/test_fact_verification.py tests/agents/test_quality_orchestrator.py -q
```

## 任务 6：将三条 API 迁入唯一编排入口

**新增：** `app/pipeline/rag_pipeline.py`、`app/pipeline/adapters.py`。

**修改：** 三个 API 路由、`app/graph/workflow.py`、增强/Advanced 工作流、SSE 处理器。

- [ ] 实现唯一 `RAGPipeline.execute(request, profile)`。
- [ ] `/query`、增强 API、Advanced API 分别转换为 standard、strict_quality、advanced Profile。
- [ ] API 层只保留认证、限流、请求转换和响应序列化。
- [ ] SSE 复用相同事件契约。
- [ ] 在本地或测试环境比较新旧的路由、引用、质量、时延与 token；不在生产请求中执行影子调用。

**验收：** API/SSE 契约兼容；单次追踪不再重复路由或重复质量链。

```powershell
conda run -n rag-local pytest tests/test_advanced_rag_workflow.py tests/agents/test_enhanced_workflow.py tests/test_workflow_fixes.py tests/integration/test_multilingual_workflow.py tests/api -q
```

## 任务 7：最终验证、删除遗留代码与代码审查

**修改：** `AGENTS.md` 和开发文档；删除通过调用扫描确认无用的遗留包装层。

- [ ] 直接切换后，如错误率、P95、Recall、引用完整率、来源隔离或 token 预算回退，立即切回旧管线。
- [ ] 直接切换后的回滚观察完成后，删除无生产 import 的重复实现。
- [ ] 增加 CI 守卫，禁止新生产代码导入已退役模块。
- [ ] 更新架构说明，明确规范组件与 Profile，不再宣称所有智能体必经。

**验收：** 只有一个生产编排入口，遗留模块无生产 import，完整测试、lint、质量门禁通过。

```powershell
conda run -n rag-local pytest tests/ -q
conda run -n rag-local ruff check app tests
conda run -n rag-local python scripts/ci_quality_gate.py --dataset data/eval/retrieval_eval.jsonl --min-recall 0.35 --report-md audit_output/agent-consolidation-final.md
git diff --check
git status --short
```
