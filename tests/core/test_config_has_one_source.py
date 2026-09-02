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

A direct `os.getenv` / `os.environ` read anywhere in `app/` must be in `ALLOWED`,
with a reason. The allowlist is keyed on `path::function` rather than a line
number: keying it on a line makes it fail on any edit *above* an exempt call,
which trains readers to re-point the entry instead of asking whether a real
escape appeared.

This began as a guard plus a ratchet, because `app/agents/shared/config.py`
reached the environment through four helper functions and the AST saw four call
sites rather than the 37 keys behind them. That block holds no environment reads
at all as of 2026-09-01 -- 20 of those constants had no reader anywhere and were
deleted, 13 became `Settings` fields, and the four scoring weights became plain
literals -- so the ratchet had nothing left to ratchet and went with it. A guard
that guards nothing is one more thing to read and no protection.
"""

from __future__ import annotations

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[2] / "app"

# `path::function` -> why this one is allowed to read the environment directly.
ALLOWED: dict[str, str] = {
    # These two choose *which* settings file to load, so they cannot live in it.
    "app/core/config.py::resolve_runtime_env_file": "selects the runtime env file",
    # The same chicken-and-egg one layer out: this bootstrap configures the
    # source that supplies Settings, so it cannot be supplied by it. It is also
    # why NACOS_PASSWORD stays in the environment and never becomes a field.
    "app/core/remote_config.py::_bootstrap": "bootstraps the configuration source itself",
    # A deployment pinning the local backend must beat persisted admin settings;
    # reading it from Settings would let the admin UI override the pin.
    "app/services/models/runtime.py::_local_backend_forced": "process-env pin over admin settings",
    # Diagnostics about the interpreter, not configuration of behaviour.
    "app/api/application/lifespan.py::lifespan": "conda environment diagnostics",
    "app/api/deps/admin.py::_runtime_diagnostics_summary": "conda environment diagnostics",
    "app/api/deps/auth.py::_resolve_pytest_header_user": "test-run detection",
}


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
