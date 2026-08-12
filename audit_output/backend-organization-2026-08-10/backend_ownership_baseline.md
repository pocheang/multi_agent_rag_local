# Task 0 — non-Agent backend ownership baseline

Date: 2026-08-10  
Status: Complete for the ownership-inventory gate; no backend implementation
was moved, deleted, or behaviorally edited.

## Scope and starting-state handling

The scoped set is every Python file under `app/` except `app/agents/` and
`app/prompts/`. Related read-only evidence covers `scripts/`, `tests/`,
backend documentation, and `config/`. The requested forbidden areas were not
edited. Git status/diff was intentionally not queried because Git operations
and Git inspection were explicitly prohibited for this run; the filesystem
inventory and file-presence baseline are recorded instead.

Baseline counts:

- 295 scoped non-Agent backend Python modules.
- 422 Python modules under `app/` including Agent/prompt code.
- 101 Python files under `app/services/`, 81 directly at its package root.
- 31 Python files under `app/api/routes/` including its package initializer.
- AST parsing passed for all 295 scoped modules.
- Targeted Ruff `E9,F63,F7,F82` passed for the scoped backend.

`config/backend_ownership.json` is the machine-readable ownership map. It
contains one record for each of the 295 scoped paths with:

- module path and current owner;
- Task 0 classification (`capability`, `shared_primitive`,
  `compatibility`, `legacy_executor`, `historical_debt`, or
  `delete_candidate`);
- planned target owner and replacement where already evidenced;
- retirement condition and a link to this evidence report.

The map deliberately does not infer deletion from file size or naming. The
two collision files, the unconsumed optimized configuration, and the two
evaluation owner families are recorded as debt/candidates for later tasks,
not changed here.

## Read-only audit evidence

The following commands were run without changing files:

```text
rg --files app | Where-Object { $_ -match '\\.py$' -and $_ -notmatch '^app[\\/]agents[\\/]' -and $_ -notmatch '^app[\\/]prompts[\\/]' } | Sort-Object
```

Result: 295 paths.

```text
conda run -n rag-local python -c "...AST parse scoped app modules and assert len(backend_ownership['modules']) == 295..."
```

Result: `TASK0 AST/OWNER MAP OK: 295 modules`.

```text
conda run -n rag-local ruff check --select E9,F63,F7,F82 app/api app/core app/domain app/graph app/ingestion app/retrievers app/services app/pipeline app/orchestration app/mcp app/evaluation app/tools app/workflow app/baselines app/models
```

Result: `All checks passed!`.

### Public symbols, `__all__`, and package exports

The ownership map is path-complete. Public symbol and export review is a
read-only AST/source audit obligation attached to every module record and is
the gate for any later move. The audit dimensions are:

1. top-level public functions, classes, and exported constants;
2. literal `__all__` assignments;
3. package initializer exports and lazy/eager import behavior;
4. direct `app`/`scripts` imports and documented public paths;
5. test monkeypatch targets, which were inspected read-only and not changed.

No implementation move is authorized by this report until the owning Task
repeats the symbol/export audit for its exact move set. This preserves public
import identity and monkeypatch seams rather than treating the ownership map
as permission to delete a path.

Read-only summary counts from the scoped source scan: 1,941 public
function/class definition lines, 38 modules mentioning `__all__`, 72
first-party backend import lines in `scripts/`, and 159 API route registration
lines. Monkeypatch seams are retained as a required caller-audit dimension;
the tests were inspected read-only and not changed or run.

### HTTP, route, and SSE contract freeze

Route registration scanning covered decorators, `add_api_route`, and
`include_router` calls under `app/api`. It found 159 registration lines. The
application router registration order remains the sequence in
`app/api/main.py:265-285`; this is a frozen contract for later API work.

The existing SSE/streaming boundary remains owned by the current API/graph
transport and orchestration compatibility path. No event name, ordering,
payload, `answer_reset`, or terminal `done.result` field was changed in Task
0. The prior 2026-08-09 stream evidence remains authoritative and is linked
from the removal register.

### Dynamic imports and same-stem collisions

The dynamic-import scan:

```text
rg -n --glob '*.py' 'spec_from_file_location|import_module\\(|__import__\\(|find_spec\\(' app scripts config docs
```

recorded these relevant results:

- `app/ingestion/loaders/__init__.py` uses
  `spec_from_file_location` to load the sibling `app/ingestion/loaders.py`;
- `app/graph/streaming/safe_wrappers.py` uses `__import__` for a dynamic
  function lookup;
- historical Agent module-object aliases were observed but are outside this
  Task 0 inventory scope and remain governed by the 2026-08-09 SDD records.

The collision audit recorded:

- `app/graph/streaming.py` plus `app/graph/streaming/`;
- `app/ingestion/loaders.py` plus `app/ingestion/loaders/`.

These are Task 1 work items. No colliding path was removed in Task 0.

### Configuration and evaluation contracts

The baseline preserves the effective settings surface and records the known
duplicate `query_rewrite_max_variants` declaration in `app/core/config.py`.
`app/core/optimized_config.py` remains a deletion candidate only; no removal
decision was made.

The two `EvaluationService` families and both baseline families remain
distinct until their contracts and public callers are named. `app/baselines`
is mapped toward explicit evaluation baseline ownership, but no algorithm or
interface was merged.

## Compatibility and removal governance

The cleanup allowlist now records the non-Agent historical/deletion-sensitive
paths discovered by this baseline:

- `app/graph/streaming.py` → `app.graph.streaming`;
- `app/ingestion/loaders.py` → `app.ingestion.loaders.dispatch`;
- `app/core/optimized_config.py` → `app.core.config` or no replacement after
  an empty audit;
- both `EvaluationService` paths pending explicit contract ownership.

Each entry has an owner, replacement, and a concrete audit-based retirement
condition. The removal register records the same evidence and explicitly
states that no Task 0 deletion occurred.

## Task 0 acceptance

Accepted: all 295 scoped modules have an ownership record; the baseline
counts and contract-sensitive collision/config/evaluation findings are
captured; compatibility/deletion conditions are registered; AST and targeted
Ruff checks pass; no backend implementation move has started.

Read-only architecture review also passed ownership coverage (295/295), found
no direct Agent/workflow imports from `app/api/routes`, and found no
`app.api`/`app.pipeline` reverse import from `app/orchestration`. The known
loader dynamic import remains present and is correctly deferred to Task 1.

Not run by explicit user scope: tests, runtime checks, Git status/diff, and
all Git mutation operations.
