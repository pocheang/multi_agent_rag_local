# Typed Orchestration Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make typed `OrchestrationEngine` the only production query executor
for standard, strict-quality, advanced, SSE, and MCP requests, then remove all
legacy workflow execution paths.

**Architecture:** Build a complete typed request/evidence/final-answer contract
and a policy-driven Engine first. Make normal and streamed requests subscribe to
that single Engine, represent Profile differences as policy, and move
validation/quality/context/resilience into shared terminal stages. Use a
temporary shadow comparison only to prove equivalence; then delete the legacy
compatibility executor and old workflows in a dedicated retirement task.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, LangGraph (optional Engine
internal), pytest, pytest-asyncio, Ruff, ChromaDB, Neo4j, MCP.

**Design:**
`docs/superpowers/specs/2026-08-11-typed-orchestration-cutover-design.md`

## Global Constraints

- Use the `rag-local` conda environment for all Python tooling.
- `RAGPipeline` remains the only HTTP/SSE/MCP public execution facade.
- Do not add a compatibility executor, a profile-specific workflow, or a
  stream-specific business workflow.
- Preserve public URLs, methods, auth/source-scope semantics, response fields,
  and SSE event names/order; additive terminal metadata is allowed.
- Standard, strict-quality, and advanced are `ExecutionPolicy` variations over
  the same Engine stages.
- Every final answer, including ReAct and SSE, must pass grounding, safety, and
  explicit validation-status handling.
- Context identity is `(user_id, session_id)`; an existing context with a
  different owner is inaccessible.
- `app.services.runtime` owns the only retry budget, deadline, and circuit
  breaker registry.
- Do not remove a legacy file until its caller/export/dynamic-import audit is
  empty and the removal register contains the evidence.
- Preserve unrelated dirty worktree changes. Do not run Git operations unless
  the user separately authorizes them.

---

## File structure and ownership

| File | Responsibility after cutover |
| --- | --- |
| `app/domain/contracts.py` | Stable `EvidenceBundle`, `ValidationStatus`, `FinalAnswer` and supporting immutable contracts. |
| `app/orchestration/request.py` | Immutable request actor, scope, deadline, retry-budget inputs. |
| `app/orchestration/policies.py` | Profile-to-stage policy only; no imports of API or workflow modules. |
| `app/orchestration/capabilities.py` | Typed capability assembly for router, planner, retrieval, tools, synthesis, validation, quality, context. |
| `app/orchestration/engine.py` | Sole sequencing owner for normal and streamed execution. |
| `app/orchestration/finalization.py` | Shared grounding, safety, validation, quality final stages. |
| `app/orchestration/streaming.py` | Typed Engine events to SSE-compatible events only; no route/retrieval/synthesis logic. |
| `app/pipeline/rag_pipeline.py` | Public request/result translation into typed Engine only. |
| `app/graph/execution/state.py` | Complete graph schema if graph remains internal. |
| `app/graph/execution/workflow.py` | Optional typed Engine graph implementation; no direct public entry. |
| `app/services/sessions/context_tracker.py` | Owner-scoped context state. |
| `app/services/runtime/{retry_policy,resilience}.py` | Single request budget and circuit breaker owner. |

## Task 1: Establish typed terminal contracts and complete GraphState

**Files:**

- Modify: `app/domain/contracts.py`
- Modify: `app/orchestration/request.py`
- Modify: `app/graph/execution/state.py`
- Create: `tests/orchestration/test_typed_contracts.py`
- Create: `tests/graph/test_graph_state_contract.py`

**Interfaces:**

- Produces `EvidenceBundle`, `ValidationStatus`, and enriched `FinalAnswer`.
- Produces a `GraphState` containing `execution_id`, `route`, `plan`,
  `evidence`, `candidate_answer`, `grounding`, `answer_safety`, `validation`,
  `quality_report`, `retry_budget`, and `final_answer`.
- Later tasks consume `ValidationStatus.approved` and `ValidationStatus.state`.

- [ ] **Step 1: Write failing immutable-contract tests**

```python
def test_degraded_validation_cannot_be_approved() -> None:
    with pytest.raises(ValidationError):
        ValidationStatus(state="degraded", approved=True, method="cascade", issues=())


def test_graph_state_declares_execution_id() -> None:
    assert "execution_id" in get_type_hints(GraphState)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `conda run -n rag-local pytest tests/orchestration/test_typed_contracts.py tests/graph/test_graph_state_contract.py -v`  
Expected: FAIL because the terminal contracts or state annotation do not yet
exist.

- [ ] **Step 3: Add immutable contracts and invariants**

```python
class ValidationStatus(ImmutableContract):
    state: Literal["validated", "degraded", "rejected"]
    approved: bool
    method: str
    issues: tuple[ValidationIssue, ...] = ()

    @model_validator(mode="after")
    def reject_degraded_approval(self) -> "ValidationStatus":
        if self.state != "validated" and self.approved:
            raise ValueError("only validated status may be approved")
        return self
```

Add every runtime field used by graph nodes to `GraphState`; do not keep
undeclared dictionary keys such as `execution_id`.

- [ ] **Step 4: Run focused tests and static state audit**

Run: `conda run -n rag-local pytest tests/orchestration/test_typed_contracts.py tests/graph/test_graph_state_contract.py -v`  
Expected: PASS.

Run an AST script that compares `state.get("...")` / state literal keys in
`app/graph` with `get_type_hints(GraphState)`; expected output has no missing
fields.

- [ ] **Step 5: Review checkpoint**

Confirm `FinalAnswer` can express rejected/degraded validation without using a
legacy payload field. Do not perform a Git operation without explicit user
authorization.

## Task 2: Assemble all canonical capabilities without legacy adapters

**Files:**

- Create: `app/orchestration/capabilities.py`
- Modify: `app/orchestration/engine.py`
- Modify: `app/agents/{router,planner,rag,tool,synthesizer,validation}/service.py`
  only where typed signatures need adaptation
- Create: `tests/orchestration/test_capabilities.py`

**Interfaces:**

- Produces `build_orchestration_services() -> OrchestrationServices`.
- `OrchestrationServices` gains explicit `finalizer` and `context` ports.
- No task after this imports `CoreCapabilities`, `RetrievalService`,
  `ReasoningService`, or `AnswerService` from compatibility modules.

- [ ] **Step 1: Write failing assembly tests**

```python
def test_typed_capability_assembly_has_all_terminal_ports() -> None:
    services = build_orchestration_services()
    assert callable(services.router)
    assert callable(services.planner)
    assert callable(services.retriever)
    assert callable(services.tool_runner)
    assert callable(services.synthesizer)
    assert callable(services.finalizer)
```

- [ ] **Step 2: Run the assembly test and verify failure**

Run: `conda run -n rag-local pytest tests/orchestration/test_capabilities.py -v`  
Expected: FAIL because the canonical assembly/finalizer port is missing.

- [ ] **Step 3: Create a non-compatibility assembly module**

```python
def build_orchestration_services() -> OrchestrationServices:
    return OrchestrationServices(
        router=RouterAgentService().route,
        planner=PlannerAgentService().plan,
        retriever=RAGAgentService().retrieve,
        tool_runner=ToolAgentService().run,
        synthesizer=SynthesizerAgentService().synthesize,
        finalizer=FinalizationService().finalize,
        context=ContextService(),
    )
```

The implementation must use canonical capability packages directly. Do not
move this code into `compatibility_capabilities.py` or retain compatibility
types in the returned service contract.

- [ ] **Step 4: Run the focused test**

Run: `conda run -n rag-local pytest tests/orchestration/test_capabilities.py -v`  
Expected: PASS.

- [ ] **Step 5: Import-direction check**

Run: `rg -n --glob '*.py' 'compatibility_capabilities|LegacyWorkflowCompatibilityExecutor|RetrievalService|ReasoningService|AnswerService' app/orchestration app/pipeline`  
Expected: only temporary retirement-task references remain; the typed assembly
has none.

## Task 3: Make ExecutionPolicy the sole Profile behavior selector

**Files:**

- Modify: `app/pipeline/profiles.py`
- Modify: `app/orchestration/policies.py`
- Create: `tests/orchestration/test_profile_policy.py`

**Interfaces:**

- Produces `ExecutionPolicy.for_profile(PipelineProfile) -> ExecutionPolicy`.
- Produces `ExecutionPolicy.validate_route(route: RouteDecision) -> None`.
- Later Engine code consumes policy flags rather than branching on profile
  workflow factories.

- [ ] **Step 1: Write the route-matrix tests**

```python
@pytest.mark.parametrize(
    "profile,route",
    [
        (PipelineProfile.STANDARD, "vector"),
        (PipelineProfile.STRICT_QUALITY, "web"),
        (PipelineProfile.ADVANCED, "react"),
    ],
)
def test_profile_policy_executes_supported_routes(profile, route) -> None:
    ExecutionPolicy.for_profile(profile).validate_route(RouteDecision(route=route))


def test_unsupported_route_is_rejected_not_rewritten() -> None:
    policy = ExecutionPolicy.for_profile(PipelineProfile.STRICT_QUALITY)
    with pytest.raises(UnsupportedRouteError):
        policy.validate_route(RouteDecision(route="unsupported"))
```

- [ ] **Step 2: Run tests and verify failure**

Run: `conda run -n rag-local pytest tests/orchestration/test_profile_policy.py -v`  
Expected: FAIL because profile policy lacks a complete route matrix.

- [ ] **Step 3: Implement one policy model**

```python
@dataclass(frozen=True)
class ExecutionPolicy:
    enable_route_validation: bool
    enable_retrieval_quality: bool
    require_answer_validation: bool
    require_quality_report: bool
    allow_planning: bool
    allowed_routes: frozenset[str]

    def validate_route(self, route: RouteDecision) -> None:
        if route.route not in self.allowed_routes:
            raise UnsupportedRouteError(route.route)
```

Map `standard`, `strict_quality`, and `advanced` to this type. Every profile
that accepts `web` or `react` must have a typed retriever/tool route for it.

- [ ] **Step 4: Run policy tests**

Run: `conda run -n rag-local pytest tests/orchestration/test_profile_policy.py -v`  
Expected: PASS.

- [ ] **Step 5: Review profile compatibility**

Verify endpoint-to-profile mapping remains `/query`, `/api/v1/enhanced/query`,
and `/api/advanced-rag/query`; no profile selects a workflow class.

## Task 4: Implement shared finalization and remove fail-open validation

**Files:**

- Create: `app/orchestration/finalization.py`
- Modify: `app/agents/validation/public.py` only for typed result adaptation
- Modify: `app/agents/validation/quality_orchestrator.py` to return the named
  `OrchestratedQualityReport`
- Create: `tests/orchestration/test_finalization.py`

**Interfaces:**

- Produces `FinalizationService.finalize(request, evidence, candidate, policy)
  -> FinalAnswer`.
- Consumes canonical grounding, safety, validation, and quality services.
- The Engine and stream path both call this one function.

- [ ] **Step 1: Write failing validation-failure tests**

```python
@pytest.mark.asyncio
async def test_strict_validation_exception_is_not_approved() -> None:
    service = FinalizationService(validator=RaisingValidator())
    answer = await service.finalize(strict_request, evidence, "candidate", strict_policy)
    assert answer.validation.approved is False
    assert answer.validation.state in {"degraded", "rejected"}


@pytest.mark.asyncio
async def test_react_answer_uses_same_finalizer() -> None:
    assert react_result.final_answer.validation.state == "validated"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `conda run -n rag-local pytest tests/orchestration/test_finalization.py -v`  
Expected: FAIL because strict workflow currently fabricates approved validation
on exceptions and ReAct finalizes itself.

- [ ] **Step 3: Implement finalization order**

```python
grounded, grounding = apply_sentence_grounding(candidate, evidence.texts)
safe, safety = sanitize_answer(grounded)
validation = await validator.validate(request.question, safe, evidence.citations)
if policy.require_answer_validation and not validation.approved:
    return FinalAnswer.rejected(safe, evidence, grounding, safety, validation)
quality = quality_service.report(...) if policy.require_quality_report else None
return FinalAnswer(..., validation=validation, quality_report=quality)
```

Turn validation exceptions into `ValidationStatus(state="degraded",
approved=False, ...)`. ReAct returns candidate text/evidence only and invokes
this service before any terminal result is emitted.

- [ ] **Step 4: Run finalization tests**

Run: `conda run -n rag-local pytest tests/orchestration/test_finalization.py -v`  
Expected: PASS.

- [ ] **Step 5: Verify no fail-open construction remains**

Run: `rg -n 'is_valid=True|action="approve"|skip_validation' app/workflow app/orchestration app/agents`  
Expected: no validation-exception path manufactures an approved result.

## Task 5: Replace engine compatibility execution with typed sequencing

**Files:**

- Modify: `app/orchestration/engine.py`
- Modify: `app/orchestration/request.py`
- Modify: `app/pipeline/rag_pipeline.py`
- Create: `tests/orchestration/test_engine_typed_execution.py`
- Create: `tests/pipeline/test_pipeline_typed_engine.py`

**Interfaces:**

- `OrchestrationEngine(services=build_orchestration_services(), policy=...)`
  is valid.
- `OrchestrationEngine(compatibility_executor=...)` is removed after Task 9.
- `RAGPipeline.execute()` delegates only to typed Engine.

- [ ] **Step 1: Write failing stage-order tests**

```python
@pytest.mark.asyncio
async def test_engine_runs_typed_stage_order() -> None:
    calls: list[str] = []
    engine = OrchestrationEngine(services=recording_services(calls))
    await engine.execute(standard_request)
    assert calls == ["route", "retrieve", "synthesize", "finalize"]


@pytest.mark.asyncio
async def test_react_plan_runs_tools_before_finalization() -> None:
    assert await run_recorded_engine(react_request) == ["route", "plan", "retrieve", "tool", "synthesize", "finalize"]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `conda run -n rag-local pytest tests/orchestration/test_engine_typed_execution.py tests/pipeline/test_pipeline_typed_engine.py -v`  
Expected: FAIL because `RAGPipeline` constructs
`OrchestrationEngine.for_legacy_compatibility()`.

- [ ] **Step 3: Implement typed Engine flow**

```python
route = await services.router(request)
policy.validate_route(route)
plan = await services.planner(request, route) if policy.should_plan(route) else None
evidence = await services.retriever(request, route, plan)
tools = await services.tool_runner(request, route, plan, evidence) if policy.should_run_tools(route, plan) else ()
candidate = await services.synthesizer(request, route, plan, evidence, tools)
return await services.finalizer(request, evidence, candidate, policy)
```

Construct this Engine from the canonical capability assembly in `RAGPipeline`.
Do not import `compatibility_executor`, `EnhancedRAGWorkflow`,
`AdvancedRAGWorkflow`, or `graph.streaming` from Pipeline or Engine.

- [ ] **Step 4: Run typed Engine and pipeline tests**

Run: `conda run -n rag-local pytest tests/orchestration/test_engine_typed_execution.py tests/pipeline/test_pipeline_typed_engine.py -v`  
Expected: PASS.

- [ ] **Step 5: Run bypass audit**

Run: `rg -n --glob '*.py' 'for_legacy_compatibility|LegacyWorkflowCompatibilityExecutor|EnhancedRAGWorkflow|AdvancedRAGWorkflow' app/pipeline app/orchestration`  
Expected: only retirement tests/documentation reference the names until Task 9.

## Task 6: Make SSE a typed Engine event adapter

**Files:**

- Create: `app/orchestration/streaming.py`
- Modify: `app/orchestration/engine.py`
- Modify: `app/api/query/streaming/execution.py`
- Modify: `app/api/routes/public/query_stream.py`
- Create: `tests/orchestration/test_typed_streaming.py`
- Create: `tests/api/test_query_stream_contract.py`

**Interfaces:**

- `OrchestrationEngine.execute_stream(request)` emits `ExecutionEvent` from the
  same stage calls as `execute(request)`.
- `encode_sse(event)` remains an API transport concern.
- Final stream event contains answer, citations, actual route, and validation
  status.

- [ ] **Step 1: Write failing stream-equivalence tests**

```python
@pytest.mark.asyncio
async def test_stream_and_normal_have_same_terminal_metadata() -> None:
    normal = await engine.execute(request)
    events = [event async for event in engine.execute_stream(request)]
    final = events[-1]
    assert final.payload["route"] == normal.route.route
    assert final.payload["validation_status"] == normal.validation.state


@pytest.mark.asyncio
async def test_stream_runs_blocking_port_off_event_loop() -> None:
    assert await probe_event_loop_responsiveness(engine, request) is True
```

- [ ] **Step 2: Run tests and verify failure**

Run: `conda run -n rag-local pytest tests/orchestration/test_typed_streaming.py tests/api/test_query_stream_contract.py -v`  
Expected: FAIL because `stream_processor.py` owns an independent business flow.

- [ ] **Step 3: Implement event-only streaming**

```python
async def execute_stream(self, request: OrchestrationRequest) -> AsyncIterator[ExecutionEvent]:
    async for event in self._execute_with_events(request):
        yield event

    # _execute_with_events calls the same typed stage functions as execute().
```

Bridge any sync model/retrieval callable with `asyncio.to_thread` and an async
queue. Move no router, retriever, ReAct, synthesis, grounding, or validation
decision into `app.api` or a stream processor.

- [ ] **Step 4: Run stream tests**

Run: `conda run -n rag-local pytest tests/orchestration/test_typed_streaming.py tests/api/test_query_stream_contract.py -v`  
Expected: PASS.

- [ ] **Step 5: Verify stream implementation ownership**

Run: `rg -n 'decide_route|run_vector_rag|run_graph_rag|run_web_research|run_react_agent|synthesize_answer' app/graph/streaming app/api/query/streaming`  
Expected: no business capability call remains outside typed orchestration.

## Task 7: Unify context, retry, circuit breaker, and async boundaries

**Files:**

- Modify: `app/services/sessions/context_tracker.py`
- Modify: `app/services/runtime/retry_policy.py`
- Modify: `app/services/runtime/resilience.py`
- Modify: `app/orchestration/degradation_strategies.py`
- Modify: `app/api/deps/query.py`
- Create: `tests/services/test_context_tracker_ownership.py`
- Create: `tests/services/test_request_resilience_budget.py`

**Interfaces:**

- `ContextKey(user_id: str, session_id: str)` is the sole storage key.
- `RetryBudget` is created once in request translation and consumed by every
  retry attempt.
- `get_circuit_breaker(component)` resolves one runtime registry.

- [ ] **Step 1: Write failing isolation and budget tests**

```python
@pytest.mark.asyncio
async def test_same_session_id_different_users_do_not_share_context() -> None:
    await update_conversation_context("u1", "default", "q1", "a1", "vector")
    assert await get_context("u2", "default") is None


def test_nested_retry_uses_one_budget() -> None:
    budget = RetryBudget(max_attempts=2)
    assert consume_retry(budget) is True
    assert consume_retry(budget) is True
    assert consume_retry(budget) is False
```

- [ ] **Step 2: Run tests and verify failure**

Run: `conda run -n rag-local pytest tests/services/test_context_tracker_ownership.py tests/services/test_request_resilience_budget.py -v`  
Expected: FAIL because context currently keys only by session and retries have
independent layers.

- [ ] **Step 3: Implement single ownership**

```python
@dataclass(frozen=True)
class ContextKey:
    user_id: str
    session_id: str


_context_store: dict[ContextKey, ConversationContext] = {}
```

Pass `RetryBudget` in `OrchestrationRequest`; remove whole-request retry from
API after Engine owns it. Make orchestration degradation strategies delegate to
runtime resilience rather than creating another `_BREAKERS` registry.

- [ ] **Step 4: Run focused tests and an event-loop test**

Run: `conda run -n rag-local pytest tests/services/test_context_tracker_ownership.py tests/services/test_request_resilience_budget.py -v`  
Expected: PASS.

Run: `conda run -n rag-local pytest tests/orchestration/test_typed_streaming.py::test_stream_runs_blocking_port_off_event_loop -v`  
Expected: PASS.

- [ ] **Step 5: Align documentation/configuration**

Update runtime configuration and `AGENTS.md` to state the single threshold and
cooldown. Remove or redirect duplicate circuit-breaker configuration sources.

## Task 8: Migrate public APIs and MCP to typed Engine; run temporary shadow comparison

**Files:**

- Modify: `app/api/query/execution.py`
- Modify: `app/api/query/streaming/execution.py`
- Modify: `app/api/routes/compatibility/enhanced_query.py`
- Modify: `app/api/routes/compatibility/advanced_rag.py`
- Modify: `app/mcp/server.py`
- Modify: `app/orchestration/shadow.py`
- Create: `tests/api/test_profile_typed_engine_contract.py`
- Create: `tests/mcp/test_typed_pipeline_contract.py`

**Interfaces:**

- All public callers construct `PipelineRequest` and call the same typed
  `RAGPipeline` methods.
- Shadow comparison is feature-flagged, non-authoritative, and records route,
  citations, validation status, latency, and terminal SSE contract differences.

- [ ] **Step 1: Write failing public-boundary tests**

```python
@pytest.mark.parametrize("path", ["/query", "/api/v1/enhanced/query", "/api/advanced-rag/query"])
def test_query_endpoint_uses_typed_pipeline(client, monkeypatch, path) -> None:
    execute = monkeypatch.spy(RAGPipeline, "execute")
    response = client.post(path, json=payload_for(path))
    assert response.status_code == 200
    assert execute.call_count == 1
```

- [ ] **Step 2: Run API and MCP tests and verify failure**

Run: `conda run -n rag-local pytest tests/api/test_profile_typed_engine_contract.py tests/mcp/test_typed_pipeline_contract.py -v`  
Expected: FAIL until all profiles/MCP stop relying on compatibility results.

- [ ] **Step 3: Switch public facades and add shadow telemetry**

Make API and MCP call typed `RAGPipeline` only. During the observation window,
run legacy execution only behind an explicit disabled-by-default shadow flag;
do not use its output for responses. Compare normalized terminal fields:

```python
ShadowComparison(
    route_match=typed.route.route == legacy["route"],
    citation_ids_match=...,
    validation_state=typed.validation.state,
    typed_latency_ms=...,
    legacy_latency_ms=...,
)
```

- [ ] **Step 4: Run API/MCP tests and static bypass audits**

Run: `conda run -n rag-local pytest tests/api/test_profile_typed_engine_contract.py tests/mcp/test_typed_pipeline_contract.py -v`  
Expected: PASS.

Run: `rg -n --glob '*.py' 'EnhancedRAGWorkflow|AdvancedRAGWorkflow|run_query_stream|LegacyWorkflowCompatibilityExecutor' app/api app/mcp app/pipeline`  
Expected: only shadow/retirement code until Task 9.

- [ ] **Step 5: Observation gate**

Define and record the observation window, traffic sample, allowed P95/error
regression, answer/citation comparison method, and zero-tolerance conditions:
cross-user context access, route-policy mismatch, validation-status mismatch,
and SSE terminal-contract mismatch.

## Task 9: Retire all old workflow execution and compatibility wrappers

**Files:**

- Delete after audits pass: `app/orchestration/compatibility_executor.py`
- Delete after audits pass: `app/workflow/enhanced_rag_workflow.py`
- Delete after audits pass: `app/workflow/advanced_rag_workflow.py`
- Delete or reduce to event-only adapter after audits pass:
  `app/graph/streaming/stream_processor.py`
- Modify/delete audited root aliases under `app/agents/`, `app/graph/`,
  `app/services/`, and `app/api/routes/`
- Modify: `config/refactor_cleanup_allowlist.json`
- Modify: `docs/development/refactor-removal-register.md`
- Create: `tests/architecture/test_no_legacy_execution_imports.py`

**Interfaces:**

- Produces an application in which `RAGPipeline` has no legacy executor
  constructor parameter.
- Produces a removal register entry for each retired path.

- [ ] **Step 1: Write failing legacy-import guard**

```python
LEGACY_EXECUTORS = {
    "app.orchestration.compatibility_executor",
    "app.workflow.enhanced_rag_workflow",
    "app.workflow.advanced_rag_workflow",
}


def test_production_modules_do_not_import_legacy_executors() -> None:
    assert find_production_importers(LEGACY_EXECUTORS) == []
```

- [ ] **Step 2: Run guard and verify the remaining caller inventory**

Run: `conda run -n rag-local pytest tests/architecture/test_no_legacy_execution_imports.py -v`  
Expected: FAIL until shadow code, aliases, scripts, and callers are migrated.

- [ ] **Step 3: Perform the retirement audit before deletion**

Run exact searches over `app`, `scripts`, `tests`, and documented imports for
every candidate path, including `__import__`, `import_module`, monkeypatch
strings, route aliases, and public `__all__` exports. Record actual callers,
replacement, cutover evidence, and deletion decision in the removal register.

Only after the observation gate closes and all caller counts are zero, remove
the legacy files and their allowlist entries with `apply_patch`.

- [ ] **Step 4: Run full verification**

Run:

```text
conda run -n rag-local pytest tests/ -v
conda run -n rag-local ruff check app tests
conda run -n rag-local python scripts/benchmark_pipeline.py
```

Expected: all tests/lint pass; benchmark meets the observation baseline; static
import guard has zero legacy execution importers.

- [ ] **Step 5: Final retirement checkpoint**

Confirm the production call graph is exactly:

```text
API / SSE / MCP → RAGPipeline → typed OrchestrationEngine → canonical capabilities
```

Confirm no dormant fallback flag can reactivate a legacy executor. Update the
removal register and architecture docs. Create a commit only if separately
authorized by the user.

## Plan self-review

| Spec requirement | Implementing tasks |
| --- | --- |
| One typed production engine | 2, 3, 5, 8, 9 |
| Same normal/SSE stages | 4, 6, 8 |
| Profile policy, no workflow selection | 3, 5, 8 |
| Context isolation | 7 |
| Fail-open validation removal | 1, 4 |
| GraphState completion | 1 |
| One resilience owner | 7 |
| Legacy executor/workflow removal | 8, 9 |
| Caller audit and removal register | 9 |

完整性检查完成：计划没有未决占位项；早期任务定义的类型名称在后续任务中
保持一致。

## Execution handoff

Plan complete. Execute only after the user separately authorizes production
code changes and confirms whether commits are permitted.

Recommended execution mode: **Subagent-Driven**. Dispatch a fresh implementer
per task, review each task against its tests and the next task's interface, and
keep retirement (Task 9) as a separately approved destructive change.
