"""Configuration has one source, and it is `Settings`.

A value read with `os.getenv` is unreachable by the documented configuration
flow. `Settings` loads `.runtime/{APP_ENV}.env` through pydantic-settings, which
parses that file into the settings object **without exporting anything into the
process environment** -- so `make config-render` cannot set an `os.getenv` key,
and neither can a configuration centre pushing values into `Settings`. The only
way to set one is a real exported environment variable, present before the
module is imported.

That is how nine live switches ended up invisible to every configuration
surface, including `GET /api/advanced-rag/config`, which reported an
`ENABLE_QUERY_DECOMPOSITION` that nothing reads while the real switch
(`QUERY_DECOMPOSE_ENABLED`) defaulted to on. An admin page reporting something
other than the running configuration is worse than no page.

Two guards, because there are two shapes of the problem:

1. `test_no_module_reads_the_environment_directly` -- a direct `os.getenv` /
   `os.environ` read anywhere in `app/` must be in `ALLOWED`, with a reason. The
   allowlist is keyed on `path::function` rather than a line number: keying it on
   a line makes it fail on any edit *above* an exempt call, which trains readers
   to re-point the entry instead of asking whether a real escape appeared.

2. `test_the_legacy_constant_block_does_not_grow` -- `app/agents/shared/config.py`
   reaches the environment through four helpers, so the AST sees four call sites
   and not the 37 keys behind them. That block is a ratchet, in the shape this
   repository already uses for `KNOWN_OFFENDERS` and the frontend design scale:
   it may shrink, never grow.
"""

from __future__ import annotations

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[2] / "app"

# `path::function` -> why this one is allowed to read the environment directly.
ALLOWED: dict[str, str] = {
    # These two choose *which* settings file to load, so they cannot live in it.
    "app/core/config.py::resolve_runtime_env_file": "selects the runtime env file",
    # A deployment pinning the local backend must beat persisted admin settings;
    # reading it from Settings would let the admin UI override the pin.
    "app/services/models/runtime.py::_local_backend_forced": "process-env pin over admin settings",
    # Diagnostics about the interpreter, not configuration of behaviour.
    "app/api/application/lifespan.py::lifespan": "conda environment diagnostics",
    "app/api/deps/admin.py::_runtime_diagnostics_summary": "conda environment diagnostics",
    "app/api/deps/auth.py::_resolve_pytest_header_user": "test-run detection",
    # The legacy constant block; bounded by the ratchet below.
    "app/agents/shared/config.py::_get_bool_env": "legacy constant block (ratcheted)",
    "app/agents/shared/config.py::_get_float_env": "legacy constant block (ratcheted)",
    "app/agents/shared/config.py::_get_int_env": "legacy constant block (ratcheted)",
    "app/agents/shared/config.py::_get_str_env": "legacy constant block (ratcheted)",
}

# Frozen count of env-backed constants in the legacy block. May only go down.
LEGACY_CONSTANT_BUDGET = 37
LEGACY_BLOCK = APP / "agents" / "shared" / "config.py"


class _EnvReads(ast.NodeVisitor):
    """Collect `os.getenv(...)`, `os.environ.get(...)` and `os.environ[...]`."""

    def __init__(self, relative_path: str) -> None:
        self.path = relative_path
        self.scope: list[str] = []
        self.found: list[tuple[str, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def _record(self, node: ast.AST) -> None:
        where = self.scope[-1] if self.scope else "<module>"
        self.found.append((f"{self.path}::{where}", getattr(node, "lineno", 0)))

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute):
            value = func.value
            if isinstance(value, ast.Name) and value.id == "os" and func.attr == "getenv":
                self._record(node)
            elif (
                func.attr == "get"
                and isinstance(value, ast.Attribute)
                and value.attr == "environ"
                and isinstance(value.value, ast.Name)
                and value.value.id == "os"
            ):
                self._record(node)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        value = node.value
        # A write (`os.environ[k] = v`) is handled by visit_Assign's targets not
        # reaching here as a Load, so only reads are recorded.
        if (
            isinstance(value, ast.Attribute)
            and value.attr == "environ"
            and isinstance(value.value, ast.Name)
            and value.value.id == "os"
            and isinstance(node.ctx, ast.Load)
        ):
            self._record(node)
        self.generic_visit(node)


def _env_reads() -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for path in sorted(APP.rglob("*.py")):
        relative = path.relative_to(APP.parent).as_posix()
        visitor = _EnvReads(relative)
        visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
        found.extend(visitor.found)
    return found


def test_no_module_reads_the_environment_directly() -> None:
    """Every escape from `Settings` is declared, with a reason."""

    offenders = sorted({site for site, _ in _env_reads() if site not in ALLOWED})
    assert not offenders, (
        "These read the environment directly, so the render step and any configuration "
        "centre cannot set them:\n  " + "\n  ".join(offenders) + "\n"
        "Add a `Settings` field with the same alias and read it through `get_settings()`, "
        "or add an entry to ALLOWED saying why this one has to bypass Settings."
    )


def test_the_legacy_constant_block_does_not_grow() -> None:
    """`app/agents/shared/config.py` may shed env-backed constants, never gain them."""

    tree = ast.parse(LEGACY_BLOCK.read_text(encoding="utf-8"))
    helpers = {"_get_bool_env", "_get_float_env", "_get_int_env", "_get_str_env"}
    count = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in helpers
    )
    assert count <= LEGACY_CONSTANT_BUDGET, (
        f"{count} env-backed constants, budget {LEGACY_CONSTANT_BUDGET}. A new configuration "
        "value belongs in Settings, not in this block."
    )
    # A ratchet only holds if it is tightened as the block shrinks, so an
    # improvement that leaves the budget behind fails too.
    assert count == LEGACY_CONSTANT_BUDGET, (
        f"{count} constants remain, below the frozen {LEGACY_CONSTANT_BUDGET}. Lower LEGACY_CONSTANT_BUDGET to {count}."
    )
