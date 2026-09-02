# Non-Agent Backend Organization Implementation Plan

> Execute task-by-task with a fresh working-tree baseline and review
> checkpoints. This plan does not authorize Git operations by itself.

**Goal:** Organize all Python backend code outside `app/agents` and
`app/prompts` into clear capability packages while preserving runtime
behavior, public imports, HTTP/SSE contracts, configuration semantics, and
compatibility paths.

**Architecture:** Leaf foundations and infrastructure are stabilized first,
services are then grouped by capability, API transport is moved only after its
downstream owners are stable, and Pipeline/Orchestration/MCP/legacy workflow
compatibility is closed last.

**Design:**
`docs/superpowers/specs/2026-08-10-non-agent-backend-organization-design.md`

**Audit source:**
`audit_output/backend-organization-2026-08-10/backend_organization_plan.md`

**Tech stack:** Python 3.11+, FastAPI, Pydantic, LangGraph, Neo4j, ChromaDB,
MCP, Ruff, Python AST.

## Global constraints

- Do not reorganize implementation code under `app/agents` or `app/prompts`.
- Do not change HTTP paths, methods, response models, SSE events/order,
  exception semantics, model selection, retrieval behavior, persistence, or
  workflow results.
- Do not edit frontend, dependencies, lock files, migrations, deployment,
  release, or CI files as part of this organization work.
- Preserve the dirty worktree and unrelated user changes.
- Do not use reset, checkout, clean, commit, push, or PR operations unless the
  user separately authorizes them.
- Use `conda run -n rag-local` for Python tooling.
- Use `apply_patch` for source/document edits.
- Do not delete a compatibility path without a full caller/export/dynamic-load
  audit and removal-register evidence.
- Never create a `.py` file and package directory with the same stem.
- Keep implementation changes and compatibility cleanup in separate steps.

## Task 0: Capture the non-Agent backend ownership baseline

**Inspect:**

- `app/api`, `core`, `domain`, `graph`, `ingestion`, `retrievers`, `services`
- `app/pipeline`, `orchestration`, `mcp`, `evaluation`, `tools`, `workflow`
- `app/baselines`, `models`
- Related `scripts`, `tests`, `docs`, and `config`

**Create or update:**

- `config/backend_ownership.json`
- `config/refactor_cleanup_allowlist.json`
- `docs/development/refactor-removal-register.md`
- A non-Agent backend inventory report under `audit_output/`

**Steps:**

1. Record the starting file status and preserve unrelated modifications.
2. Inventory every scoped module, public symbol, `__all__`, route
   registration, script import, dynamic import, monkeypatch path, and package
   export.
3. Classify each module as capability, shared primitive, compatibility,
   legacy executor, historical debt, or deletion candidate.
4. Record canonical owner, replacement, known callers, and retirement
   condition.
5. Freeze behavior-sensitive contracts: URLs, SSE events, schemas, settings,
   singleton identity, model/provider selection, and retrieval interfaces.

**Acceptance:** All 295 scoped modules have an owner; no move begins before
the ownership map is complete.

**Task 0 status (2026-08-10): Complete.** `config/backend_ownership.json`
records all 295 scoped modules with current/target owner, classification,
replacement, and retirement condition. The baseline report records the
read-only symbol/export/caller audit dimensions, route registration and
router-order freeze, dynamic-import and same-stem findings, settings and
evaluation ownership debt, and compatibility governance. Scoped AST parsing
and targeted Ruff `E9,F63,F7,F82` passed. No source move, deletion, test run,
or Git inspection/mutation was performed.

## Task 1: Remove same-stem collisions and certain orphan owners

### 1A. Ingestion loader collision

**Modify/create:**

- `app/ingestion/loaders/dispatch.py`
- `app/ingestion/loaders/__init__.py`
- Historical `app/ingestion/loaders.py` according to caller audit

**Steps:**

1. Move the current dispatcher implementation from `loaders.py` to
   `loaders/dispatch.py` without changing loader order, fallbacks, constants,
   aliases, or return values.
2. Replace `spec_from_file_location` loading with normal package imports.
3. Preserve monkeypatch/public seams through explicit delegates only where
   real callers require them.
4. Audit and retire the colliding file, or retain a non-colliding documented
   compatibility path.

### 1B. Graph streaming collision

**Modify:** `app/graph/streaming/**` and the historical
`app/graph/streaming.py` record.

**Steps:**

1. Confirm `app.graph.streaming` resolves to the package for every first-party
   caller.
2. Keep `streaming/__init__.py` as the supported export surface.
3. Remove the inaccessible same-stem file only after tests/docs/config audits
   and update the removal register.

### 1C. Configuration and evaluation owner audit

**Inspect:**

- `app/core/optimized_config.py`
- `app/core/config.py`
- `app/evaluation/service.py`
- `app/evaluation/services/evaluation_service.py`
- `app/baselines/**`
- `app/evaluation/baselines/**`

**Steps:**

1. Remove `optimized_config.py` only if the repeated full-scope audit remains
   empty.
2. Resolve the duplicate Settings field while preserving the currently
   effective default and alias.
3. Name and document both evaluation interfaces before deciding whether any
   implementation is redundant.
4. Classify both baseline families by contract instead of merging by filename.

**Acceptance:** No same-stem collision, no dynamic sibling-file loading, and
every evaluation/config owner is explicit.

**Task 1 status (2026-08-10): Complete.** The loader dispatcher is canonical
at `app.ingestion.loaders.dispatch`, the package facade preserves the existing
public/private seams without dynamic sibling loading, and the historical
`app/ingestion/loaders.py` path was removed after caller audit. The inaccessible
`app/graph/streaming.py` collision was removed while the package export surface
remained unchanged. The uncalled `app/core/optimized_config.py` candidate was
removed after pre/post audit, the effective Settings duplicate was reduced to
one declaration, and the two evaluation/baseline contracts were explicitly
named and kept distinct. AST/JSON and targeted Ruff checks passed; tests and
Git operations were not run.

## Task 2: Converge core, domain, schemas, and model runtime

### 2A. API schemas

**Create:**

- `app/api/schemas/auth.py`
- `app/api/schemas/query.py`
- `app/api/schemas/documents.py`
- `app/api/schemas/prompts.py`
- `app/api/schemas/admin.py`
- `app/api/schemas/models.py`
- `app/api/schemas/__init__.py`

**Modify:** `app/core/schemas.py` as compatibility export.

**Steps:** Move schema classes by HTTP capability without changing field
definitions, validators, defaults, serialization, or import names.

### 2B. Domain errors

**Modify/create:** focused files under `app/domain/errors/` or an equivalent
non-conflicting package name; keep `app/core/exceptions.py` as compatibility
surface until callers migrate.

**Steps:** Move only errors that are not transport-specific. HTTP conversion
remains in `api/transport`.

### 2C. Model runtime

**Create:** `app/services/models/{runtime,catalog,settings,redaction,security}.py`
as supported by the Task 0 map.

**Modify:** `app/core/models.py` to compatibility-only after production imports
move.

**Steps:** Separate local fallback models, provider adapters, cached factories,
request/global overrides, redaction wrappers, and cache clearing while
preserving factory signatures and cache identity.

**Acceptance:** `app/core` imports no `api`, `services`, `pipeline`, or
`orchestration`; old schema/model imports still resolve to exact canonical
objects.

**Task 2 status (2026-08-10): Complete within compatibility constraints.**
HTTP schemas are canonical under `app.api.schemas.http`, domain exceptions
under `app.domain.exceptions`, and model provider/runtime code under
`app.services.models.runtime`. Historic `app.core.schemas`,
`app.core.exceptions`, and `app.core.models` paths are module-object aliases;
non-Agent first-party callers were migrated to canonical owners while Agent
compatibility imports remain outside this task scope. Settings defaults and
aliases were preserved. AST, Ruff, JSON, and canonical/legacy object-identity
checks passed; tests and Git operations were not run.

## Task 3: Organize graph ownership

**Create/move:**

- `app/graph/knowledge/{client,cypher_validation,entity_extraction}.py`
- `app/graph/execution/{state,workflow,studio_entry}.py`
- Existing `nodes`, `routing`, and `streaming` packages as canonical owners

**Steps:**

1. Move Neo4j/Cypher/entity code under knowledge ownership.
2. Move state, workflow construction, and Studio entry under execution.
3. Keep graph nodes and routing focused; move cross-node policy to
   orchestration rather than duplicating it.
4. Preserve `app.graph.workflow`, `neo4j_client`, `entity_extraction`, and
   other real public imports through thin compatibility modules.
5. Split large modules only by complete responsibility: client lifecycle,
   query execution, schema operations, normalization, matching, and LLM
   extraction.

**Acceptance:** Knowledge graph infrastructure and LangGraph execution have
separate owners; orchestration policy is not duplicated.

**Task 3 status (2026-08-10): Complete.** Knowledge infrastructure is
canonical under `app.graph.knowledge`; graph state/workflow/Studio execution
is canonical under `app.graph.execution`; nodes and routing use canonical state
imports; and the six historical graph root modules are logic-free
module-object compatibility aliases. The compatibility executor remains the
only production historical-workflow caller. AST, Ruff, and canonical/legacy
identity checks passed; tests and Git operations were not run.

**Task 4 status (2026-08-10): Complete.** Ingestion chunking is canonical under
`app.ingestion.chunking` with classification, metadata, and splitter owners;
the historical enhanced chunker remains a logic-free facade. The former
`app.ingestion.utils` implementations now have canonical extraction and
processing owners, while historical utility modules and package exports retain
object-identity-compatible aliases. First-party loader and ingestion-service
callers use canonical paths. AST, targeted Ruff, and compatibility identity
checks passed; tests and Git operations were not run.

## Task 4: Organize ingestion ownership

**Create/move:**

- `app/ingestion/chunking/{classification,metadata,splitter}.py`
- `app/ingestion/extraction/{ocr,charts,tables,formulas,layout,people}.py`
- `app/ingestion/processing/{cleaning,structure,coreference,performance}.py`
- Canonical loader modules remain under `app/ingestion/loaders/`

**Steps:**

1. Split `chunker_enhanced_clean.py` by classification, metadata enrichment,
   scoring, and splitting responsibilities.
2. Replace the generic `utils` bucket with extraction/processing owners.
3. Keep loader fallback order, chart extraction count, OCR normalization,
   metadata, and supported extensions unchanged.
4. Move ingestion application services only when their persistence and queue
   dependencies have explicit owners.

**Acceptance:** No generic utility bucket owns business implementations; all
existing loader/chunker entry imports remain compatible.

## Task 5: Organize retrieval, evaluation, baselines, and tools

### Retrieval

**Create/move:**

- `app/retrievers/stores/{vector,corpus,parent}.py`
- `app/retrievers/hybrid/retriever.py`
- `app/retrievers/query/{expansion,rewrite,tuning}.py` where ownership audit
  supports it
- Focused lexical and reranking owners

**Steps:** Preserve vector/BM25/fusion/reranking order, cache keys, scoring,
top-k, parent expansion, and fallback behavior.

### Evaluation and baselines

**Steps:**

1. Move `app/baselines` implementations under explicit evaluation baseline
   namespaces.
2. Keep Chroma-object baselines distinct from runtime-global retriever
   baselines unless contract equivalence is proven.
3. Give the two evaluation service interfaces explicit module names and
   migrate CLI/API imports.
4. Keep old imports as re-exports until public scripts/tests move.

### Tools and advanced models

**Steps:**

1. Move graph tools/config under `app/tools/graph` and web search under
   `app/tools/web`.
2. Move `app/models/advanced_rag_models.py` to its evidence-backed domain or
   legacy-workflow contract owner; retain the old import surface.

**Acceptance:** Each retriever, evaluator, baseline contract, tool, and model
has one canonical owner.

**Task 5 status (2026-08-10): Complete.** Retriever storage has canonical
owners under `app.retrievers.stores`, and the hybrid executor is canonical under
`app.retrievers.hybrid.retriever`; historical retriever roots are logic-free
compatibility aliases. Chroma/object baselines now live under
`app.evaluation.baselines.chroma`, distinct from runtime-global evaluation
baselines. Graph/web tools have canonical `app.tools.graph` and
`app.tools.web` owners, and advanced RAG DTOs are canonical under
`app.domain.advanced_rag`. The two evaluation service contracts remain named
and separate. First-party non-Agent callers use canonical paths; Agent, test,
and documented historical imports remain compatible. AST, Ruff, and identity
checks passed; tests and Git operations were not run.

## Task 6: Split the services root by capability

Execute each subtask independently and finish its import/export audit before
starting the next.

### 6A. Models, runtime, and observability

- `services/models`: model catalog/config/runtime
- `services/runtime`: queues, bulkhead, circuit breaker, resilience, retry,
  runtime state, request context, caches
- `services/observability`: tracing, metrics, alerts, logs, execution tracking

### 6B. Documents, sessions, and language

- `services/documents`: registry, deduplication, index management/health
- `services/sessions`: history, memory, context, session language
- `services/language`: detection, analytics, tokenizer, Chinese processing

### 6C. Query and retrieval

- `services/query`: normalization, guard, intent, decomposition, rewrite,
  synonyms
- `services/retrieval`: profiles, logging, multi-query, evidence, citation,
  Self-RAG service integration

Keep rule-based rewrite generation and LLM query rewriting as separately named
owners unless behavior equivalence is proven.

### 6D. Security

- Admin security/rate limits/tokens
- RBAC/quota/rate limiting
- Network validation/outbound redaction
- Answer/prompt/PDF safety

### 6E. Legacy

- Move `legacy_*`, historical `auth_db`, and compatibility factories into
  `services/legacy` canonical adapters.
- Keep established root imports as import-only wrappers.

**Acceptance:** The services package root contains no unrelated business
implementation; every retained root file is a documented facade or
compatibility adapter.

**Task 6 status (2026-08-10): Complete.** Services now have canonical
`models`, `runtime`, `observability`, `documents`, `sessions`, `language`,
`query`, `retrieval`, and `security` subpackages. Root service modules retained
for public compatibility are logic-free aliases with allowlist entries and
retirement conditions. Rule-based and LLM query rewriting remain separate
owners. Non-Agent first-party imports were migrated; Agent/test/documented
legacy imports remain compatible. AST, Ruff, canonical/legacy identity, and
the sol high read-only architecture gate passed. Tests and Git operations were
not run.

## Task 7: Organize the API after service owners stabilize

### 7A. Application construction

**Create:**

- `app/api/application/factory.py`
- `app/api/application/lifespan.py`
- `app/api/application/router_registry.py`
- `app/api/application/static_files.py`

**Modify:** `app/api/main.py` to expose the stable `app` entry.

Preserve middleware order, lifespan initialization/cleanup, router order,
frontend fallback behavior, and compatibility attributes.

### 7B. Dependencies and transport

**Create:**

- `app/api/deps/{auth,query,documents,admin,runtime}.py`
- `app/api/transport/{errors,responses,sse,middleware}.py`

**Modify:** `dependencies.py`, `middleware.py`, and historical utils as
compatibility surfaces where callers require them.

### 7C. Query internals

**Create/move:**

- `app/api/query/request.py`
- `app/api/query/response.py`
- `app/api/query/execution.py`
- `app/api/query/streaming/{cache,execution,transport}.py`

`routes/query.py` remains route assembly only.

**Task 7 query checkpoint (2026-08-10): Complete.** Query request, response,
execution, and SSE cache/execution/transport implementations are canonical
under `app.api.query`; the historical route module paths are logic-free
compatibility aliases. `routes/query.py` and `routes/query_stream.py` retain
the route assembly and handler registration surfaces. AST, Ruff, import
identity, and sol high read-only route/SSE checks passed; Task 7E oversized
route extraction remains pending.

**Task 7B checkpoint (2026-08-10): Complete.** API error responses, response/SSE
helpers, and middleware are canonical under `app.api.transport`; historical
utility and middleware paths are logic-free compatibility aliases. Non-Agent
first-party imports use canonical transport paths. AST, Ruff, import identity,
and sol high read-only transport review passed. Task 7E oversized route
extraction remains pending.

**Task 7C checkpoint (2026-08-10): Complete.** API auth/query/documents/
sessions/admin/runtime dependency owners are canonical under `app.api.deps`;
historical utility/runtime paths are logic-free compatibility aliases, while
`app.api.dependencies` remains the public aggregation facade. Non-Agent
first-party imports use canonical deps/transport paths. AST, Ruff, import
identity, and sol high read-only dependency review passed. Task 7E oversized
route extraction remains pending.

**Task 7A checkpoint (2026-08-10): Complete.** Application construction is
canonical under `app.api.application`: `factory.py` preserves middleware
registration order, `lifespan.py` preserves startup/shutdown cleanup,
`router_registry.py` preserves the compatibility module sequence and all 21
router registrations, and `static_files.py` preserves mounts and frontend
fallback behavior. `app.api.main` remains the stable `app` entry and
compatibility facade. API AST/Ruff/route-order gates passed; the sol high
read-only application review passed after correcting static error detail
composition and extending the compatibility propagation bridge to application
owners. Task 7E oversized route extraction remains pending.

**Task 7D checkpoint (2026-08-10): Complete.** Canonical route owners now span
`app.api.routes.public`, `admin`, `operations`, and `compatibility` packages;
all 23 historical flat route modules are pure module-object compatibility
aliases. `app.api.application.router_registry` retains 21 routers and the
original registration order. The route audit expanded to 137 API routes with
zero duplicate `(method, URL)` pairs; AST, Ruff, identity, same-stem, dynamic
loader, and sol high read-only architecture gates passed. The duplicate
`POST /admin/ops/rollback` implementation was removed from `admin.ops`; the
canonical owner is `admin.settings`.

**Task 7E checkpoint (2026-08-10): Complete with one documented deferred
boundary.** The oversized route responsibilities were extracted across
`admin_ops`, `documents`, `auth`, and `admin_settings` into their existing
canonical service owners. Replay continues through the existing
`execute_standard_compatibility` → `RAGPipeline` → `OrchestrationEngine` path;
document upload/index operations preserve source binding, visibility, queue,
and freshness semantics; OAuth state retains TTL and one-time-consumption
semantics; and model/user settings call canonical model services. The route
handlers retain HTTP parsing, authorization, service/pipeline calls, audit,
and response conversion only.

Rollback retains the canonical owner `app.services.runtime.runtime_ops` and
the sole HTTP owner in `admin.settings`; the duplicate route was removed
during 7D. The settings reload handler remains intentionally deferred because
it mutates singleton globals held by `app.api.dependencies`. Moving that
mutation into a service would either add a forbidden services-to-API
dependency or change query/SSE runtime semantics. This is the only deferred
Task 7E boundary and is recorded in the removal register.

### 7D. Route grouping

Group route modules under public, admin, operations, and compatibility
packages. Preserve every route URL, method, tag, dependency, response model,
and registration order. Old module paths remain import-only wrappers when
needed.

### 7E. Oversized route extraction

- `admin_ops`: overview, benchmark, rollout, replay, logs
- `documents`: upload/storage, registry/index actions, health
- `auth`: local auth, profile/password, OAuth state/callback
- `admin_settings`: model settings, user API settings, reload/rollback

Business logic moves to its service owner; route handlers retain HTTP
translation only.

**Acceptance:** Routes contain no workflow/Agent construction and no business
policy; public HTTP/SSE behavior is unchanged.

## Task 8: Close Pipeline, Orchestration, MCP, and legacy Workflow boundaries

### Pipeline

Keep `contracts.py`, `profiles.py`, and `rag_pipeline.py` as supported owners.
Audit `adapters.py`, `capabilities.py`, `post_execution.py`,
`standard_request_policy.py`, and `tool_agent_factory.py` as compatibility
paths; do not duplicate their canonical implementations.

### Orchestration

Group engine/request/policies/degradation under core, execution events under
events, shadow/canary seams under rollout, and historical capability/executor
code under compatibility. Preserve one stage-sequencing owner.

### MCP

Group authorization/approvals/audit under governance; gateway/registry/server
under runtime; keep connector contracts focused. The MCP server may adapt to
Pipeline but may not implement a second execution policy.

### Workflow

Move enhanced and advanced historical workflows under `workflow/legacy`.
Only the orchestration compatibility executor may import their canonical
implementations. Preserve old workflow imports through wrappers until audit
retirement.

**Acceptance:** The supported dependency flow remains:

```text
API -> RAGPipeline -> OrchestrationEngine -> canonical capability/legacy executor
```

No reverse import into API/Pipeline and no second workflow selector exist.

**Task 8 status (2026-08-10): Complete by audit.** Existing Pipeline contracts,
profiles, and `RAGPipeline` remain the supported execution owners. The
orchestration engine/request/policy/event and compatibility boundaries remain
separate; MCP remains an adapter over Pipeline; historical workflows remain
behind the compatibility executor. The supported dependency-flow and reverse
import audits passed, and sol high read-only architecture review returned PASS.
No Task 8 production source move was necessary.

## Task 9: Package exports, compatibility retirement, and documentation

**Modify:**

- Scoped `__init__.py` files
- `config/backend_ownership.json`
- `config/refactor_cleanup_allowlist.json`
- `docs/development/refactor-removal-register.md`
- Backend architecture/development documentation
- Package README files

**Steps:**

1. Remove wildcard/eager package exports.
2. Expose only supported public boundaries.
3. Re-run caller audits for every deletion candidate.
4. Delete only candidates with empty audits and documented rationale.
5. Record all retained adapters and exact retirement conditions.
6. Update diagrams and examples to canonical paths while documenting public
   compatibility paths explicitly.

**Task 9 status (2026-08-10): Complete.** Canonical package boundaries,
compatibility aliases, allowlist retirement conditions, removal records, and
backend documentation examples were updated through the completed Task 8 and
Task 7 query checkpoints. No wildcard export redesign or public compatibility
path removal was performed. sol high read-only documentation/compatibility
review passed.

**Task 10 status (2026-08-10): Static migration closure complete.** Task 7E
oversized route extraction is complete with the documented settings-reload
deferred boundary. Final AST parsing covered 589 app modules; targeted Ruff,
route, canonical-owner, and reverse-import gates passed. Git checks were not
run because the user explicitly prohibited all Git commands. Tests were not
run, so runtime verification remains a separately authorized follow-up.

## Task 10: Verification and final read-only review

**Static commands:**

```powershell
conda run -n rag-local python -c "import ast; from pathlib import Path; files=list(Path('app').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p)) for p in files]; print(f'AST OK: {len(files)} app modules')"
conda run -n rag-local ruff check --select E9,F63,F7,F82 app
git diff --check
```

Run Git-related verification only after Git operations are authorized.

**Additional checks:**

- New and historical imports resolve.
- Compatibility modules contain no second implementation.
- No same-stem file/package pair exists.
- No dynamic sibling-file loading remains.
- `core` has no upward dependency.
- API routes do not instantiate Agent/workflow code.
- Orchestration does not import API/Pipeline.
- Every canonical implementation is unique.
- No stale backend documentation paths remain.
- No forbidden-scope files were changed by the task.

Focused/full tests and runtime checks are run only under the implementation
authorization and environment available at that time. Finish with a read-only
architecture review against the design document.

## Step-based completion order

Progress is measured only by completed, verified tasks—not elapsed time:

1. Complete Task 0 before changing ownership boundaries.
2. Complete Task 1 before moving foundational modules or public imports.
3. Complete Tasks 2–5 in their listed dependency order; begin Task 6 only
   when the shared foundation, graph, ingestion, and retrieval boundaries are
   stable.
4. Complete Task 6 before moving API route implementations in Task 7.
5. Complete Tasks 8–9 only after the canonical owners they depend on are
   established.
6. Run Task 10 after all migration tasks and before declaring the work closed.

Because the working tree already contains broad changes, migrate shared entry
files serially and close each task's compatibility and verification checklist
before starting the next dependent task.

## Post-Task-10 directory checkpoint (2026-08-11)

This is an additive status update; it does not reopen or regenerate the Task
0–10 plan. The requested directories were reviewed with Luna as implementer
and Sol as read-only reviewer:

- `app/services/auth`: completed; legacy JSON authentication remains a
  compatibility owner, while SQLite authentication remains uniquely owned by
  `auth_service.py`.
- `app/services/connectors`: completed and Sol-approved; only explicit package
  exports were added, with no mechanical split of management logic.
- `app/services/documents`: completed and Sol-approved after adding
  `OverflowError` handling for malformed persisted counters.
- `app/services/language`: completed and Sol-approved; the query preprocessor
  now points directly to the canonical synonyms package.

No tests or Git commands were run. Deferred issues and exact compatibility
conditions are recorded in `docs/development/refactor-removal-register.md`
and `audit_output/backend-organization-2026-08-10/backend_followup_audit.md`.
