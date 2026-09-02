# Multimodal Knowledge Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保持 QueryMind 现有 API 和可用能力的前提下，将生产查询收敛到 6 个核心 Agent、LangGraph、Knowledge Orchestrator、三层知识体系、多模态证据链和确定性隐私/权限治理。

**Architecture:** `RAGPipeline` 保持唯一公开门面，LangGraph 只负责状态和条件编排，节点调用现有或新增 Service。现有 Vector/BM25/Graph/Web/hybrid/reranker、session、RBAC、validation 和 ingestion 逻辑优先复用；通过 shadow、兼容投影和特性开关逐步切换，不长期保留两套业务编排。

**Tech Stack:** Python 3.11、FastAPI、Pydantic v2、LangGraph 1.x、LangChain、ChromaDB、Neo4j、BM25、BGE reranker、React 18、TypeScript。

**Spec:** `docs/superpowers/specs/2026-08-24-multimodal-knowledge-platform-design.md`

## Global Constraints

- 所有 Python 命令使用 `conda run -n rag-local`。
- 现有 URL、HTTP 方法、SSE 基础事件、MCP 方法和响应字段保持兼容；新增字段必须可选。
- 不删除正常功能，不把 Retriever、Privacy、Permission、Memory Resolver 或 Orchestrator 变成 Agent。
- 不移动现有模块只为匹配目录；新边界出现时才新建文件。
- 所有 LLM/检索/视觉调用都有 timeout、受控 retry、fallback 和结构化 failure reason。
- 当前阶段不创建、不修改测试文件，不在任务中包含测试代码；只使用静态检查、导入探针、构建、现有质量门禁和人工验收场景验证实现。
- 全请求 Verifier 回检最大 1 次；所有上限从 `app/core/config.py` 读取。
- 未授权数据必须在 Retriever 调用和模型上下文构建前被排除。
- 任何 legacy 删除都要求 caller audit、shadow 对比和回滚窗口完成。
- 当前工作树已有未提交修改；执行前先由用户完成/保存这些修改，实施者不得覆盖。

---

## 文件职责映射

| 路径 | 终态职责 |
| --- | --- |
| `app/pipeline/rag_pipeline.py` | 唯一公开执行门面和兼容结果投影 |
| `app/orchestration/langgraph/state.py` | 可检查点化的 `WorkflowState` |
| `app/orchestration/langgraph/nodes.py` | 节点到 Service 的薄适配，不含业务重复实现 |
| `app/orchestration/langgraph/workflow.py` | 节点、条件边、interrupt/resume、最大回路 |
| `app/agents/{router,clarification,planner,knowledge,synthesizer,verifier}` | 六个结构化 Agent 边界 |
| `app/knowledge/orchestrator.py` | 知识源执行、并发、超时和降级 |
| `app/knowledge/{fusion,deduplication,context}.py` | 单一融合/去重/上下文实现 |
| `app/retrievers/` | 继续拥有 Vector/BM25/Graph/Web/Multimodal 适配实现 |
| `app/services/evidence/` | Evidence manifest、artifact、版本和引用解析 |
| `app/wiki/` | 生成、更新、版本、diff、rollback、source mapping |
| `app/services/sessions/memory_store.py` | 现有本地长期记忆兼容后端 |
| `app/memory/` | Resolver、LongTermMemoryPort、GBrain adapter |
| `app/privacy/` | 输入/上下文/输出 DLP 与图片 mask |
| `app/services/security/access_scope.py` | tenant/RBAC/ACL/document/field scope 的统一解析 |
| `app/evaluation/` | 检索、RAG、Agent 决策和执行指标 |

## Canonical Interfaces

以下名称和签名是所有任务共享的唯一契约；实施时不得另起同义类型：

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Literal, Protocol, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator


KnowledgeSource = Literal["vector", "bm25", "graph", "wiki", "memory", "multimodal", "web", "tool"]
EvidenceLayer = Literal["evidence", "knowledge", "memory", "web", "tool"]
Modality = Literal["text", "table", "image", "page", "graph"]


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    document_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    page: int | None = Field(default=None, ge=1)
    chunk_id: str | None = None
    image_id: str | None = None


class KnowledgeSourcePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: KnowledgeSource
    queries: tuple[str, ...] = Field(min_length=1)
    top_k: int = Field(ge=1, le=100)
    timeout_ms: int = Field(ge=100, le=120_000)
    required: bool = False


class KnowledgeStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    sources: tuple[KnowledgeSourcePlan, ...] = Field(min_length=1)
    rewrite: bool = True
    rerank: bool = True
    visual_required: bool = False
    rationale: str = Field(min_length=1)


class AccessScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    permissions: frozenset[str] = frozenset()
    document_ids: frozenset[str] = frozenset()
    allowed_sources: frozenset[str] = frozenset()
    acl_tags: frozenset[str] = frozenset()
    allowed_fields: frozenset[str] = frozenset()


class RouterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    intent: str = Field(min_length=1)
    complexity: Literal["simple", "complex"]
    completeness: Literal["complete", "incomplete", "ambiguous"]
    next_stage: Literal["clarification", "planner", "knowledge"]
    knowledge_hints: frozenset[KnowledgeSource] = frozenset()
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class ClarificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action: Literal["ask", "continue", "skipped"]
    question: "ClarificationQuestion | None" = None
    context: "ClarificationContext"
    complete_query: str | None = None
    workflow_thread_id: str = Field(min_length=1)


class ContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence: tuple["EvidenceItem", ...] = ()
    rendered_context: str = ""
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class CandidateAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    text: str
    citations: tuple[EvidenceRef, ...] = ()
    unresolved_items: tuple[str, ...] = ()


class MemoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    memory_id: str = Field(min_length=1)
    kind: Literal["preference", "stable_fact", "task", "explicit_remember"]
    content: str = Field(min_length=1)
    updated_at: str
    expires_at: str | None = None
    supersedes: str | None = None


class WorkflowError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    stage: str = Field(min_length=1)
    code: str = Field(min_length=1)
    retryable: bool = False
    fallback_used: bool = False


class VerificationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["approved", "retry_retrieval", "rejected", "degraded"]
    unsupported_claims: tuple[str, ...] = ()
    citation_errors: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    missing_aspects: tuple[str, ...] = ()
    retry_query: str | None = None

    @model_validator(mode="after")
    def require_retry_query(self):
        if self.status == "retry_retrieval" and not (self.retry_query or "").strip():
            raise ValueError("retry_retrieval requires retry_query")
        return self


class WorkflowState(TypedDict, total=False):
    request: "OrchestrationRequest"
    privacy: "PrivacyResult"
    permission_scope: "AccessScope"
    route_decision: "RouterDecision"
    clarification: "ClarificationResult"
    complete_query: str
    task_plan: "TaskPlan"
    knowledge_strategy: KnowledgeStrategy
    context: "ContextBundle"
    candidate_answer: "CandidateAnswer"
    verification: VerificationDecision
    final_answer: "FinalAnswer"
    retry_count: int
    errors: tuple["WorkflowError", ...]
    trace: tuple["ExecutionEvent", ...]


class KnowledgeAgentPort(Protocol):
    async def decide(
        self,
        request: "OrchestrationRequest",
        route: "RouterDecision",
        plan: "TaskPlan | None",
        retry_feedback: VerificationDecision | None = None,
    ) -> KnowledgeStrategy: ...


class KnowledgeOrchestratorPort(Protocol):
    async def retrieve(
        self,
        strategy: KnowledgeStrategy,
        scope: "AccessScope",
        trace: Callable[["ExecutionEvent"], Awaitable[None]],
    ) -> "ContextBundle": ...


class LongTermMemoryPort(Protocol):
    async def search(self, query: str, scope: "AccessScope", top_k: int) -> Sequence["MemoryItem"]: ...
    async def upsert(self, item: "MemoryItem", scope: "AccessScope") -> "MemoryItem": ...
    async def expire(self, memory_id: str, scope: "AccessScope") -> bool: ...
```

## Task 0：冻结基线并修复导入阻断项

**Files:**
- Modify: `app/agents/shared/base.py:200`
- Reconcile only if still present after user changes: `app/api/routes/public/auth.py`, `app/api/routes/public/documents.py`
- Modify: `langgraph.json` only in Task 3

**Interfaces:**
- Produces: 核心模块可导入的 Python 基线；不改变业务行为。

- [ ] 在独立工作树执行 `git status --short`，确认本计划不覆盖当前 6 个已修改后端文件和 Tailwind 工作。
- [ ] 直接运行核心模块导入探针，记录 `app.agents.shared.base`、`app.api.main`、`app.pipeline.rag_pipeline` 当前的导入异常。
- [ ] 将 `fallback_func: callable | None` 改为 `fallback_func: Callable[..., Any] | None`，并从 `collections.abc` 导入 `Callable`。
- [ ] 仅在当前用户修改仍留下 F821 时补齐 `HTTPException` import；不顺手处理无关格式化。
- [ ] 重新运行核心模块导入探针和 `python -m compileall app`，确认无导入或语法阻断。
- [ ] 运行 `conda run -n rag-local ruff check app`，记录并只修复阻断本计划的 F821/F401/I001；UP038 可单独机械提交。
- [ ] 运行现有检索质量门禁和前端 build，保存基线结果；建议提交 `fix: restore application import baseline`。

## Task 1：建立跨层契约与稳定引用

**Files:**
- Create: `app/domain/knowledge.py`
- Create: `app/domain/workflow.py`
- Modify: `app/domain/contracts.py`
- Modify: `app/pipeline/contracts.py`

**Interfaces:**
- Produces: `KnowledgeStrategy`、`KnowledgeSourcePlan`、`EvidenceRef`、扩展 `EvidenceItem`、`VerificationDecision`、`WorkflowError`。

- [ ] 定义枚举 `EvidenceLayer = evidence|knowledge|memory|web|tool` 和 `Modality = text|table|image|page|graph`。
- [ ] 定义 `KnowledgeSourcePlan(source, queries, top_k, timeout_ms, required)` 与 `KnowledgeStrategy(sources, rewrite, rerank, visual_required, rationale)`；source 只允许 `vector/bm25/graph/wiki/memory/multimodal/web/tool`。
- [ ] 扩展 `EvidenceItem`，新增可选 `version/chunk_id/image_id/artifact_uri/modality/layer/acl_tags`，保持现有构造方可运行。
- [ ] 定义 `VerificationDecision(status, unsupported_claims, citation_errors, conflicts, missing_aspects, retry_query)`，`status=retry_retrieval` 时强制 `retry_query` 非空。
- [ ] 为 Pipeline citation metadata 增加上述 provenance，不删除现有字段。
- [ ] 运行 Pydantic schema 导入与序列化探针，核对缺失 provenance、未知 layer/modality 和 retry_query 约束均按设计拒绝；建议提交 `feat: add knowledge workflow contracts`。

## Task 2：统一确定性 Privacy 与 Permission preflight

**Files:**
- Create: `app/privacy/models.py`
- Create: `app/privacy/text.py`
- Create: `app/privacy/image_masking.py`
- Create: `app/privacy/dlp.py`
- Create: `app/privacy/service.py`
- Create: `app/services/security/access_scope.py`
- Modify: `app/orchestration/request.py`
- Reuse: `app/services/security/outbound_redaction.py`, `app/services/answer_safety.py`, `app/services/security/rbac.py`, `app/api/deps/documents.py`

**Interfaces:**
- Produces: `PrivacyService.inspect_input(text, images) -> PrivacyResult`、`mask_context(items, scope) -> tuple[EvidenceItem, ...]`、`filter_output(answer, citations, scope) -> DLPResult`、`AccessScopeResolver.resolve(actor, requested_scope) -> AccessScope`。

- [ ] 从 outbound redaction 提取可复用 pattern/state，不改变现有 provider proxy 行为；输入和输出分别记录 detection/redaction 数，不记录原始秘密。
- [ ] 实现图片 detector/mask port；默认本地规则实现生成 masked derivative，未配置 detector 时对外部 VLM fail closed，对纯本地 OCR 标记 degraded。
- [ ] `RequestActor` 增加可选 `tenant_id`，`RequestScope` 增加 `acl_tags/allowed_fields`；旧请求自动映射到 `tenant_id=user_id` 兼容域。
- [ ] `AccessScopeResolver` 复用 document registry 的 owner/visibility/allowed_sources，统一计算 document_ids 和 ACL；禁止 Retriever 自行扩大 scope。
- [ ] 用脱敏样例和 admin/public/owner/ACL 场景进行人工验收，确认 data URL 不会原样发送给外部 VLM、缺失身份时私有检索 fail closed；建议提交 `feat: add deterministic privacy and access preflight`。

## Task 3：构建 LangGraph 单一工作流骨架

**Files:**
- Create: `app/orchestration/langgraph/__init__.py`
- Create: `app/orchestration/langgraph/state.py`
- Create: `app/orchestration/langgraph/nodes.py`
- Create: `app/orchestration/langgraph/workflow.py`
- Create: `app/orchestration/langgraph/checkpoint.py`
- Modify: `app/orchestration/engine.py`
- Modify: `app/pipeline/rag_pipeline.py`
- Modify: `langgraph.json`

**Interfaces:**
- Consumes: Task 1/2 contracts。
- Produces: `build_workflow(services, settings) -> CompiledStateGraph`、`OrchestrationEngine.execute/execute_stream` 兼容接口。

- [ ] 定义 `WorkflowState`，为 evidence/errors/trace 指定显式 reducer；candidate/final 等单写字段禁止 reducer 合并。
- [ ] 节点仅调用 `WorkflowServices` protocol，不直接 import Retriever/DB/API。
- [ ] checkpoint key 使用 `tenant_id:user_id:session_id:request_id`；缺身份时只允许 request-local in-memory state。
- [ ] workflow 中写死的仅是拓扑；最大 retry、timeout 和 feature flag 从 Settings 注入。
- [ ] 将 `OrchestrationEngine` 变为 graph facade，保留方法签名；迁移期旧顺序执行器改名为 private shadow baseline，禁止生产直接构造。
- [ ] 更新 `langgraph.json` 为 `app.orchestration.langgraph.workflow:get_graph`，运行本地 import probe 并导出图结构，核对主节点顺序及两条条件边。
- [ ] 使用无副作用 stub services 执行一次简单、一次澄清、一次 verifier retry 流程，确认 retry 不超过一次；建议提交 `feat: add canonical langgraph workflow`。

## Task 4：拆分 Router 与 Clarification 并形成完整 Query

**Files:**
- Modify: `app/agents/router/service.py`
- Create: `app/agents/clarification/__init__.py`
- Create: `app/agents/clarification/service.py`
- Reuse then retire internals from: `app/agents/router/enhanced_service.py`, `hybrid_clarification.py`
- Modify: `app/api/routes/public/clarification.py`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/pages/chat/hooks/useClarification.ts`

**Interfaces:**
- Produces: `RouterDecision(intent, complexity, completeness, next_stage, knowledge_hints)`；`ClarificationResult(action, question, context, complete_query)`。

- [ ] 通过 Agent trace 人工核对简单问题直达、复杂完整问题进入 Planner、信息缺失进入 Clarification，并确认 Router 阶段没有 retriever 调用。
- [ ] 将已存在的缺失字段识别、recommended options、asked_questions 逻辑移动到独立 Clarification Service；保留旧 EnhancedRouter 代理避免旧 import 失效。
- [ ] `complete_query` 使用“原问题 + 已确认字段”的结构化渲染，并保证同一 field 不重复询问。
- [ ] clarification API 响应新增 `complete_query/workflow_thread_id/resume_token`；旧字段不变。
- [ ] 修复前端完成澄清后仍提交 `originalQuestion` 的逻辑，改为提交 response.complete_query；skip 明确提交原问题。
- [ ] 在现有聊天界面完成一次推荐选项和一次自由输入澄清，核对最终请求使用 `complete_query` 且不重复提问；建议提交 `feat: integrate clarification into workflow`。

## Task 5：实现真正有界的 Planner DAG

**Files:**
- Modify: `app/agents/planner/service.py`
- Modify: `app/domain/contracts.py`
- Create: `app/agents/planner/prompts.py`

**Interfaces:**
- Produces: `TaskPlan` 中每个 task 包含 dependencies、parallel_group、knowledge_required、tool_required、budget。

- [ ] 用简单问题和复杂比较问题检查结构化 Planner 输出：前者为单 task 且不额外调用 LLM，后者包含两个可并行检索 task 和一个依赖它们的 synthesis task。
- [ ] 复用现有 Kahn cycle validation，新增 max task count、max depth、总 retrieval/tool budget 校验。
- [ ] Planner 使用结构化输出；解析失败降级为现有 `_direct_task`，并写 `plan_fallback_reason`。
- [ ] LangGraph 根据 DAG ready set 并发执行知识子任务，串行依赖必须等待前置结果。
- [ ] 检查 cycle、max task count、max depth 和总预算拒绝路径，确认 Planner fallback 有明确 reason；建议提交 `feat: add bounded planner dag`。

## Task 6：新增 Knowledge Agent（只决策，不检索）

**Files:**
- Create: `app/agents/knowledge/__init__.py`
- Create: `app/agents/knowledge/service.py`
- Create: `app/agents/knowledge/prompts.py`
- Modify: `app/orchestration/capabilities.py`

**Interfaces:**
- Produces: `KnowledgeAgentService.decide(request, route, plan, retry_feedback=None) -> KnowledgeStrategy`。

- [ ] 用精确术语、关系、图表、稳定偏好和内部知识不足五类样例核对 source selection 分别选择 BM25+Vector、Graph、Multimodal、Memory 和获准 Web。
- [ ] 将 Router 的知识源判断降为 hints；Knowledge Agent 综合 plan、capability availability、privacy scope 和 retry_feedback 生成最终策略。
- [ ] 使用 Pydantic structured output；失败时以确定性规则生成最小安全策略 vector+bm25。
- [ ] 用 import graph 静态扫描确认 `app.agents.knowledge` 不依赖 `app.retrievers`、Neo4j、Chroma、WikiStore 或 MemoryStore；建议提交 `feat: add knowledge strategy agent`。

## Task 7：把现有 Retriever 收敛到 Knowledge Orchestrator

**Files:**
- Create: `app/knowledge/__init__.py`
- Create: `app/knowledge/orchestrator.py`
- Create: `app/knowledge/adapters.py`
- Create: `app/knowledge/fusion.py`
- Create: `app/knowledge/deduplication.py`
- Create: `app/knowledge/context.py`
- Modify: `app/agents/rag/service.py`
- Reuse: `app/retrievers/hybrid/*`, `app/retrievers/reranker.py`, `app/services/query_rewrite.py`

**Interfaces:**
- Produces: `KnowledgeOrchestrator.retrieve(strategy, scope, trace) -> ContextBundle`。

- [ ] 用 trace 核对 rewrite 只调用一次、只执行策略选中的 adapters，且并发耗时接近最慢单源而非各源总和。
- [ ] Adapter 统一返回 `tuple[EvidenceItem, ...]`，分别包裹现有 Vector、BM25、Graph、Web、Multimodal、Wiki、Memory。
- [ ] 把现有 hybrid 的 rewrite/RRF/rerank/parent expansion 抽成可复用阶段，旧 `hybrid_search_with_diagnostics` 调用新阶段保持行为。
- [ ] Dedup key 优先 `document_id/version/chunk_id/image_id`，缺失时使用 canonical source/page/content hash；保留最高分并合并 retriever labels。
- [ ] RRF 后统一调用 BGE reranker；model 缺失/timeout 使用现有 lexical fallback，并记录 `reranker_backend/fallback_reason`。
- [ ] Context Builder 先做 AccessScope/field mask，再按 Evidence > Wiki > current context > Memory > Web/Tool 解决冲突，按 token budget 截断。
- [ ] `RAGAgentService` 改成兼容代理，不再独立并发和简单分数融合。
- [ ] 运行现有检索质量门禁，并检查 source scope、RRF、dedup、reranker 和 fallback diagnostics；建议提交 `feat: unify retrieval in knowledge orchestrator`。

## Task 8：独立 Synthesizer 与 Verifier，限制一次回检

**Files:**
- Modify: `app/agents/synthesizer/service.py`
- Create: `app/agents/verifier/__init__.py`
- Create: `app/agents/verifier/service.py`
- Reuse: `app/agents/validation/*`, `app/services/retrieval/citation_grounding.py`, `app/services/evidence_conflict.py`
- Modify: `app/orchestration/finalization.py`

**Interfaces:**
- Produces: Synthesizer 只生成 `CandidateAnswer`；Verifier 返回 Task 1 的 `VerificationDecision`。

- [ ] 用 Evidence/Wiki 冲突样例核对答案采用 Evidence 并披露冲突，且 image/table 引用保留 image_id/chunk_id。
- [ ] Synthesizer 消费 ContextBundle，不自行检索、不调用 Memory、不执行 Output DLP。
- [ ] Verifier 检查 claim support、citation target、遗漏、冲突和无依据内容；复用现有 cascade/NLI/rules。
- [ ] LangGraph 条件边仅在 `retry_retrieval` 且 retry_count=0 时回 Knowledge；第二次失败输出 rejected/degraded，绝不第三次调用。
- [ ] Finalization 只保留 deterministic grounding、安全和质量汇总，Verifier 业务判断不再重复执行。
- [ ] 查看执行 trace，确认 supported、retry、rejected/degraded 三条路径及一次重检上限；建议提交 `feat: add bounded verifier loop`。

## Task 9：建立可版本化 Evidence 与统一 Office ingestion

**Files:**
- Create: `app/services/evidence/models.py`
- Create: `app/services/evidence/artifact_store.py`
- Create: `app/services/evidence/manifest.py`
- Modify: `app/services/documents/registry.py`
- Modify: `app/ingestion/loaders/dispatch.py`
- Create: `app/ingestion/loaders/office_loader.py`
- Modify: `app/services/documents/ingest.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `ParsedDocument(document, pages, text_blocks, tables, images)`；`EvidenceManifest(document_id, version, source, sha256, artifacts, status)`。

- [ ] 准备非测试目录中的验收样本文档，覆盖 PDF/DOCX/PPTX/XLSX；逐类核对 document_id、version、page/sheet、chunk/table/image provenance。
- [ ] registry 的 document_id 与 source path 解耦；同文档新 sha256 创建递增 version，历史 manifest 不覆盖。
- [ ] ArtifactStore 在配置根目录下按 tenant/document/version 保存原文件、解析 manifest、图片和 masked derivative；写入使用临时文件原子替换。
- [ ] dispatch 增加 `.docx/.pptx/.xlsx/.xls`；Docling 处理 PDF/DOCX/PPTX，openpyxl/pandas 处理 Excel，失败链记录 parser/fallback。
- [ ] ingestion 统一输出 normalized metadata，并把 version/tenant/owner/visibility/ACL 传给 corpus、Chroma、BM25 和 Neo4j。
- [ ] reindex 只替换目标 document/version 的索引；删除/回滚不误删同名其他租户文件。
- [ ] 执行四类文档导入、更新、回滚和跨租户拒绝场景，核对 manifest 与索引记录；建议提交 `feat: add versioned evidence ingestion`。

## Task 10：打通原图、OCR/VLM 与 Visual Retrieval

**Files:**
- Modify: `app/services/multimodal/models.py`
- Modify: `app/services/multimodal/processor.py`
- Modify: `app/services/multimodal/image_processor.py`
- Modify: `app/retrievers/multimodal_retriever.py`
- Create: `app/ingestion/embedding/visual.py`
- Remove broken import usage by adapting to: `app/retrievers/stores/vector.py`

**Interfaces:**
- Produces: `VisualEmbeddingProvider.embed_page/image -> vector`；multimodal result 返回 artifact_uri、ocr_text、description、page、image_id、version。

- [ ] 移除不存在的 `chroma_store` 导入路径，并通过 import probe 确认新 adapter 使用现有 vector store port。
- [ ] ImageContent 增加 `document_id/version/artifact_uri/masked_artifact_uri/embedding_model`，保留 `doc_id/page_number` 兼容属性。
- [ ] 在 OCR/VLM 前调用 Task 2 image masking；外部 provider 只能拿 masked bytes，本地原图仅写 owner-scoped artifact store。
- [ ] 实现 ColPali provider feature flag；可用时索引 page/image visual vector，不可用时描述 embedding fallback，并写 capability diagnostics。
- [ ] MultimodalRetriever 接受 AccessScope filter，返回 text/image/table/chart/page 统一 EvidenceItem。
- [ ] 将 Multimodal adapter 接入 Task 7 Orchestrator，并验证架构图/统计图 query 会选择 visual source。
- [ ] 用架构图、流程图和统计图验收 visual retrieval、图片脱敏边界和 source scope；建议提交 `feat: enable traceable visual retrieval`。

## Task 11：实现带来源和回滚的 LLM Wiki

**Files:**
- Create: `app/wiki/models.py`
- Create: `app/wiki/store.py`
- Create: `app/wiki/generator.py`
- Create: `app/wiki/updater.py`
- Create: `app/wiki/source_mapping.py`
- Create: `app/wiki/retriever.py`
- Modify: `app/core/config.py`

**Interfaces:**
- Produces: `WikiEntry`、`WikiVersion`、`WikiStore.create_version/diff/rollback`、`WikiRetriever.retrieve(query, scope)`。

- [ ] 在写入入口强制 Wiki 版本至少包含一个 EvidenceRef，无来源请求直接拒绝并记录 reason。
- [ ] 采用与现有 prompt version store 相同的 SQLite 事务模式，实现 entry/version/source_map 三表；路径进入 Settings。
- [ ] generator 仅接受 EvidenceBundle，保存模型和 prompt version；updater 根据 document version 计算 impacted entries。
- [ ] rollback 创建新 active version 并标记 `rollback_from`，不删除历史；diff 输出字段级/文本级差异。
- [ ] WikiRetriever 将结果标记 `layer=knowledge`，Orchestrator 冲突规则确保 Evidence 胜出。
- [ ] 人工执行 create/update/diff/rollback 和 Evidence 冲突场景，核对版本链及来源映射；建议提交 `feat: add source-grounded versioned wiki`。

## Task 12：加入 Memory Resolver 与 GBrain 端口

**Files:**
- Create: `app/memory/models.py`
- Create: `app/memory/resolver.py`
- Create: `app/memory/long_term.py`
- Create: `app/memory/gbrain.py`
- Modify: `app/services/sessions/memory_store.py`
- Modify: `app/api/utils/memory_helpers.py`
- Modify: `app/core/config.py`

**Interfaces:**
- Produces: `MemoryResolver.resolve(current, candidates) -> ResolvedMemory`、`should_write(exchange) -> MemoryWriteDecision`、`LongTermMemoryPort`。

- [ ] 用当前上下文覆盖、重复、更新、过期和冲突五类场景核对 Resolver 输出，未解决冲突不得直接写入 prompt。
- [ ] 把当前“回答完成即 add_candidate”改为先经过 `should_write`；只允许 preference/stable_fact/task/explicit_remember，敏感值默认拒绝。
- [ ] 现有 JSON MemoryStore 实现 LongTermMemoryPort，保持 session API 和已有数据可读。
- [ ] GBrain adapter 只在 `GBRAIN_ENABLED` 且 provider factory 成功构造时启用；timeout/认证错误降级本地 store 并记录 failure reason，不把未知 API 合约硬编码进业务层。
- [ ] MemoryRetriever 经 Resolver 后返回 `layer=memory` EvidenceItem；不把整段聊天无条件检索。
- [ ] 通过 session API 和 trace 核对本地 fallback、GBrain disabled/timeout、敏感记忆拒绝和过期过滤；建议提交 `feat: add governed long term memory`。

## Task 13：统一 Evaluation 与 Observability

**Files:**
- Modify: `app/evaluation/models.py`
- Modify: `app/evaluation/metrics.py`
- Replace duplicate logic in: `app/evaluation/services/evaluation_service.py`
- Modify: `app/services/observability/agent_execution_tracker.py`
- Modify: `app/domain/events.py`
- Modify: `scripts/ci_quality_gate.py`

**Interfaces:**
- Produces: 每个 execution_id 的 stage、decision、source hits、pre/post rerank ranks、token usage、latency、retry、failure reason；离线指标统一从 `app.evaluation.metrics` 计算。

- [ ] 修复 evaluation models/service Schema 漂移，删除重复 metric 算法，MRR/NDCG 使用唯一实现。
- [ ] Retrieval trace 记录 rewrite 数、各源 hit/latency、RRF rank、dedup count、reranker before/after 和 context drop reason。
- [ ] Agent trace 记录 Router expected/actual、Planner DAG、KnowledgeStrategy、Verifier decision/retry，不记录未脱敏 prompt/evidence。
- [ ] 从模型 runtime usage metadata 汇总 input/output/total tokens；provider 不返回 usage 时明确 `available=false`。
- [ ] 添加 faithfulness、answer relevance、citation correctness、router accuracy、reranker NDCG delta 数据集字段和报告。
- [ ] 质量门禁同时检查 retrieval、privacy isolation、max retry、citation provenance 和 API contract；运行现有 gate 并审阅报告。
- [ ] 建议提交 `feat: unify rag evaluation and traces`。

## Task 14：API/SSE/MCP/前端兼容与影子切换

**Files:**
- Modify: `app/api/routes/public/query_stream.py`
- Modify: `app/api/query/streaming/execution.py`
- Modify: `app/mcp/server.py`
- Modify: `frontend/src/features/execution-trace/*`
- Modify: `frontend/src/pages/chat/components/MessageCard.tsx`
- Modify: `frontend/src/types/api.ts`
- Modify: `app/core/config.py`, `.env.example`, `config/env/base.env.example`

**Interfaces:**
- Produces: 旧客户端不变，新客户端可显示 clarification、strategy、verification 和 image citation。

- [ ] 从当前 OpenAPI、SSE 事件样本和 MCP 响应保存兼容基线，新字段只允许 additive。
- [ ] 增加 `ORCHESTRATION_BACKEND=engine|langgraph`、`LANGGRAPH_SHADOW_ENABLED`、`VERIFIER_MAX_RETRIES=1` 及各 privacy/multimodal/wiki/memory 配置；业务代码不读裸环境变量。
- [ ] shadow 同时运行新图但禁用 persistence/tool side effect；比较 route、evidence IDs、answer support、validation、latency。
- [ ] 前端忽略未知事件保持兼容，并新增 image/page citation 打开逻辑；未授权 artifact URI 不渲染。
- [ ] 依次按 internal -> 5% -> 25% -> 100% 开启 LangGraph；任一权限泄漏、retry>1、P95/faithfulness 超阈值自动回退。
- [ ] 100% 稳定窗口结束后，`OrchestrationEngine` 只代理 LangGraph，删除 private legacy sequencing；caller audit 和 removal register 留证。
- [ ] 对比切换前后的 OpenAPI、SSE、MCP 和前端构建结果，确认旧字段及事件顺序兼容；建议提交 `feat: cut over query execution to langgraph`。

## Task 15：全链路验收与文档收敛

**Files:**
- Modify: `README.md`, `CLAUDE.md`
- Modify: `docs/architecture/overview.md`, `docs/architecture/multi-agent-system.md`, `docs/architecture/retrieval-system.md`
- Modify: `docs/development/refactor-removal-register.md`
- Modify: `docs/audits/2026-08-24-multimodal-agent-architecture/*`

**Interfaces:**
- Produces: 可复核的终态架构、配置、迁移/回滚和运行证据。

- [ ] 用真实验收样本跑 PDF/DOCX/PPTX/XLSX ingestion，核对 document/version/page/chunk/image/artifact provenance。
- [ ] 执行 cross-tenant、RBAC、ACL、field mask、OCR/VLM mask、Output DLP 红队场景，预期 0 unauthorized context/citation。
- [ ] 运行 `conda run -n rag-local ruff check app scripts`、核心模块 import probe 和 `python -m compileall app`。
- [ ] 运行 retrieval gate，报告 Recall@K/MRR/NDCG/reranker delta；运行 RAG/Agent eval，报告 faithfulness/relevance/router accuracy。
- [ ] 在 `frontend` 运行 `npm.cmd run type-check` 和 `npm.cmd run build`。
- [ ] 对普通、澄清、复杂并行、Graph、Wiki、Memory、多模态、Web fallback、Verifier retry 各执行一次端到端 trace，确认每次能定位 failure stage。
- [ ] 更新文档中已过时的“LangGraph 已删除”和虚构旧路径，记录新图唯一入口与 rollback 配置。
- [ ] 最终 caller audit 确认没有生产路径绕过 RAGPipeline/LangGraph；建议提交 `docs: finalize multimodal knowledge platform architecture`。

## 7/30/90 天交付节奏

### 7 天：恢复可信基线与安全骨架

- 完成 Task 0-3：修复核心模块导入、契约、Privacy/Permission preflight、LangGraph skeleton。
- 保持生产仍走现有 Engine，新图只运行无副作用验收流程。
- 出口标准：核心模块可导入；质量门禁与前端 build 可复现；LangGraph 无无限边；scope fail closed。

### 30 天：完成六 Agent 与统一检索主链

- 完成 Task 4-8、Task 13 的基础 trace：Clarification、Planner DAG、Knowledge Agent、Orchestrator、Synthesizer、Verifier。
- 以 shadow 对比 typed old path 与 LangGraph，不启用 Wiki/GBrain/ColPali 生产写入。
- 出口标准：6 个 Agent 均有结构化输出；RRF/dedup/rerank 只有一个实现；Verifier 最多一次回检；API/SSE contract 不变。

### 60 天：完成 Evidence 与多模态

- 完成 Task 9-10：Office ingestion、版本化 Evidence、原图/Mask/OCR/VLM/视觉向量、image citation。
- 出口标准：四类文档 fixture 全通过；图表问题可命中 visual evidence；外部视觉 provider 不接收原始敏感图。

### 90 天：完成 Wiki/Memory、切流与治理闭环

- 完成 Task 11-15：Wiki version/diff/rollback、Memory Resolver/GBrain 端口、全量评测、前端展示、100% 切流和旧顺序编排退役。
- 出口标准：所有验收标准满足；执行 trace 可定位阶段；回滚窗口关闭后只有一个生产编排实现。

## 明确决策门

1. Task 0 未通过时禁止开始架构修改。
2. Task 2 权限矩阵未通过时禁止接入任何新 Retriever。
3. Task 7 未证明单一融合链前禁止启用 Knowledge Orchestrator 生产流量。
4. Task 10 未证明 masked image boundary 前禁止外部 OCR/VLM。
5. GBrain 未提供可验证 provider/SDK 时保持 disabled，本地 MemoryStore 继续服务且不得宣称 GBrain 已完成。
6. 任一 cross-tenant 泄漏、Verifier 循环超限或 citation provenance 丢失均阻止 100% 切流。
