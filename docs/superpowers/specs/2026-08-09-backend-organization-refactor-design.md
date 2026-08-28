# Backend Organization Refactor Design

## Purpose

Normalize the existing backend source tree around clear ownership without
adding features or changing public runtime behavior. The work is limited to
Python backend modules, their package layout, compatibility imports, and
documentation required to explain those changes.

## Scope

Included:

- Organize backend modules by the responsibility they already own.
- Keep FastAPI transport, pipeline translation, orchestration, Agent
  capabilities, MCP infrastructure, and services in separate package
  boundaries.
- Replace duplicate compatibility implementations with import-only adapters
  where production callers still use historic paths.
- Remove a backend module only after a repository-wide import audit proves it
  has no runtime caller and its replacement is identified.
- Update the removal register with the owner, replacement, and removal
  condition for retained compatibility modules.

Excluded:

- New tests, test edits, CI changes, frontend changes, dependency changes,
  database migrations, and release automation.
- New endpoint, streaming, MCP, retrieval, validation, or model behavior.
- Deleting a compatibility path based only on naming or directory placement.

## Target ownership model

```text
app/
  api/             HTTP and SSE transport, route assembly, dependencies
  domain/          immutable contracts and domain errors
  pipeline/        public profile translation and execution delegation
  orchestration/   existing stage coordination, events, and rollout seams
  agents/
    router/        routing capability adapters
    planner/       planning capability adapters
    rag/           retrieval adapters and fusion
    tool/          tool-facing adapters
    synthesizer/   answer construction adapters
    validation/    sole validation implementation
    shared/        cross-capability primitives only when genuinely shared
    legacy/        temporary import/request-response compatibility adapters
  mcp/             registry, authorization, approvals, gateway, audit
  services/        persistence, connector, security, and telemetry services
```

`app/agents` package root may retain only exports and compatibility primitives
used by multiple capability packages. It must not gain new feature
implementations. Existing flat modules are classified before they are moved:
capability, shared primitive, legacy adapter, historical debt, or deletion
candidate.

## Refactor rules

1. Preserve public imports and runtime semantics. A moved module leaves a
   thin re-export at its former path while production imports remain.
2. Make one module responsible for one concern. Extract only a complete,
   existing responsibility; do not mix a file move with behavior redesign.
3. Routes remain transport-only. They may depend on pipeline contracts but do
   not instantiate Agents or workflows.
4. Pipeline remains a translation/delegation boundary. Orchestration owns
   existing execution sequencing. Neither boundary is redesigned in this
   refactor.
5. `agents/validation/` is the canonical validation implementation. Flat
   validation files may only delegate to it.
6. Before any deletion, run `rg` against the backend and scripts, record the
   evidence in the removal register, and retain the file if a runtime caller
   remains or ownership is unclear.
7. Do not change `tests/`, frontend files, CI/workflow configuration, package
   dependencies, or deployment configuration.

## Completion evidence

The refactor is complete when the changed backend files have clear ownership,
all retained compatibility paths are documented, all removed backend files
have import-audit evidence, and a static import/format inspection reports no
new backend import errors. Runtime, test, CI, frontend, and release checks are
outside this task's scope.

## 2026-08-09 implementation fact record

This records the implemented scoped organization work; it does not claim that
all historical backend debt has been removed.

- Canonical Agent implementations are under
  `app/agents/{router,planner,rag,tool,synthesizer,validation,shared,legacy}`.
  `legacy` is an adapter-only namespace; `shared` holds only cross-capability
  configuration, model, and cache primitives. The focused capability package
  initializers expose their public service/cascade boundaries (with lazy
  exports where importing the implementation is heavyweight).
- Relocated flat capability and support paths are explicit compatibility
  re-exports to their exact canonical symbols. `enhanced_vector_rag_agent.py`
  explicitly re-exports `app.agents.rag.enhanced_vector` plus the historic
  `app.agents.rag.vector.run_vector_rag` symbol; the root adapters
  that preserve a request/result shape are `enhanced_router_agent.py`,
  `vector_rag_agent.py`, and `answer_validator_agent.py`. None is a second
  routing, retrieval, or validation implementation. `validation_cascade.py`
  is an import-compatible re-export, and `ValidationCascade` is the sole
  validation engine.
- `app/api` owns FastAPI construction, HTTP/SSE transport, dependencies, and
  route assembly; routes do not directly import an Agent or legacy workflow.
  `app/domain` owns typed contracts/errors/events. `app/pipeline` owns public
  profile/request/result translation and delegation only. Both non-stream and
  stream `RAGPipeline` calls pass through `OrchestrationEngine` and its
  `LegacyWorkflowCompatibilityExecutor`; orchestration owns legacy profile
  choice, tool invocation, events, post-execution policy, terminal shaping,
  and existing execution sequencing.
- `app/mcp` owns registry, authorization, approvals, gateway, audit, and MCP
  contracts. `app/services` owns infrastructure, connectors, and the narrow
  legacy service facades used by API/runtime wiring; it does not own workflow
  sequencing.
- Eight current `app/` deletions have recorded retirement rationale and
  `app` plus `scripts` import-audit evidence, maintained in
  `docs/development/refactor-removal-register.md`.
- `result_schemas.py` and `shared_utils.py` remain documented, logic-free
  public re-exports to `app.agents.shared.result_schemas` and
  `app.agents.shared.utils`; they are not deletion candidates. `report_agent`
  and the unused duplicate `adaptive_strategy` implementation are deleted.
- Retained compatibility paths and deliberate debt are also recorded there,
  including the two missing `scripts/benchmark_optimization.py` graph-cache
  symbols that predate this refactor and are not a supported compatibility
  promise.
- Sol review initially found a router config-path regression, eager package
  exports, and one canonical module importing a legacy root. Terra corrected
  them; the follow-up Sol review was **ADDRESSED / PASS**. Static AST,
  targeted Ruff fatal/undefined-name, import-graph, and `git diff --check`
  inspections were performed; no test result is asserted.
- Stream terminal behavior preserves `HEAD:app/api/routes/query.py`:
  source-scope enforcement precedes saving the answer, `answer_reset` occurs
  only if resynthesis changes that scoped answer, and conflict-warning
  decoration does not independently emit a reset.
- The pre-existing `chunker_enhanced_clean.py` parse typo was corrected with
  the minimal legal quote literal needed for full-app static inspection. It is
  not an ingestion redesign.
- The starting tree already contained uncommitted Connector, Orchestration,
  MCP, and route work, together with strict-quality, adaptive-routing, and
  model-selection behavior changes. Those pre-existing feature behaviors were
  not attributed to or accepted by this refactor; orchestration boundary files
  were nevertheless edited to enforce the documented ownership model. This
  refactor does not assert runtime verification of the pre-existing feature
  changes.
- No tests were run. The scoped refactor and this fact correction did not edit
  tests, CI, frontend, dependencies, migrations, or deployment/release files;
  existing user changes there were preserved. No commit, push, or PR was made.
