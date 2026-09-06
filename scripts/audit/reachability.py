"""Which functions in app/ is nothing able to call?

Run from the repo root with the rag-local interpreter:

    python scripts/audit/reachability.py
    python scripts/audit/reachability.py --methods
    python scripts/audit/reachability.py --sonar issues.json

The question is the one that settled a `python:S3776` finding on 2026-09-06:
`UserManager.create_user` carried a cognitive complexity of 18 and nothing in the
repository called it, so the answer was `git rm`, not a refactor. Refactoring it
would have satisfied the rule and left the dead code standing. Asking that
question 89 times by hand is not practical; this asks it once.

With `--sonar`, the file is the JSON body of a SonarCloud issues query, and each
finding is reported with the reachability of the function it points at:

    curl -s 'https://sonarcloud.io/api/issues/search?componentKeys=pocheang_querymind
             &rules=python:S3776&ps=500&resolved=false' -o issues.json


How it decides
--------------
A name-based call graph over app/, scripts/ and deploy/. Every identifier a
function body mentions -- bare names, attribute names, and string constants that
are valid identifiers, so `getattr(obj, "method")` counts -- draws an edge to
*every* definition anywhere with that name. Roots are FastAPI-decorated handlers
and other framework entry points, dunders, the module-level code of every module
transitively imported from `app.api.main`, and each file under scripts/ and
deploy/, which are invoked directly.


What it is wrong about, which matters more
------------------------------------------
**It over-approximates, deliberately.** Sharing a name with something live makes
a function reachable here. That is the safe direction: UNREACHABLE is a strong
candidate, "reachable" is weak evidence. Nothing this prints is a verdict --
confirm each candidate with `git grep -w <name>` and by reading it before
deleting anything.

**It has been wrong in the expensive direction.** The first version resolved
`from .export import router` inside a package's `__init__.py` against the
package's *parent*, so `app/api/routes/sessions/` -- whose router IS registered
in `router_registry.py` -- dropped out of the import graph, and two live HTTP
endpoints were reported as dead (`import_session`, cognitive complexity 42, and
`SessionSearchService._match_metadata`, 31). Only hand-verification caught it.
Assume the same class of bug is still in here somewhere.

**Tests are not roots**, on purpose. A function only tests call is a third
answer, not a live one, and it is reported in its own section.

**Methods are excluded by default** (`--methods` includes them). A method is
reached through an instance whose type this analysis does not track, so the
false-positive rate on "unreachable method" is much higher than on a
module-level function. The `--sonar` cross-reference always covers both, because
a finding names whatever it names.

**It is not a CI gate and must not become one.** A check that over-approximates
and needs a human to confirm each hit would block a push on its own false
positives, which is how a check gets switched off. It always exits 0. The same
reasoning as `npm run screenshots` and the vector/hybrid retrieval numbers: some
things earn their keep as a tool you run and read, not as a condition.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRS = ("app", "scripts", "deploy")
ENTRY_MODULES = ("app.api.main", "app.main")

# Decorators that mean something outside this codebase does the calling.
ENTRY_DECORATORS = re.compile(
    r"\b(router|app|api|sub_?router)\.(get|post|put|patch|delete|head|options|websocket)\b"
    r"|\bon_event\b|\bapp\.middleware\b|\bexception_handler\b|\bvalidator\b|\bfield_validator\b"
    r"|\bmodel_validator\b|\bfixture\b|\bhookimpl\b|\bcontextmanager\b|\bproperty\b|\bsetter\b"
    r"|\bcached_property\b|\bstaticmethod\b|\bclassmethod\b|\boverload\b|\babstractmethod\b"
)


class Def:
    __slots__ = ("module", "qualname", "name", "lineno", "end_lineno", "cls", "refs", "is_entry")

    def __init__(self, module, qualname, name, lineno, end_lineno, cls, is_entry):
        self.module = module
        self.qualname = qualname
        self.name = name
        self.lineno = lineno
        self.end_lineno = end_lineno
        self.cls = cls
        self.is_entry = is_entry
        self.refs: set[str] = set()

    @property
    def key(self) -> tuple[str, str]:
        return (self.module, self.qualname)

    @property
    def lines(self) -> int:
        return (self.end_lineno or self.lineno) - self.lineno + 1


def source_files():
    for d in SOURCE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            if "__pycache__" in p.parts or ".venv" in p.parts:
                continue
            yield p


def module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def referenced_names(node: ast.AST) -> set[str]:
    """Every identifier a body mentions, including getattr/dispatch-table strings."""
    out: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            out.add(child.id)
        elif isinstance(child, ast.Attribute):
            out.add(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value.isidentifier():
            out.add(child.value)
    return out


def package_of(module: str, is_package: bool) -> str:
    """The package a relative import inside `module` resolves against.

    Inside a package's __init__.py that is the package itself, not its parent.
    Getting this wrong is what made app/api/routes/sessions/ look unmounted; see
    the module docstring.
    """
    if is_package or "." not in module:
        return module
    return module.rsplit(".", 1)[0]


def resolve_relative(pkg: str, level: int, module: str | None) -> str:
    """Where `from ..x import y` points, given the package it appears in.

    `level` is the number of leading dots: 1 is the package itself, so only the
    dots beyond the first walk upwards.
    """
    base = pkg
    for _ in range(level - 1):
        base = base.rsplit(".", 1)[0] if "." in base else ""
    return f"{base}.{module}" if module else base


def import_targets(node: ast.AST, pkg: str) -> set[str]:
    """The module paths one import statement names, plus `module.name` per alias.

    Both forms are emitted because a caller may name either: `from pkg.mod import
    Thing` makes the module live, and `Thing` is also the name a reader of the
    importing module will use.
    """
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names}
    if not isinstance(node, ast.ImportFrom):
        return set()

    target = resolve_relative(pkg, node.level, node.module) if node.level else (node.module or "")
    if not target:
        return set()
    return {target} | {f"{target}.{alias.name}" for alias in node.names}


def imports_of(tree: ast.AST, module: str, is_package: bool) -> set[str]:
    """Every module path this file imports, plus `module.name` for each name."""
    pkg = package_of(module, is_package)
    out: set[str] = set()
    for node in ast.walk(tree):
        out |= import_targets(node, pkg)
    return out


def collect(path: Path, module: str):
    """Every def in one module, and the names its module-level code mentions."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    defs: list[Def] = []
    module_level: set[str] = set()

    def walk(node, prefix, cls, at_import_time):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                decorators = [ast.unparse(d) for d in child.decorator_list]
                info = Def(
                    module,
                    f"{prefix}{child.name}",
                    child.name,
                    child.lineno,
                    child.end_lineno,
                    cls,
                    any(ENTRY_DECORATORS.search(d) for d in decorators),
                )
                info.refs = referenced_names(child)
                defs.append(info)
                # Descend to find nested defs, but a function's *body* does not run
                # at import: at_import_time goes false. It stayed true until
                # 2026-09-06, which made every name mentioned anywhere in the module
                # an import-time root -- so a helper called only from dead code
                # looked alive. `_source_mtime_ns` in api/deps/documents.py was
                # exactly that, and was found by reading rather than by this.
                walk(child, f"{prefix}{child.name}.", cls, False)
            elif isinstance(child, ast.ClassDef):
                # A class body does run at import, so it keeps the flag it was given.
                walk(child, f"{prefix}{child.name}.", child.name, at_import_time)
            elif not at_import_time:
                continue
            else:
                # Module- and class-level statements run at import, so the names
                # they mention are reachable from the moment the module loads.
                module_level.update(referenced_names(child))

    walk(tree, "", None, True)
    return defs, module_level, tree


class Graph:
    def __init__(self):
        self.defs: list[Def] = []
        self.by_name: dict[str, list[Def]] = defaultdict(list)
        self.by_module: dict[str, list[Def]] = defaultdict(list)
        self.module_level: dict[str, set[str]] = {}
        self.imports: dict[str, set[str]] = {}
        self.path_of: dict[str, Path] = {}
        self.live_modules: set[str] = set()
        self.reachable: set[tuple[str, str]] = set()
        self.test_names: set[str] = set()

    def build(self):
        for path in source_files():
            module = module_name(path)
            try:
                defs, module_level, tree = collect(path, module)
            except SyntaxError as exc:
                print(f"  SKIP (syntax) {path}: {exc}", file=sys.stderr)
                continue
            self.path_of[module] = path
            self.module_level[module] = module_level
            self.imports[module] = imports_of(tree, module, path.name == "__init__.py")
            for d in defs:
                self.defs.append(d)
                self.by_name[d.name].append(d)
                self.by_module[module].append(d)

        self._resolve_live_modules()
        self._resolve_reachable()
        self._collect_test_names()
        return self

    def _resolve_live_modules(self):
        entries = set(ENTRY_MODULES)
        # Anything under scripts/ or deploy/ is run directly, so it is its own root.
        entries |= {m for m in self.path_of if m.startswith(("scripts", "deploy"))}
        queue = deque(m for m in entries if m in self.path_of)
        while queue:
            module = queue.popleft()
            if module in self.live_modules:
                continue
            self.live_modules.add(module)
            for target in self.imports.get(module, ()):
                # "pkg.mod.Name" also names the module "pkg.mod".
                for candidate in (target, target.rsplit(".", 1)[0]):
                    if candidate in self.path_of and candidate not in self.live_modules:
                        queue.append(candidate)

    def _seed(self, d: Def, work: deque[Def]) -> None:
        """Mark one definition reached, and queue what it in turn mentions."""
        if d.key not in self.reachable:
            self.reachable.add(d.key)
            work.append(d)

    def _is_import_time_root(self, d: Def) -> bool:
        """Something outside the call graph reaches this the moment its module loads.

        A framework-decorated handler, a dunder the interpreter calls, or a name
        the module's own top level mentions -- an assignment, an `__all__`, a
        decorator argument.
        """
        if d.is_entry:
            return True
        if d.name.startswith("__") and d.name.endswith("__"):
            return True
        return d.name in self.module_level.get(d.module, ())

    def _names_live_modules_mention(self) -> set[str]:
        """Every name a live module names at import time, or imports by name."""
        named: set[str] = set()
        for module in self.live_modules:
            named |= self.module_level.get(module, set())
            named |= {target.rsplit(".", 1)[-1] for target in self.imports.get(module, ())}
        return named

    def _seed_roots(self, work: deque[Def]) -> None:
        for d in self.defs:
            if d.module in self.live_modules and self._is_import_time_root(d):
                self._seed(d, work)

        for name in self._names_live_modules_mention():
            for d in self.by_name.get(name, ()):
                if d.module in self.live_modules:
                    self._seed(d, work)

    def _propagate(self, work: deque[Def]) -> None:
        """Follow every name a reached definition mentions, until nothing is new."""
        while work:
            for name in work.popleft().refs:
                for target in self.by_name.get(name, ()):
                    if target.module in self.live_modules:
                        self._seed(target, work)

    def _resolve_reachable(self) -> None:
        work: deque[Def] = deque()
        self._seed_roots(work)
        self._propagate(work)

    def _collect_test_names(self):
        tests = ROOT / "tests"
        if not tests.exists():
            return
        for path in tests.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            self.test_names |= referenced_names(tree)

    def state(self, d: Def) -> str:
        if d.module not in self.live_modules:
            return "MODULE-NOT-IMPORTED"
        if d.key in self.reachable:
            return "reachable"
        if d.name in self.test_names:
            return "TEST-ONLY"
        return "UNREACHABLE"


def is_reportable(d: Def, include_methods: bool) -> bool:
    """Whether this definition belongs in the report at all.

    Methods are excluded by default: one is reached through an instance whose
    type this analysis does not track, so the false-positive rate on "unreachable
    method" is far higher than on a module-level function.
    """
    if not d.module.startswith("app"):
        return False
    if d.name.startswith("__"):
        return False
    return include_methods or not (d.cls or "." in d.qualname)


def dead_buckets(graph: Graph, include_methods: bool) -> dict[str, list[Def]]:
    """Reportable definitions grouped by the state that keeps them out of the call graph."""
    buckets: dict[str, list[Def]] = defaultdict(list)
    for d in graph.defs:
        if not is_reportable(d, include_methods):
            continue
        state = graph.state(d)
        if state != "reachable":
            buckets[state].append(d)
    return buckets


def print_bucket(state: str, found: list[Def]) -> None:
    """One state's definitions, heaviest module first, in line order within it."""
    print(f"\n=== {state}: {len(found)} in app/ ===")
    if not found:
        return

    by_module: dict[str, list[Def]] = defaultdict(list)
    for d in found:
        by_module[d.module].append(d)

    for module in sorted(by_module, key=lambda m: (-len(by_module[m]), m)):
        entries = sorted(by_module[module], key=lambda d: d.lineno)
        lines = sum(d.lines for d in entries)
        print(f"  {len(entries):>2} fn  {lines:>4} lines  {module}")
        for d in entries:
            print(f"          {d.qualname}  (line {d.lineno}, {d.lines} lines)")


def report_dead(graph: Graph, include_methods: bool) -> None:
    buckets = dead_buckets(graph, include_methods)
    for state in ("UNREACHABLE", "MODULE-NOT-IMPORTED", "TEST-ONLY"):
        print_bucket(state, buckets.get(state, []))

    total = sum(len(v) for v in buckets.values())
    print(f"\n{total} non-reachable definitions; confirm each with `git grep -w <name>` before deleting.")


def readable_file(path: Path) -> Path:
    """Resolve a path that came from the command line, before opening it.

    argv is untrusted as far as taint analysis is concerned
    (`pythonsecurity:S8707`), and this is a developer tool an agent may well run
    with arguments it constructed itself. Resolving symlinks and requiring an
    existing regular file is what makes the read a deliberate one rather than
    whatever the string happened to name.
    """
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from exc
    if not resolved.is_file():
        raise SystemExit(f"not a regular file: {resolved}")
    return resolved


def report_sonar(graph: Graph, sonar_path: Path) -> None:
    issues = json.loads(readable_file(sonar_path).read_text(encoding="utf-8")).get("issues", [])
    rows = []
    for issue in issues:
        rel = issue["component"].split(":", 1)[-1]
        line = issue.get("line")
        message = issue.get("message", "")
        match = re.search(r"from (\d+) to", message)
        severity = int(match.group(1)) if match else 0
        module = module_name(ROOT / rel)
        candidates = [d for d in graph.by_module.get(module, ()) if line and d.lineno <= line <= (d.end_lineno or 0)]
        if not candidates:
            rows.append((severity, "NO-DEF", rel, line, "?"))
            continue
        d = min(candidates, key=lambda x: x.lines)
        rows.append((severity, graph.state(d), rel, line, d.qualname))

    rows.sort(key=lambda r: (r[1] == "reachable", -r[0]))
    print(f"\n=== {len(rows)} findings from {sonar_path.name} ===")
    print(f"{'n':>5}  {'state':<20}  location")
    for severity, state, rel, line, qual in rows:
        print(f"{severity:>5}  {state:<20}  {rel}:{line} {qual}")
    counts = defaultdict(int)
    for row in rows:
        counts[row[1]] += 1
    print("\nsummary:", dict(counts))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--methods", action="store_true", help="include methods and nested defs (noisier)")
    parser.add_argument("--sonar", type=Path, help="SonarCloud issues JSON to cross-reference")
    args = parser.parse_args()

    graph = Graph().build()
    print(f"{len(graph.defs)} definitions in {len(graph.path_of)} modules; {len(graph.live_modules)} modules imported")

    if args.sonar:
        report_sonar(graph, args.sonar)
    else:
        report_dead(graph, args.methods)

    # Always 0: this over-approximates and needs a human. See the module docstring.
    return 0


if __name__ == "__main__":
    sys.exit(main())
