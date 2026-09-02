# Non-Agent Backend Organization Design

Date: 2026-08-10  
Status: Proposed execution baseline; implementation has not started.

## Purpose

Reorganize the Python backend outside `app/agents` and `app/prompts` into
clear capability and ownership boundaries without changing public runtime
behavior.

This work addresses physical source organization, canonical ownership,
dependency direction, compatibility exports, and removal governance. It does
not redesign the RAG algorithms, HTTP APIs, streaming protocol, model
selection, persistence semantics, or deployment model.

## Scope

Included:

- `app/api`
- `app/core`
- `app/domain`
- `app/graph`
- `app/ingestion`
- `app/retrievers`
- `app/services`
- `app/pipeline`
- `app/orchestration`
- `app/mcp`
- `app/evaluation`
- `app/tools`
- `app/workflow`
- `app/baselines`
- `app/models`
- Backend-owned references in `config`, `scripts`, and `docs`

Excluded:

- `app/agents` implementation organization
- `app/prompts` implementation organization
- Frontend source
- Product features or endpoint additions
- Retrieval, generation, validation, model, SSE, or database behavior changes
- Dependency, lock-file, migration, deployment, release, and CI redesign
- Git operations until separately authorized

Tests may be used later as verification when implementation is authorized,
but test changes are not part of the directory design itself.

## Current evidence

The 2026-08-10 static inventory found:

- 295 non-Agent/non-prompt backend Python modules.
- AST parsing passed for all 295 modules.
- Ruff `E9,F63,F7,F82` passed for the scoped backend.
- `app/services` contains 101 Python files, with 81 files directly at package
  root.
- `app/api/routes` contains 31 flat route and query-collaborator modules.
- `app/graph/streaming.py` conflicts with `app/graph/streaming/`.
- `app/ingestion/loaders.py` conflicts with `app/ingestion/loaders/`.
- `app/ingestion/loaders/__init__.py` dynamically reloads the sibling
  `loaders.py` through `spec_from_file_location`.
- `app/core/models.py` imports five modules from `app.services`, creating a
  bottom-layer reverse dependency.
- `app/core/schemas.py` primarily owns HTTP request/response models rather
  than core primitives.
- Two `EvaluationService` implementations and two baseline families exist
  with different contracts but ambiguous ownership.
- `app/core/optimized_config.py` has no external runtime consumer.
- `Settings.query_rewrite_max_variants` is declared twice.

This is an ownership and source-layout problem, not a syntax-repair project.

## Design principles

1. One canonical implementation per responsibility.
2. Move complete responsibilities, not arbitrary line ranges.
3. Preserve HTTP paths, methods, response models, exception mapping, SSE
   event names/order, public imports, configuration keys, and singleton
   behavior.
4. Routes are transport adapters. They validate input, apply authorization,
   call a supported service or pipeline boundary, and translate results.
5. `core` may not depend on `api`, `services`, `pipeline`, or
   `orchestration`.
6. `domain` owns stable contracts, domain errors, events, and text primitives.
7. `pipeline` translates public profiles/contracts and delegates.
8. `orchestration` is the only stage-sequencing owner.
9. Historical workflows may be called only through the documented
   compatibility executor.
10. Never create another same-stem `.py` file and package pair.
11. A moved public path leaves an import-only compatibility export until its
    retirement audit is complete.
12. No file is deleted based on naming alone.

## Target ownership model

```text
app/
├── api/
│   ├── main.py                    # stable uvicorn entry
│   ├── application/               # factory, lifespan, router registry, static serving
│   ├── deps/                      # dependency providers by capability
│   ├── schemas/                   # HTTP request/response models
│   ├── transport/                 # errors, responses, SSE, middleware
│   ├── query/
│   │   ├── request.py
│   │   ├── response.py
│   │   ├── execution.py
│   │   └── streaming/             # cache, execution, transport
│   └── routes/
│       ├── public/
│       ├── admin/
│       ├── operations/
│       └── compatibility/
├── core/                          # stable config/logging primitives only
├── domain/                        # contracts, errors, events, text
├── graph/
│   ├── knowledge/                 # Neo4j, Cypher validation, entity extraction
│   ├── execution/                 # graph state/workflow/studio entry
│   ├── nodes/
│   ├── routing/
│   └── streaming/                 # sole streaming owner
├── ingestion/
│   ├── chunking/
│   ├── loaders/                   # dispatch and file-type loaders
│   ├── extraction/
│   └── processing/
├── retrievers/
│   ├── stores/
│   ├── hybrid/
│   ├── query/
│   ├── lexical.py
│   └── reranking.py
├── services/
│   ├── auth/
│   ├── connectors/
│   ├── documents/
│   ├── query/
│   ├── retrieval/
│   ├── runtime/
│   ├── security/
│   ├── sessions/
│   ├── observability/
│   ├── language/
│   ├── models/
│   ├── web_activity/
│   └── legacy/                    # compatibility only
├── pipeline/                      # contracts, profiles, RAGPipeline
├── orchestration/
│   ├── core/
│   ├── events/
│   ├── rollout/
│   └── compatibility/
├── mcp/
│   ├── governance/
│   ├── connectors/
│   └── runtime/
├── evaluation/
│   ├── baselines/
│   ├── services/
│   ├── metrics.py
│   ├── models.py
│   └── data_loader.py
├── tools/
│   ├── graph/
│   └── web/
└── workflow/
    └── legacy/
```

The tree describes canonical owners. Temporary root compatibility modules may
remain beside these packages, but they must contain no business logic.

## Package boundaries

### API

- `main.py` remains the public `uvicorn app.api.main:app` entry.
- Application construction, lifespan, router registration, and static-file
  serving move under `api/application`.
- Query execution collaborators move out of `api/routes` into `api/query`.
- Route modules are grouped by public, admin, operational, and compatibility
  exposure.
- `api/dependencies.py` remains a compatibility facade while canonical
  providers move to `api/deps`.
- HTTP schemas move from `core/schemas.py` to `api/schemas` with compatibility
  exports at the old path.

### Core and domain

- `core` retains settings aggregation, logging setup, and true low-level
  primitives only.
- Provider/model runtime behavior moves from `core/models.py` to
  `services/models` because it depends on request context, model settings,
  security validation, and outbound redaction.
- Stable stage contracts and domain errors remain under `domain`.
- Configuration refactoring must preserve environment aliases and runtime
  defaults exactly.

### Graph

- `graph/knowledge` owns Neo4j, Cypher validation, and graph-oriented entity
  extraction.
- `graph/execution` owns LangGraph state/workflow construction and Studio
  entry.
- `graph/streaming` is the only streaming implementation package.
- The same-stem `graph/streaming.py` file is retired only after complete import
  and public-contract audit.

### Ingestion

- The canonical loader dispatcher becomes
  `ingestion/loaders/dispatch.py`.
- `loaders/__init__.py` becomes an explicit export facade and no longer loads
  a sibling file dynamically.
- Chunk classification, metadata enrichment, and splitting become separate
  complete responsibilities under `ingestion/chunking`.
- Generic `utils` modules move to extraction or processing owners.

### Retrieval and evaluation

- Store implementations move under `retrievers/stores`.
- `hybrid_retriever.py` becomes `retrievers/hybrid/retriever.py`; the old path
  is compatibility-only.
- Query expansion/rewrite integration belongs under `retrievers/query`, while
  request-level query policy remains in services/query.
- Both baseline families move under evaluation with names that expose their
  distinct contracts; algorithms are not merged merely because filenames are
  similar.
- Evaluation services receive explicit owners before any consolidation.

### Services

`services` is reorganized by capability, not by technical suffix. Root files
move in dependency order:

1. models, runtime, observability
2. documents, sessions, language
3. query, retrieval
4. security
5. legacy compatibility

Auth, connectors, and web activity retain their existing focused packages.
The service root should eventually contain only package exports and genuinely
cross-capability facades.

### Pipeline, orchestration, MCP, workflow

- Pipeline keeps contracts, profiles, and `RAGPipeline` as canonical owners.
- Orchestration is split internally into core, events, rollout, and
  compatibility while preserving its single sequencing authority.
- MCP separates governance, connectors, and runtime server adapters.
- Historical workflows move under `workflow/legacy` and remain reachable only
  through the compatibility executor.
- Existing compatibility imports remain until audited retirement conditions
  are satisfied.

## Compatibility and removal policy

For every moved module:

1. Audit `app`, `scripts`, `tests`, `docs`, and `config` for direct imports,
   dynamic imports, monkeypatch paths, package exports, and documented public
   commands.
2. Move the implementation to one canonical owner.
3. Update first-party production imports.
4. Keep the old module as import-only compatibility when any contract remains.
5. Record owner, replacement, caller evidence, and `remove_when` in
   `config/refactor_cleanup_allowlist.json` and
   `docs/development/refactor-removal-register.md`.
6. Delete only when the repeated audit is empty and no route registration or
   public package export depends on the path.

Compatibility modules may contain a module docstring, imports, aliases needed
for exact identity, and `__all__`. They may not contain a second algorithm,
registry, singleton, policy, or prompt/model configuration.

## Migration order

```text
ownership inventory
→ same-stem collision removal
→ core/domain/model runtime
→ graph/ingestion/retrievers/evaluation/tools
→ services capability packages
→ API application/routes/query internals
→ pipeline/orchestration/MCP/legacy workflow
→ exports, documentation, compatibility retirement
```

API is intentionally late in the sequence. Its downstream service and
infrastructure owners must be stable before route imports are moved.

## Verification contract

Each implementation wave must verify, at minimum:

- AST parsing of all `app` Python modules.
- Ruff `E9,F63,F7,F82` for the changed backend scope.
- New and historical public imports.
- Package export identity and singleton identity where applicable.
- Dynamic-import and monkeypatch target resolution.
- No new same-stem file/package pair.
- No forbidden dependency direction.
- No stale documentation paths.
- `git diff --check` when Git operations are later authorized.

Focused and full tests are implementation gates when authorized; this design
does not claim runtime verification.

## Completion criteria

The organization work is complete when:

- Every scoped module has a documented canonical owner.
- `services` root no longer contains unrelated business implementations.
- API routes are transport-only.
- Same-stem file/package conflicts and dynamic sibling-file loading are gone.
- `core` has no upward dependency.
- Graph knowledge infrastructure and execution graph code have separate
  owners.
- Evaluation services/baselines have explicit, non-ambiguous contracts.
- Pipeline and orchestration have no second execution owner.
- All retained compatibility modules have evidence and retirement conditions.
- Static and authorized runtime verification passes without contract changes.

