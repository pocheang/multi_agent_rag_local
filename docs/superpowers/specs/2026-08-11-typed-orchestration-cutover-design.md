# Typed Orchestration Cutover Design

Date: 2026-08-11  
Status: Approved design baseline; implementation not started.

## Purpose

Replace all production query execution that currently depends on retained
compatibility workflows with one typed, canonical orchestration path. The
terminal architecture has no `LegacyWorkflowCompatibilityExecutor`, no
profile-specific legacy workflow executor, and no second business workflow for
SSE.

This is a behavior redesign, not a package-organization-only refactor. It
supersedes the compatibility-retention direction in prior organization plans
for the execution path only. Existing public HTTP and MCP contracts remain
supported throughout the cutover, but their implementation is moved to the
typed engine before legacy code is removed.

## Goals

1. Make `RAGPipeline -> OrchestrationEngine(typed services)` the sole
   production execution path for standard, strict-quality, advanced, SSE, and
   MCP queries.
2. Make each capability have one business owner: routing, planning, retrieval,
   tools/ReAct, synthesis, safety, validation, quality, and context.
3. Express Profile differences as typed policy, not as a different workflow
   implementation.
4. Make normal and SSE queries run the same orchestration stages and emit a
   consistent final answer/validation contract.
5. Remove the context ownership, fail-open validation, State schema, blocking
   async, route-capability, retry, and circuit-breaker conflicts documented by
   the 2026-08-11 architecture audit.
6. Retire the legacy execution chain after evidence-based cutover gates pass.

## Non-goals

- No new public endpoint, MCP method, retrieval provider, model provider, or
  frontend feature.
- No change to existing URL, HTTP method, authorization, source-scope, or
  response-model semantics unless a response gains explicitly additive
  execution metadata.
- No deletion based only on file naming. Public imports and monkeypatch seams
  are migrated deliberately before removal.
- No permanent dual-run mode. Shadow execution is temporary validation only.

## Terminal architecture

```text
HTTP / SSE / MCP
        |
        v
RAGPipeline
        |
        v
OrchestrationEngine(typed OrchestrationServices)
        |
        +-- request policy / deadline / retry budget
        +-- route
        +-- optional plan
        +-- retrieve evidence
        +-- optional tool / ReAct
        +-- synthesize
        +-- sentence grounding + safety
        +-- validation
        +-- optional quality report
        +-- FinalAnswer or streamed ExecutionEvent sequence
```

`RAGPipeline` remains the only public execution facade. It translates the
public request into `OrchestrationRequest`, selects a `PipelineProfile`, and
normalizes `FinalAnswer` into the existing response shape. It must not select a
workflow, construct a legacy executor, or call an Agent directly.

`OrchestrationEngine` is the only stage-sequencing owner. It receives typed
services and an explicit `ExecutionPolicy`; constructing it with a
compatibility executor is removed at the terminal state.

## Canonical capability ownership

| Capability | Canonical owner | Required terminal behavior |
| --- | --- | --- |
| Routing | `app.agents.router.routing` and router validator | Emits immutable semantic `RouteDecision`; planner cannot overwrite it. |
| Planning | `app.agents.planner` | Produces optional `TaskPlan`; route-specific execution hints are separate from semantic route. |
| Retrieval | `app.agents.rag.vector`, `graph`, `web`, fusion service | Returns one `EvidenceBundle` regardless of vector/graph/web/hybrid source. |
| Tool/ReAct | `app.agents.tool` | Produces tool results and supplemental evidence; never returns a terminal unvalidated answer. |
| Synthesis | `app.agents.synthesizer.generation` | Produces a candidate answer from `EvidenceBundle`. |
| Safety/grounding | canonical safety and citation-grounding services | Applies to every terminal answer, including ReAct and stream paths. |
| Validation | `app.agents.validation` | Emits an explicit `ValidationStatus`; a validation exception cannot be represented as approved. |
| Quality | `app.agents.validation.quality_orchestrator` | Runs only where policy enables it and returns one named report schema. |
| Context | `app.services.sessions.context_tracker` | Keys state by `(user_id, session_id)` and rejects owner mismatch. |
| Resilience | `app.services.runtime` | Owns one request-scoped deadline, retry budget, and circuit-breaker registry. |

Compatibility modules may temporarily re-export canonical symbols while callers
migrate, but cannot contain workflow sequencing or alternative business rules.

## Typed contracts

The implementation must converge on these stable boundaries. Exact Pydantic or
dataclass placement follows existing `app.domain` conventions.

```python
class OrchestrationRequest:
    question: str
    profile: PipelineProfile
    actor: RequestActor
    session_id: str
    source_scope: SourceScope
    conversation: tuple[ConversationMessage, ...]
    execution_id: str | None
    deadline: datetime
    retry_budget: RetryBudget

class EvidenceBundle:
    route: RouteDecision
    plan: TaskPlan | None
    items: tuple[Evidence, ...]
    citations: tuple[Citation, ...]
    diagnostics: RetrievalDiagnostics

class ValidationStatus:
    state: Literal["validated", "degraded", "rejected"]
    approved: bool
    method: str
    issues: tuple[ValidationIssue, ...]

class FinalAnswer:
    answer: str
    citations: tuple[Citation, ...]
    route: RouteDecision
    evidence: EvidenceBundle
    grounding: GroundingReport
    safety: SafetyReport
    validation: ValidationStatus
    quality_report: OrchestratedQualityReport | None
    execution_metadata: Mapping[str, Any]
```

`ValidationStatus(state="degraded")` must never set `approved=True`. A strict
profile returns an explicit degraded or rejected outcome if required validation
cannot run; it must not synthesize a passing validation result.

If LangGraph remains an internal implementation detail, it uses one complete
`GraphState` schema. The schema includes `execution_id`, semantic route,
execution plan, evidence, candidate answer, grounding, safety, validation,
quality, retry state, and final answer. Nodes return only fields they own;
reducer rules are explicit for every multi-writer collection.

## Profile policy

Profiles are policies over the same stages, not executor selection.

| Stage | standard | strict_quality | advanced |
| --- | --- | --- | --- |
| Route validation | baseline route checks | required | required |
| Planner | only when route/intent requires it | optional | enabled for decomposition or multi-hop |
| Vector/graph/web retrieval | policy-selected | policy-selected | policy-selected |
| Tool/ReAct | only for an approved plan | only for an approved plan | enabled when plan requires it |
| Grounding/safety | required | required | required |
| Answer validation | minimum required validation | required cascade | required cascade |
| Quality report | omitted unless requested | required | required |
| Context tracking | optional, owner-scoped | optional, owner-scoped | optional, owner-scoped |

Every route accepted by routing policy must be executable by retrieval/tool
policy. If a profile cannot support a route, route validation rejects it with a
typed reason; it may not silently substitute vector retrieval.

## Streaming design

SSE is an output transport over the same Engine execution, not a second
workflow. The Engine publishes typed `ExecutionEvent` values from the shared
stages. The API encodes those events as existing SSE event names and order.

The final SSE event carries the same terminal data as non-streaming execution:
answer, citations, actual route, grounding/safety summary, and
`validation_status`. Token chunks may be emitted during synthesis, but a final
validation failure/degradation is visible before the stream closes. Blocking
model/retrieval APIs run through an async port or a controlled thread bridge;
they never synchronously iterate on the event loop.

## Resilience and lifecycle design

- A request owns one deadline and one decrementing retry budget. API, node, and
  capability code may not create independent budgets.
- `app.services.runtime` owns the sole circuit-breaker registry and its
  configuration. The chosen threshold/cooldown is declared once in runtime
  configuration and documented identically in `AGENTS.md`.
- App-scoped services are immutable or concurrency-safe. Request-scoped state
  lives in `OrchestrationRequest`/execution context.
- Context lifecycle cleanup is app-scoped, started once by lifespan, stopped
  once by lifespan, and never shares a context between actors.

## Legacy retirement scope

The following cease to be production execution paths and are deleted after the
cutover gates below:

- `app.orchestration.compatibility_executor.LegacyWorkflowCompatibilityExecutor`
- the `OrchestrationEngine.for_legacy_compatibility` construction path
- strict execution through `app.workflow.enhanced_rag_workflow.EnhancedRAGWorkflow`
- advanced execution through `app.workflow.advanced_rag_workflow.AdvancedRAGWorkflow`
- duplicated business sequencing in `app.graph.streaming.stream_processor`
- compatibility adapters that have no remaining public, script, test, or
  documented import after migration.

`app.graph.execution.workflow` may remain only if it becomes the typed Engine's
single internal execution graph; otherwise it is retired together with the old
workflow path. Root-level re-export aliases are removed only after their caller
audit is empty and the public migration notice/replacement is complete.

## Cutover and deletion gates

1. Typed Engine produces the existing non-stream and SSE contracts for all
   three profiles.
2. Unit, integration, contract, concurrency, and SSE-order tests pass in the
   mandated `rag-local` environment.
3. Temporary shadow comparison meets all release thresholds for a defined
   observation window: no route-policy mismatch, no cross-user context access,
   no validation-status discrepancy, no SSE final-event contract discrepancy,
   and no material regression in answer/citation quality, error rate, or P95.
4. A repository-wide import audit covers `app`, `scripts`, tests, documented
   public imports, dynamic imports, and monkeypatch targets; each legacy module
   is either migrated or explicitly retained outside the execution chain.
5. `docs/development/refactor-removal-register.md` records the final caller
   audit, replacement, and removal decision for each deleted path.
6. The rollback window closes with the typed Engine as the only enabled
   production executor. Then delete legacy code in a dedicated retirement
   change; do not leave a dormant compatibility executor.

## Error handling

- Source-scope or authorization failure remains an API-layer rejection.
- Unsupported route/profile combinations return a typed policy rejection,
  never a silent fallback.
- Validation infrastructure failure is `degraded` for standard only if the
  response clearly reports it; strict-quality and advanced reject or return a
  non-approved degraded result according to their HTTP contract.
- Retrieval failure can use only policy-approved fallback routes and records
  both requested and actual evidence strategy.
- SSE sends a terminal error/degraded event before close when it cannot emit a
  valid final answer.

## Verification requirements

- Static: AST state-field audit, import-direction audit, route uniqueness,
  duplicate implementation audit, Ruff in `rag-local`.
- Unit: each typed service, policy route matrix, retry budget, circuit breaker,
  validation failure, context owner mismatch, and GraphState schema.
- Integration: standard/strict/advanced HTTP and MCP queries, all routes,
  source scope, context isolation, and fallback policy.
- Streaming: event order, token stream, cancellation, final validation status,
  and equivalence with non-stream final answer metadata.
- Performance/concurrency: event-loop non-blocking behavior, concurrent
  users/sessions, lifecycle start/stop, P95 regression budget.

## Success criteria

The project has one production orchestration implementation; all profiles and
transports use it; all final answers pass through the same minimum safety and
validation contract; no legacy executor is importable as a supported production
path; and the removal register contains evidence for every retired component.
