# Agentic RAG Web MCP Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以 `RAGPipeline` 为唯一生产入口，交付可迁移的 Router → Planner → RAG → Tool → Synthesizer 编排器、网页端执行追踪以及支持第三方连接器的受控 MCP Gateway。

**Architecture:** 新的不可变 Pydantic 契约位于 `app/domain`，`app/orchestration` 只编排这些契约，Agent 和检索器仅通过明确接口接入。FastAPI 继续作为网页的认证与 SSE 边界；独立的 Streamable HTTP MCP Gateway 由后端调用，网页从不直接持有 MCP 凭据。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、LangGraph（兼容适配器）、FastMCP、React 18、TypeScript、Ant Design、Vite、pytest、Playwright。

## Global Constraints

- 所有公开查询 API 必须通过 `RAGPipeline`；迁移期间不删除任何仍有生产导入的兼容工作流。
- 跨层协议只能使用 `app/domain` 的 Pydantic 模型；禁止新增无约束 `dict[str, Any]` 协议。
- 生产业务文件保持单一职责，通常不超过约 300 行；超过时按模型、策略、服务、适配器或组件拆分。
- 网页只调用版本化 FastAPI REST/SSE API，不能直接调用 MCP JSON-RPC 或读取第三方密钥。
- MCP 远程传输为 Streamable HTTP；工具使用 `querymind_<domain>_<action>` 命名、Pydantic Schema 和风险注解。
- 写入、删除、发送或费用敏感工具必须拥有用户 scope 和一次性审批令牌；`dev_*` 工具首期只读。
- 运行 Python 命令使用 Conda 环境：`conda run -n rag-local <command>`。

---

## 文件结构与交付顺序

1. **契约与编排基础**：先建立 `app/domain` 和 `app/orchestration`，不改变现有请求结果。
2. **Agent 与检索接入**：将旧 Router、分解器、检索器、工具和 Synthesis 包装进新接口。
3. **MCP Gateway 与连接器**：先只读工具，再启用经审批的写工具。
4. **API/SSE 与前端**：前端消费稳定执行事件，再增加连接器管理和审批 UI。
5. **影子迁移与下线**：通过开关和指标完成替换，最后删除无生产引用的重复逻辑。

### Task 1: 建立不可变领域契约与执行事件

**Files:**
- Create: `app/domain/__init__.py`
- Create: `app/domain/contracts.py`
- Create: `app/domain/events.py`
- Create: `app/domain/errors.py`
- Test: `tests/domain/test_contracts.py`
- Test: `tests/domain/test_events.py`

**Interfaces:**
- Produces: `RouteDecision`, `PlanTask`, `TaskPlan`, `EvidenceItem`, `EvidenceBundle`, `ToolCall`, `ToolResult`, `FinalAnswer`, `ExecutionEvent`.
- Consumed by: Tasks 2–5; no module outside `app/domain` may redefine these shapes.

- [ ] **Step 1: 写出失败的契约不可变性和引用完整性测试。**

```python
from pydantic import ValidationError
from app.domain.contracts import EvidenceItem, EvidenceBundle


def test_evidence_bundle_rejects_fact_without_source() -> None:
    with pytest.raises(ValidationError):
        EvidenceBundle(items=(EvidenceItem(content="fact", source=""),))
```

- [ ] **Step 2: 验证测试当前失败。**

Run: `conda run -n rag-local pytest tests/domain/test_contracts.py -v`

Expected: FAIL because `app.domain.contracts` does not exist.

- [ ] **Step 3: 实现最小不可变模型和事件模型。**

```python
class EvidenceItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    document_id: str | None = None
    page: int | None = Field(default=None, ge=1)


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: tuple[EvidenceItem, ...]
```

- [ ] **Step 4: 运行领域测试。**

Run: `conda run -n rag-local pytest tests/domain/test_contracts.py tests/domain/test_events.py -v`

Expected: PASS; 测试覆盖空来源、非法页码、不可变性和 JSON 序列化。

- [ ] **Step 5: 提交本任务。**

```bash
git add app/domain tests/domain
git commit -m "feat: add orchestration domain contracts"
```

### Task 2: 实现唯一的新编排器并保留兼容入口

**Files:**
- Create: `app/orchestration/__init__.py`
- Create: `app/orchestration/request.py`
- Create: `app/orchestration/engine.py`
- Create: `app/orchestration/policies.py`
- Create: `app/orchestration/event_publisher.py`
- Modify: `app/pipeline/rag_pipeline.py`
- Test: `tests/orchestration/test_engine.py`
- Test: `tests/pipeline/test_rag_pipeline_orchestration.py`

**Interfaces:**
- Consumes: `PipelineRequest`; Task 1 contracts; injected `Router`, `Planner`, `RAGExecutor`, `ToolExecutor`, `Synthesizer` protocols.
- Produces: `OrchestrationRequest`, `OrchestrationEngine.execute(request) -> FinalAnswer` and ordered `ExecutionEvent` values.

- [ ] **Step 1: 写出简单查询不调用 Planner 或 Tool 的失败测试。**

```python
async def test_simple_question_skips_planner_and_tools(engine, router, planner, tools):
    router.return_value = RouteDecision(intent="general_qa", confidence=0.98, requires_plan=False)
    await engine.execute(OrchestrationRequest(question="hello"))
    planner.assert_not_awaited()
    tools.assert_not_awaited()
```

- [ ] **Step 2: 验证测试当前失败。**

Run: `conda run -n rag-local pytest tests/orchestration/test_engine.py::test_simple_question_skips_planner_and_tools -v`

Expected: FAIL because `OrchestrationEngine` does not exist.

- [ ] **Step 3: 实现顺序编排、预算和事件发布。**

```python
route = await self._router.route(request)
plan = await self._planner.plan(request, route) if route.requires_plan else TaskPlan.single(request.question)
evidence = await self._rag.execute(plan, request)
tool_results = await self._tools.execute(plan, request) if plan.requires_tools else ()
return await self._synthesizer.synthesize(plan, evidence, tool_results)
```

`RAGPipeline.execute` 应优先委托 `OrchestrationEngine`；仅在 `ORCHESTRATION_MODE=legacy` 时调用既有 profile adapter，并在结果 metadata 写入降级事件。

- [ ] **Step 4: 运行编排与现有管道回归测试。**

Run: `conda run -n rag-local pytest tests/orchestration tests/pipeline tests/test_api_rag_scope.py -v`

Expected: PASS; 旧请求仍返回答案、引用和路由字段。

- [ ] **Step 5: 提交本任务。**

```bash
git add app/orchestration app/pipeline/rag_pipeline.py tests/orchestration tests/pipeline
git commit -m "feat: route pipeline through orchestration engine"
```

### Task 3: 把 Router、Planner、RAG、Tool、Synthesizer 接入明确适配器

**Files:**
- Create: `app/agents/router/service.py`
- Create: `app/agents/planner/service.py`
- Create: `app/agents/rag/service.py`
- Create: `app/agents/rag/fusion.py`
- Create: `app/agents/tool/service.py`
- Create: `app/agents/synthesizer/service.py`
- Modify: `app/pipeline/adapters.py`
- Modify: `app/agents/enhanced_rag_workflow.py`
- Test: `tests/agents/router/test_service.py`
- Test: `tests/agents/planner/test_service.py`
- Test: `tests/agents/rag/test_fusion.py`
- Test: `tests/agents/tool/test_service.py`
- Test: `tests/agents/synthesizer/test_service.py`

**Interfaces:**
- Consumes: Task 1 models and existing `RoutingService`, `QueryDecomposer`, vector/graph/web retrieval and `synthesize_answer` implementations.
- Produces: protocol-conformant services consumed only by `OrchestrationEngine`; `RAGService.execute` returns `EvidenceBundle`.

- [ ] **Step 1: 写出 RAG 融合保留来源、去重但不丢引用的失败测试。**

```python
def test_fusion_deduplicates_same_document_page_and_keeps_best_score() -> None:
    bundle = fuse_evidence((vector_item, bm25_duplicate))
    assert len(bundle.items) == 1
    assert bundle.items[0].source == "vector"
```

- [ ] **Step 2: 验证测试当前失败。**

Run: `conda run -n rag-local pytest tests/agents/rag/test_fusion.py -v`

Expected: FAIL because `fuse_evidence` does not exist.

- [ ] **Step 3: 实现适配器和并发检索融合。**

```python
results = await asyncio.gather(
    self._vector.retrieve(task),
    self._bm25.retrieve(task),
    self._graph.retrieve(task),
    self._web.retrieve(task),
    return_exceptions=True,
)
return self._reranker.rank(fuse_evidence(normalize_results(results)))
```

只有 Router 允许的能力和 Planner 任务声明的能力可以执行；Tool Service 在调用前返回 `approval_required`，不得直接执行高风险工具。

- [ ] **Step 4: 运行 Agent、检索和引用回归测试。**

Run: `conda run -n rag-local pytest tests/agents tests/retrievers tests/test_citation_grounding.py -v`

Expected: PASS; Graph/Web 失败时产生降级事件，不能伪造证据。

- [ ] **Step 5: 提交本任务。**

```bash
git add app/agents app/pipeline/adapters.py tests/agents tests/retrievers
git commit -m "feat: adapt agents to orchestration contracts"
```

### Task 4: 构建远程 MCP Gateway、连接器注册表与审批机制

**Files:**
- Create: `app/mcp/gateway.py`
- Create: `app/mcp/registry.py`
- Create: `app/mcp/contracts.py`
- Create: `app/mcp/authorization.py`
- Create: `app/mcp/approvals.py`
- Create: `app/mcp/audit.py`
- Create: `app/mcp/connectors/base.py`
- Create: `app/mcp/connectors/rest.py`
- Modify: `app/mcp/server.py`
- Modify: `app/api/main.py`
- Test: `tests/mcp/test_registry.py`
- Test: `tests/mcp/test_authorization.py`
- Test: `tests/mcp/test_approvals.py`
- Test: `tests/mcp/test_gateway.py`

**Interfaces:**
- Consumes: Task 1 `ToolCall`/`ToolResult`, authenticated FastAPI identity and encrypted secret service.
- Produces: `querymind_mcp` Streamable HTTP application; `ToolRegistry.invoke(call, actor) -> ToolResult`.

- [ ] **Step 1: 写出未审批写工具绝不执行的失败测试。**

```python
async def test_write_tool_requires_matching_approval(registry, actor) -> None:
    result = await registry.invoke(write_call, actor)
    assert result.status == "approval_required"
    assert registry.connector.calls == []
```

- [ ] **Step 2: 验证测试当前失败。**

Run: `conda run -n rag-local pytest tests/mcp/test_approvals.py::test_write_tool_requires_matching_approval -v`

Expected: FAIL because `ToolRegistry` does not exist.

- [ ] **Step 3: 实现 Pydantic Schema、scope 校验、审批令牌与审计。**

```python
if descriptor.risk is ToolRisk.WRITE and not approvals.consume(call.approval_token, actor, call):
    return ToolResult(status="approval_required", summary="Confirm this operation in the web app.")
if not authorizer.allows(actor, descriptor.required_scopes):
    return ToolResult(status="denied", summary="Missing connector permission.")
return await connector.invoke(call)
```

远程部署使用 Streamable HTTP；将 `app/mcp/server.py` 的 profile 查询工具保留为 Gateway 内置的只读 `querymind_rag_*` 工具。首个第三方适配器仅实现 REST 的只读调用、超时、分页、URL allowlist 和凭据脱敏。

- [ ] **Step 4: 运行 MCP、安全和编译检查。**

Run: `conda run -n rag-local pytest tests/mcp tests/security -v; conda run -n rag-local python -m py_compile app/mcp/gateway.py`

Expected: PASS; 未授权、过期令牌、路径/URL 非法和写调用均被拒绝。

- [ ] **Step 5: 提交本任务。**

```bash
git add app/mcp app/api/main.py tests/mcp tests/security
git commit -m "feat: add governed streamable HTTP MCP gateway"
```

### Task 5: 提供版本化 API、SSE 执行事件与网页连接器界面

**Files:**
- Create: `app/api/routes/orchestration.py`
- Create: `app/api/routes/connectors.py`
- Create: `frontend/src/features/execution-trace/types.ts`
- Create: `frontend/src/features/execution-trace/ExecutionTrace.tsx`
- Create: `frontend/src/features/integrations/api.ts`
- Create: `frontend/src/features/integrations/IntegrationsPage.tsx`
- Create: `frontend/src/features/tool-approval/ToolApprovalDialog.tsx`
- Modify: `app/api/routes/enhanced_query.py`
- Modify: `frontend/src/pages/chat/hooks/useMessageActions.ts`
- Modify: `frontend/src/pages/chat/hooks/streamEventHandlers.ts`
- Modify: `frontend/src/App.tsx`
- Test: `tests/api/test_orchestration_stream.py`
- Test: `tests/api/test_connectors.py`
- Test: `frontend/src/features/execution-trace/ExecutionTrace.test.tsx`
- Test: `frontend/src/features/integrations/IntegrationsPage.test.tsx`

**Interfaces:**
- Consumes: `ExecutionEvent` from Task 2 and connector/approval APIs from Task 4.
- Produces: `/api/v1/orchestration/stream`, `/api/v1/connectors`, `/api/v1/tool-approvals`; typed frontend rendering of known events.

- [ ] **Step 1: 写出未知 SSE 事件被安全忽略、已知事件进入执行轨迹的失败测试。**

```typescript
it("records a tool approval event and ignores unknown events", () => {
  expect(reduceExecutionEvent(state, { type: "tool_approval", payload })).toMatchObject({ pendingApproval: payload });
  expect(reduceExecutionEvent(state, { type: "future_event" })).toEqual(state);
});
```

- [ ] **Step 2: 验证测试当前失败。**

Run: `cd frontend; npm test -- --run ExecutionTrace.test.tsx`

Expected: FAIL because `reduceExecutionEvent` does not exist. If no test runner is configured, add Vitest and its `test` script before implementing the reducer.

- [ ] **Step 3: 实现 API 事件映射和小型前端 feature。**

```python
async for event in engine.stream(request):
    yield f"data: {event.model_dump_json()}\n\n"
```

```typescript
switch (event.type) {
  case "tool_approval": return { ...state, pendingApproval: event.payload };
  case "completed": return { ...state, finalAnswer: event.payload };
  default: return state;
}
```

连接器页面只能显示名称、scope、健康状态和脱敏凭据；提交凭据后必须清空浏览器内存中的明文值。

- [ ] **Step 4: 运行 API、前端单测与构建。**

Run: `conda run -n rag-local pytest tests/api/test_orchestration_stream.py tests/api/test_connectors.py -v; cd frontend; npm run build`

Expected: PASS; TypeScript 无错误，网页不包含 MCP URL 或原始凭据。

- [ ] **Step 5: 提交本任务。**

```bash
git add app/api frontend/src tests/api frontend/package.json frontend/vitest.config.ts
git commit -m "feat: expose orchestration trace and connector UI"
```

### Task 6: 影子流量迁移、质量门禁与旧路径下线

**Files:**
- Create: `app/orchestration/shadow.py`
- Create: `config/orchestration_rollout.json`
- Create: `scripts/compare_orchestration_results.py`
- Modify: `app/pipeline/profiles.py`
- Modify: `app/api/utils/query_helpers.py`
- Modify: `app/api/routes/query.py`
- Modify: `app/api/routes/advanced_rag.py`
- Modify: `app/api/routes/enhanced_query.py`
- Modify: `docs/development/mcp.md`
- Test: `tests/orchestration/test_shadow.py`
- Test: `tests/api/test_query_profile_compatibility.py`

**Interfaces:**
- Consumes: new `FinalAnswer` and existing compatibility payloads.
- Produces: percent rollout configuration, shadow comparison report and a verified import list proving which legacy wrappers remain necessary.

- [ ] **Step 1: 写出影子模式不改变用户响应、但记录差异的失败测试。**

```python
async def test_shadow_mode_returns_primary_result_and_records_difference(client, recorder):
    response = await client.post("/api/v1/query", json={"question": "q"})
    assert response.json()["answer"] == "legacy answer"
    assert recorder.comparisons[0].candidate_answer == "orchestrated answer"
```

- [ ] **Step 2: 验证测试当前失败。**

Run: `conda run -n rag-local pytest tests/orchestration/test_shadow.py -v`

Expected: FAIL because `ShadowExecutor` does not exist.

- [ ] **Step 3: 实现按 profile 的影子和百分比切换策略。**

```python
mode = rollout.mode_for(request.profile, request.user)
if mode == "shadow":
    primary, candidate = await run_shadow_pair(request)
    recorder.record(compare(primary, candidate))
    return primary
return await orchestrator.execute(request) if mode == "new" else await legacy.execute(request)
```

仅当 API 兼容测试、引用覆盖率、P95 延迟和回滚观察期均通过时，才删除一个确认无生产导入的 legacy adapter；每次删除前运行 `rg -n "<adapter_name>" app tests` 并将结果写入变更记录。

- [ ] **Step 4: 运行完整回归、质量门禁和前端构建。**

Run: `conda run -n rag-local pytest -q; conda run -n rag-local python scripts/ci_quality_gate.py --dataset data/eval/retrieval_eval.jsonl --min-recall 0.35 --report-md audit_output/quality-report.md; cd frontend; npm run build`

Expected: PASS; 若依赖或数据集缺失，标记为 blocked 并记录重跑命令，不能将其报告为功能失败。

- [ ] **Step 5: 提交本任务。**

```bash
git add app/orchestration config scripts app/pipeline app/api docs/development/mcp.md tests/orchestration tests/api
git commit -m "feat: roll out orchestrated RAG pipeline safely"
```

## 计划自检

- 设计稿中的执行流、契约、MCP Gateway、网页边界、安全审批、质量门禁和迁移下线分别由 Tasks 1–6 覆盖。
- 所有跨任务接口名称均在其首次任务中定义；后续任务只消费已定义的 `ExecutionEvent`、`ToolResult`、`EvidenceBundle` 和 `FinalAnswer`。
- 本计划没有使用未定义的待定工作；唯一条件分支是测试工具尚未配置时先添加明确的 Vitest 配置，然后再执行前端测试。
