# Backend Organization Refactor Plan

**Goal:** Finish organizing the existing Python backend into clear,
responsibility-owned packages while preserving its public behavior and import
compatibility.

**Scope:** `app/`, backend configuration and backend-refactor documentation
only. Do not create or edit tests, CI/workflow files, frontend code,
dependencies, database migrations, or deployment configuration. Do not commit
unless the user explicitly requests it.

**Compatibility rule:** A historical module may be deleted only after an
import audit shows that no runtime code imports it. A moved public module keeps
a minimal re-export at the original path until all callers use its canonical
path.

## Target file ownership

| Package | Responsibility | Public boundary |
| --- | --- | --- |
| `app/api/` | FastAPI HTTP/SSE transport and application wiring | routes depend on pipeline contracts only |
| `app/domain/` | immutable request, answer, evidence, and event contracts | no I/O or framework code |
| `app/pipeline/` | profile/request conversion and engine delegation | `RAGPipeline` |
| `app/orchestration/` | stage sequencing, events, policies, and shadow seams | `OrchestrationEngine` |
| `app/agents/router/` | route-decision implementation and typed adapter | `RouterAgentService` |
| `app/agents/planner/` | task planning adapter | `PlannerAgentService` |
| `app/agents/rag/` | vector, graph, web retrieval and evidence fusion | `RAGAgentService` |
| `app/agents/tool/` | ReAct/tool compatibility adapter | `ToolAgentService` |
| `app/agents/synthesizer/` | answer construction and templates | `SynthesizerAgentService` |
| `app/agents/validation/` | validation stages and cascade | `ValidationCascade` |
| `app/agents/shared/` | primitives used by multiple Agent capabilities | explicitly exported shared symbols only |
| `app/agents/legacy/` | short-lived compatibility adapters that do not own business logic | re-exports and request/response adaptation only |
| `app/mcp/` | MCP registry, authorization, approval, gateway, and audit | MCP protocol boundary |
| `app/services/` | storage, connector, telemetry, security, and other infrastructure | service interfaces, never workflow sequencing |

## Task 1: Produce an ownership inventory before moving code

**Files:**

- Modify: `config/refactor_cleanup_allowlist.json`
- Modify: `docs/development/refactor-removal-register.md`
- Inspect: every direct `app/agents/*.py`, `app/api/*.py`, and
  `app/api/routes/*.py` module

**Work:**

1. Search repository runtime imports for every root Agent module and API
   compatibility module; exclude only test and frontend paths from the caller
   count.
2. Classify each module as `canonical_capability`, `shared_primitive`,
   explicit `compatibility` re-export, `compatibility_adapter`,
   `historical_debt`, or `delete_candidate`.
3. For every compatibility or deletion candidate, record its canonical
   replacement, actual callers, owner, and the exact condition for removal.
4. Correct the existing allowlist so it describes the inventory rather than
   granting a blanket exemption to a module.

**Result:** No backend file is moved or removed solely because it is flat,
large, or old.

## Task 2: Complete the Agent capability packages

**Files:**

- Modify: `app/agents/__init__.py`
- Create/modify: `app/agents/shared/__init__.py` and focused shared modules
  needed by more than one capability
- Create/modify: `app/agents/legacy/__init__.py` and one adapter per audited
  historic import family
- Modify: `app/agents/router/{__init__.py,service.py}`
- Modify: `app/agents/planner/{__init__.py,service.py}`
- Modify: `app/agents/rag/{__init__.py,service.py,fusion.py}`
- Modify: `app/agents/tool/{__init__.py,service.py}`
- Modify: `app/agents/synthesizer/{__init__.py,service.py}`
- Modify: `app/agents/validation/{__init__.py,cascade.py,citations.py,deep.py,models.py,nli.py,rules.py}`

**Work:**

1. Make each package `__init__.py` export its sole supported service or
   cascade and no implementation details.
2. Keep typed domain conversion at the capability boundary; retain existing
   legacy calls behind that boundary instead of duplicating their logic.
3. Move a helper to `agents/shared/` only after at least two capability
   packages import it. Keep single-capability helpers beside their owner.
4. Place old import-path adapters in `agents/legacy/` when they must adapt
   request/response shapes; use direct re-exports when no adaptation is
   required.
5. Keep `app/agents` root limited to package exports and temporary
   compatibility files. It must not acquire new feature implementations.

**Result:** The capability folders are the canonical implementation locations;
cross-capability helpers and historic imports have explicit, separate homes.

## Task 3: Consolidate routing, retrieval, synthesis, and tool compatibility

**Files:**

- Canonicalize: `app/agents/router_agent.py`,
  `app/agents/enhanced_router_agent.py` into `app/agents/router/`
- Canonicalize: `app/agents/vector_rag_agent.py`,
  `app/agents/vector_rag_agent_unified.py`,
  `app/agents/enhanced_vector_rag_agent.py`, `app/agents/graph_rag_agent.py`,
  `app/agents/graph_rag_agent_enhanced.py`, and
  `app/agents/web_research_agent.py` into `app/agents/rag/`
- Canonicalize: `app/agents/react_agent.py` into `app/agents/tool/`
- Canonicalize: `app/agents/synthesis_agent.py` and
  `app/agents/synthesis_templates.py` into `app/agents/synthesizer/`
- Update backend callers: `app/pipeline/adapters.py`,
  `app/workflow/advanced_rag_workflow.py`, `app/graph/nodes/`,
  `app/graph/streaming/stream_processor.py`, and
  `app/api/utils/document_helpers.py`

**Work:**

1. Select one existing implementation for each of routing, vector retrieval,
   graph retrieval, web retrieval, tool/ReAct execution, synthesis, and
   template rendering. Do not merge algorithms or change result fields.
2. Relocate that implementation into the corresponding canonical capability
   package with a focused module name (`routing.py`, `vector.py`, `graph.py`,
   `web.py`, `react.py`, `service.py`, or `templates.py`).
3. Replace old flat files with narrow re-exports that preserve the existing
   imports used by workflows, graph nodes, scripts, and pipeline adapters.
4. Update production callers to import the canonical package path where this
   does not alter their runtime contract. Retain flat imports only where the
   compatibility record names a concrete outstanding consumer.
5. Remove a duplicate implementation only after its public functions are
   re-exported and its import audit is empty.

**Result:** Each Agent capability has one implementation; old flat names,
where necessary, are visibly compatibility-only.

## Task 4: Finalize the validation and shared-support boundaries

**Files:**

- Modify: `app/agents/answer_validator_agent.py`
- Modify: `app/agents/validation_cascade.py`
- Classify/move as warranted: `app/agents/fact_verification.py`,
  `app/agents/hallucination_patterns.py`, `app/agents/relevance_scoring.py`,
  `app/agents/result_schemas.py`, `app/agents/shared_cache.py`,
  `app/agents/shared_utils.py`, `app/agents/quality_*.py`, and
  `app/agents/route_*.py`
- Update backend callers in `app/api/main.py`, `app/pipeline/adapters.py`,
  `app/agents/answer_validator_batch.py`, and Agent/workflow modules only as
  required by the canonical import path

**Work:**

1. Keep `ValidationCascade` and its focused stages as the only validation
   implementation.
2. Reduce `answer_validator_agent.py` to public-result conversion and reduce
   `validation_cascade.py` to an import-compatible re-export.
3. Put validation-specific helpers next to `agents/validation/`; put only
   genuinely multi-capability primitives in `agents/shared/`.
4. Delete support modules classified as deletion candidates only when their
   import search is empty and the removal register records the evidence.

**Result:** Validation has no second engine, and Agent support code is either
owned, shared by evidence, or removed with an audit record.

## Task 5: Finish API, pipeline, and orchestration source separation

**Files:**

- Modify: `app/api/main.py`, `app/api/runtime.py`, and
  `app/api/dependencies.py`
- Modify: `app/api/routes/query.py`, `query_request.py`,
  `query_request_execution.py`, `query_response.py`, `query_stream.py`,
  `query_stream_cache.py`, `query_stream_execution.py`,
  `query_stream_transport.py`, `pipeline_compat.py`, and `orchestration.py`
- Modify: `app/api/utils/query_helpers.py`
- Modify: `app/pipeline/{__init__.py,adapters.py,capabilities.py,contracts.py,profiles.py,rag_pipeline.py}`
- Modify: `app/orchestration/{__init__.py,engine.py,event_publisher.py,execution_events.py,policies.py,request.py,shadow.py}`

**Work:**

1. Keep `main.py` limited to application construction, router registration,
   middleware, lifespan, and exception handlers.
2. Keep `query.py` limited to route assembly. Retain focused request, response,
   stream, cache, execution, and SSE transport modules as its collaborators.
3. Keep `RAGPipeline` responsible only for profile and public-contract
   translation plus delegation. Keep stage sequencing, events, budgets, and
   rollout seams in `OrchestrationEngine`.
4. Replace direct API-to-Agent/workflow construction with the existing
   pipeline boundary. Preserve `pipeline_compat.py` only as a documented
   request/response adapter for callers that still need it.
5. Remove obsolete route helpers or compatibility modules only after the same
   import-audit and removal-register process used for Agent modules.

**Result:** API is transport-only, pipeline is translation/delegation-only,
and orchestration is the sole stage-coordination owner.

## Task 6: Clean package exports and remove audited dead files

**Files:**

- Modify: `__init__.py` files under the changed backend packages
- Delete: only inventory-approved backend files and empty directories
- Modify: `config/refactor_cleanup_allowlist.json` and
  `docs/development/refactor-removal-register.md`

**Work:**

1. Remove stale exports that point to moved or deleted implementation modules.
2. Ensure every retained compatibility file has a concise module docstring
   naming its canonical replacement.
3. Delete only modules whose import audit is empty, whose replacement or
   retirement rationale is recorded, and whose deletion cannot remove a public
   route registration or package export.
4. Remove empty packages created by superseded files and update the removal
   register with the final file status.

**Result:** The backend tree contains only owned implementations, deliberate
shared primitives, and documented compatibility adapters.

## Task 7: Static completion review

**Files:** All backend files changed by Tasks 1–6.

**Work:**

1. Use `rg` to confirm that API routes do not directly instantiate an Agent or
   a legacy workflow and that moved symbols resolve from their canonical paths.
2. Run static Python import and formatting inspection on the changed backend
   modules only; correct issues in backend source only.
3. Re-run the import inventory and verify every retained old path has an owner
   and every removed path has recorded evidence.
4. Report the canonical packages, retained adapters, deleted files, and any
   deliberately deferred historical-debt modules.

**Result:** A clean backend ownership map with no test, CI, frontend, or
runtime feature work included in the refactor.

## 2026-08-09 implementation status

| Task | Status | Final factual outcome |
| --- | --- | --- |
| 1. Ownership inventory | Complete (scoped) | Root Agent/API candidates were classified. Retained root modules are explicit compatibility re-exports or documented request/result adapters with exact canonical owners; runtime imports were audited before deletion or canonicalization. |
| 2. Agent packages | Complete | `router`, `planner`, `rag`, `tool`, `synthesizer`, `validation`, `shared`, and `legacy` exist with the intended ownership boundaries. |
| 3. Capability canonicalization | Complete (scoped) | Routing, vector/graph/web RAG (including `EnhancedVectorRAGAgent`), ReAct, synthesis, and templates have one canonical implementation. Old flat paths are explicit re-exports or documented shape adapters. |
| 4. Validation/shared support | Complete (scoped) | `ValidationCascade` is the only validation engine; validation and shared support implementations have canonical owners in `validation`, `shared`, `router`, or `rag`. |
| 5. API/pipeline/orchestration | Complete (scoped) | API routes remain transport/assembly only. `RAGPipeline` only converts contracts and delegates; both non-stream and stream calls pass through `OrchestrationEngine` and `LegacyWorkflowCompatibilityExecutor`, which own existing sequencing and policy. |
| 6. Exports and audited deletion | Complete for approved candidates | Eight current `app/` deletions have recorded retirement rationale and import-audit evidence. Retained root compatibility paths remain deliberately documented rather than being broadly deleted. |
| 7. Static review | Complete (static scope only) | Sol findings on router paths/lazy exports/canonical imports, stream-engine boundaries/`answer_reset`, and enhanced-vector compatibility were corrected by Terra and re-reviewed as **ADDRESSED / PASS**. AST, targeted Ruff fatal/undefined-name, import-graph, import-boundary, and diff checks were used; no test or runtime feature result is asserted. |

### Final boundaries and deferred debt

- `app/api` owns HTTP/SSE transport, dependencies, runtime/app wiring, and
  route assembly. An import audit found no direct API import of an Agent or
  legacy workflow.
- `app/domain` owns contracts/errors/events; `app/pipeline` is the public
  profile and request/result translation/delegation boundary;
  `app/orchestration` owns existing execution coordination, events, policies,
  shadowing, and the compatibility executor.
- `app/mcp` owns MCP protocol governance (registry, authorization, approvals,
  gateway, audit); `app/services` owns infrastructure, connectors, and narrow
  legacy service facades, never execution sequencing.
- Historical root imports remain where audited callers (including scripts) or
  a public result-shape adapter require them. The two imports of
  `analyze_pdf_quality` and `extract_document_entities` from
  `scripts/benchmark_optimization.py` were already absent from
  `graph_rag_cache` before this work; they are recorded debt, not newly
  supported compatibility.
- The pre-existing parse typo in `app/ingestion/chunker_enhanced_clean.py`
  was corrected by Corrective Task J as the single-character-equivalent legal
  quote literal required to close the full-app AST gate; no ingestion behavior
  was redesigned.

- `answer_reset` follows the historical order: source scope, save the scoped
  answer, resynthesis, reset only when that answer changes, then conflict
  warning and terminal metadata. Warning decoration alone cannot cause reset.
- Connector, Orchestration, MCP, and newly present route modules, plus
  strict-quality retry, adaptive-routing, and model-selection behavior changes
  were already uncommitted work in the starting tree. They were preserved and
  deliberately excluded from this pure-refactor acceptance; this plan does
  not claim they were runtime-verified or accepted.

No tests were run. The scoped refactor and final inventory correction did not
edit tests, CI, frontend, dependencies, migrations, or deployment/release
files; existing user changes in those areas were preserved. No commit, push,
or PR was made.

## Final convergence execution addendum (approved 2026-08-09)

**Goal:** Remove the remaining root-level Agent business implementations and
make the API → Pipeline → Orchestration → canonical capability flow the only
supported backend execution architecture.

**Architecture:** Existing algorithms and public behavior are preserved by
moving implementations to one canonical owner and updating first-party
imports. Root paths may remain only as documented, logic-free external
compatibility adapters. Workflow code remains only when explicitly selected by
`app.orchestration.compatibility_executor`.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, Pydantic, Ruff, Python AST.

### Global constraints

- Use conda environment `rag-local` for Python commands.
- Do not modify or run `tests/`.
- Do not modify CI, frontend, dependencies, migrations, deployment, or release files.
- Do not change HTTP APIs, SSE event names/order/fields/status codes, MCP contracts, retrieval behavior, validation behavior, or model selection.
- Do not run `git reset`, `git checkout`, `git clean`, or any command that discards existing user changes.
- Before deleting any backend file, audit `app/` and `scripts/` with `rg`, record exact evidence, delete, and repeat the audit.
- All implementation edits are delegated to `gpt-5.6-terra` with high reasoning; each task receives a read-only `gpt-5.6-sol` high review and the branch receives a final Sol high review.

### Convergence Task A: Canonicalize shared Agent foundations

**Files:** `app/agents/base_agent.py`, `app/agents/unified_config.py`,
`app/agents/shared/`, `app/agents/rag/vector.py`, `config/`, and matching
first-party callers.

Move the still-used base-agent and vector configuration implementations to
canonical packages, update all `app/` and `scripts/` imports, and reduce the
old root files to documented adapters only when an external compatibility
constraint is proven. Preserve symbols, defaults, and lazy-loading behavior.

Static gate: AST parse changed files, targeted Ruff fatal/undefined-name
checks, and `rg` proving no canonical module imports the old root path.

### Convergence Task B: Move context tracking to its owning service boundary

**Files:** `app/agents/context_tracker_agent.py`,
`app/services/legacy_agent_runtime.py`, `app/pipeline/adapters.py`,
`app/agents/enhanced_rag_workflow.py`, and the selected canonical service
package.

Move the context store and cleanup lifecycle to a service-owned canonical
module, update callers, and retain only a narrow adapter if a real external
caller remains. Do not change context semantics or lifecycle behavior.

Static gate: import graph audit, AST parse, and targeted Ruff checks.

### Convergence Task C: Move degradation policy and the compatibility workflow

**Files:** `app/agents/degradation_strategies.py`,
`app/agents/enhanced_rag_workflow.py`,
`app/orchestration/compatibility_executor.py`, `app/workflow/`, and direct
first-party callers.

Move degradation policy to orchestration ownership and move the retained
strict-profile workflow under `app/workflow/`. The compatibility executor is
the only workflow caller. The old Agent root files must become adapters or be
deleted after audit. Preserve retry, circuit-breaker, answer-reset, and stream
terminal semantics.

Static gate: API/workflow direct-import audit, orchestration reverse-dependency
audit, AST parse, targeted Ruff checks, and `git diff --check`.

### Convergence Task D: Move Web Activity implementations to services

**Files:** `app/agents/web_activity_*.py`, `app/agents/rag/web.py`,
`app/services/legacy_web_activity.py`, and the selected
`app/services/web_activity/` canonical package.

Move Web Activity implementations to services, update all first-party imports,
and preserve the existing legacy facade only as request/result adaptation. No
RAG workflow or routing logic may be added to services.

Static gate: `rg` import audit before and after the move, AST parse, and
targeted Ruff checks.

### Convergence Task E: Delete audited dead implementations and close exports

**Files:** only audit-approved files under `app/agents/`, `app/api/`,
`app/services/`, plus package initializers, `config/refactor_cleanup_allowlist.json`,
and `docs/development/refactor-removal-register.md`.

Audit and delete uncalled root implementations such as `report_agent` when no
runtime caller exists. Remove stale exports and update the register with the
exact command, pre-delete result, replacement/retirement rationale, and
post-delete result. Do not delete a path with an unresolved runtime caller.

Static gate: repeated `rg` audit, allowlist inventory, AST parse, Ruff fatal
checks, and `git diff --check`.

### Convergence Task F: Final boundary and documentation review

**Files:** changed backend modules and the three refactor documents.

Verify that routes do not instantiate Agents or call workflows, Pipeline does
not own execution policy, Orchestration does not import API/Pipeline, services
do not own a second RAG workflow, and ValidationCascade is the sole validation
engine. Update the plan/spec/register only with evidence from this run.

Static gate: `conda run -n rag-local python` AST parse, `conda run -n rag-local ruff check --select E9,F63,F7,F82`, `git diff --check`, and all required `rg` audits. Tests remain unrun by explicit scope.

### Corrective Task G: Put standard request policy and stream entry in orchestration

**Files:** `app/pipeline/standard_request_policy.py`,
`app/pipeline/rag_pipeline.py`, `app/api/routes/query_stream.py`,
`app/api/routes/query_stream_execution.py`, `app/api/routes/query_request_execution.py`,
and the orchestration request/compatibility modules.

Move standard-profile business preparation behind the orchestration boundary.
The public routes may retain authentication, quota/cache/persistence concerns,
request normalization, and SSE mapping, but may not independently decide file
inventory/PDF targeting/smalltalk/retrieval strategy/Web/reasoning or return a
business answer before the pipeline-engine path. Preserve the existing sync and
stream event contracts, early-response payloads, cache behavior, and runtime
callbacks. Keep orchestration independent of API and pipeline imports.

Static gate: route-to-engine import/call audit, reverse-dependency audit,
AST parse of changed modules, and targeted Ruff fatal/undefined-name checks.

### Corrective Task H: Make ValidationCascade the sole public answer validator

**Files:** `app/agents/synthesizer/generation.py`,
`app/agents/validation/cascade.py`, `app/agents/validation/fact_verification.py`,
`app/agents/validation/public.py`, and exact canonical imports.

Remove the synthesizer's independent `FactVerifier` execution path. If its
fact-claim checks are still required for behavior compatibility, integrate them
as an internal cascade stage/helper owned and invoked by `ValidationCascade`;
do not create a second public validation engine. Preserve the existing
non-blocking behavior, result metadata, thresholds, and fallback semantics.

Static gate: validation call-graph audit proving the synthesizer reaches only
the cascade entry, AST parse, and targeted Ruff checks.

### Corrective Task I: Restore public compatibility and remove the unused strategy owner

**Files:** `app/agents/result_schemas.py`, `app/agents/shared_utils.py`,
`app/services/adaptive_strategy.py`, `config/refactor_cleanup_allowlist.json`,
`docs/development/refactor-removal-register.md`, and exact evidence notes.

Restore the two historically documented/tested modules as logic-free aliases to
canonical replacements, or create canonical replacements plus aliases if the
symbols have no existing owner. Before deleting `AdaptiveStrategyRouter`, audit
`app`, `scripts`, tests, and docs; delete only the uncalled duplicate strategy
implementation while preserving any genuinely used complexity helper. Reconcile
the deletion count/table and every stale ownership statement with fresh status
and import evidence.

Static gate: public compatibility audit, post-delete audit, allowlist JSON
validation, AST parse of changed backend modules, and `git diff --check`.

### Corrective Task J: Close static evidence and stale documentation

**Files:** `.superpowers/sdd/2026-08-09-backend-organization-refactor/`,
the three refactor documents, and only the pre-existing syntax defect in
`app/ingestion/chunker_enhanced_clean.py` if a behavior-preserving correction
is required by the final AST gate.

Record the initial forbidden-area status manifest, remove duplicate ledger
states, correct stale Task A-E/deletion-count claims, and re-run final static
audits. The chunker defect may be fixed only if it is demonstrably a pre-existing
parse typo and the correction does not expand into ingestion feature work.
Tests remain unrun.

### Corrective Task K: Preserve stream transport contracts at the final boundary

**Files:** `app/api/routes/query_stream.py`,
`app/api/routes/query_stream_execution.py`,
`app/api/routes/query_stream_transport.py`, `app/orchestration/`,
`app/pipeline/`, and exact boundary documentation.

Move construction of compatibility post-execution policy behind the
orchestration boundary; API may provide only transport/runtime callbacks and
request metadata. Restore the established stream contract at the versioned
boundary: original event types, `answer_reset`, complete `done.result`, field
values, and event order must pass through unchanged. Read overload state once
per execution and propagate that snapshot through the executor.

Static gate: compare the current serializer and stream path with the retained
HEAD contract, AST/Ruff checks, and a read-only event-shape/import audit. Tests
remain unrun.

### Corrective Task J fact record (2026-08-09)

The final deletion inventory is eight paths: `answer_validator_batch.py`,
`quality_logging.py`, `quality_thread_safety.py`, `report_agent.py`,
`auth.py.deprecated`, `reports.py`, `adaptive_strategy.py`, and
`optimized_rag_pipeline.py`. `result_schemas.py` and `shared_utils.py`
are retained logic-free compatibility re-exports to `agents.shared`, not
deleted paths. `report_agent.py` and `adaptive_strategy.py` are deleted;
their exact rationale and audits live in the removal register. The root
context adapter, workflow/degradation aliases, Web Activity aliases, and the
root validation module have their respective canonical owners listed there;
none is a second business implementation.

The forbidden-area baseline manifest and the permitted full-app AST/Ruff
results are recorded in `.superpowers/sdd/2026-08-09-backend-organization-refactor/`.
Tests remain unrun.
