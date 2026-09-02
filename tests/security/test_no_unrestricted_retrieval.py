"""No request path may search the vector store without a source filter.

`similarity_search(require_source_filter=False)` searches every user's corpus.
It exists for genuine system operations (index health, admin benchmarking).
Four request-path call sites used it before phase 1 of
docs/superpowers/plans/2026-08-29-user-data-isolation.md, so a user's top-k was
computed over everyone's documents and their own chunks could be crowded out
before the output-stage scope filter ever ran. All four are gone; this guard
keeps them gone.

The check is AST-based rather than a grep because two of those call sites passed
the flag positionally, through a thunk, where a grep for
`require_source_filter=False` finds nothing:

    loop.run_in_executor(pool, similarity_search, question, None, sources, False)
    asyncio.to_thread(similarity_search, query, top_k, allowed, False)

The second form was missed by the first version of this guard, which only knew
about `run_in_executor` -- the reason the baseline below started at three rather
than four.

Add a module to ALLOWED_UNRESTRICTED only for an operation that legitimately
spans all tenants, and say why.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

# module path -> why an unrestricted search is legitimate there
ALLOWED_UNRESTRICTED: dict[str, str] = {
    "app/evaluation/baselines/api_retriever.py": (
        "offline evaluation harness measuring retrieval quality over a fixed corpus; it has "
        "no request and no user, and comparing baselines is the whole point of the run"
    ),
}

# A ratchet: the count per module may go down, never up. Empty since phase 1
# (2026-08-30) removed the last of them, so any entry appearing here again is a
# regression rather than a baseline.
KNOWN_OFFENDERS: dict[str, int] = {}

# Positional index of require_source_filter in similarity_search's signature.
_REQUIRE_FILTER_POSITION = 3
_TARGET = "similarity_search"


def _python_sources() -> list[Path]:
    found: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk("app"):
        if "__pycache__" in dirpath:
            continue
        found.extend(Path(dirpath) / name for name in filenames if name.endswith(".py"))
    return found


def _is_false(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _called_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _unrestricted_invocations(tree: ast.AST) -> list[int]:
    """Line numbers where similarity_search is invoked with the filter disabled."""
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        name = _called_name(node)

        # Direct call: similarity_search(query, k, sources, False) / (..., require_source_filter=False)
        if name == _TARGET:
            positional = node.args[_REQUIRE_FILTER_POSITION : _REQUIRE_FILTER_POSITION + 1]
            keyword = [kw.value for kw in node.keywords if kw.arg == "require_source_filter"]
            if any(_is_false(value) for value in [*positional, *keyword]):
                hits.append(node.lineno)
            continue

        # Thunks, where the callable is an argument rather than the callee:
        #   run_in_executor(pool, similarity_search, query, k, sources, False)
        #   to_thread(similarity_search, query, k, sources, False)
        target_index = {"run_in_executor": 1, "to_thread": 0}.get(name)
        if target_index is None or len(node.args) <= target_index:
            continue
        target = node.args[target_index]
        if isinstance(target, ast.Name) and target.id == _TARGET:
            params = node.args[target_index + 1 :]
            if len(params) > _REQUIRE_FILTER_POSITION and _is_false(params[_REQUIRE_FILTER_POSITION]):
                hits.append(node.lineno)

    return hits


def _offenders_by_module() -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for path in _python_sources():
        key = path.as_posix()
        if key in ALLOWED_UNRESTRICTED or key == "app/retrievers/stores/vector.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        if lines := _unrestricted_invocations(tree):
            found[key] = lines
    return found


def test_no_new_unrestricted_vector_search_is_introduced():
    found = _offenders_by_module()
    regressions = {module: lines for module, lines in found.items() if len(lines) > KNOWN_OFFENDERS.get(module, 0)}

    assert not regressions, (
        "New call site(s) searching every user's documents: "
        f"{ {module: lines for module, lines in regressions.items()} }. "
        "Pass the caller's allowed_sources, or add the module to "
        "ALLOWED_UNRESTRICTED with a reason if it is a genuine system-wide operation."
    )


def test_the_known_offender_baseline_is_not_stale():
    """Shrinks the ratchet as P0-1 lands, and fails if an entry is already fixed."""
    found = _offenders_by_module()
    fixed = {module: expected for module, expected in KNOWN_OFFENDERS.items() if len(found.get(module, ())) < expected}

    assert not fixed, (
        f"{sorted(fixed)} no longer has as many unrestricted searches as "
        "KNOWN_OFFENDERS claims. Lower or delete the entry so the ratchet keeps holding."
    )


def test_no_exception_handler_recovers_with_an_unfiltered_search():
    """A retrieval error must fail, not silently widen to the whole corpus.

    `_safe_similarity_search` used to catch TypeError and retry without the
    filter. A TypeError there means the signature changed; degrading to a
    cross-tenant search is never the right recovery.
    """
    handlers: list[str] = []
    for path in _python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        handlers.extend(
            f"{path.as_posix()}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.ExceptHandler) and _unrestricted_invocations(node)
        )

    assert not handlers, (
        f"Exception handler(s) recovering with an unfiltered search: {sorted(handlers)}. "
        "Let the error propagate instead."
    )


# --- P1-4: every call site must also identify who is asking -----------------

# Positional index of `owner` in similarity_search's signature.
_OWNER_POSITION = 4

# Call sites that legitimately have no caller identity to pass, and why.
OWNERLESS_CALL_SITES: dict[str, str] = {
    "app/retrievers/hybrid/candidate_collection.py": (
        "legacy default for collect_candidates' vector_fn; the live path always injects "
        "retriever._safe_similarity_search, which is owner-bound via functools.partial"
    ),
    "app/evaluation/baselines/api_retriever.py": (
        "offline evaluation harness measuring retrieval quality over a fixed corpus; it has no request and no user"
    ),
}


def _invocations(tree: ast.AST) -> list[tuple[int, bool]]:
    """(line, passes_owner) for every similarity_search invocation."""
    found: list[tuple[int, bool]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _called_name(node)

        if name == _TARGET:
            has_owner = len(node.args) > _OWNER_POSITION or any(kw.arg == "owner" for kw in node.keywords)
            found.append((node.lineno, has_owner))
            continue

        target_index = {"run_in_executor": 1, "to_thread": 0}.get(name)
        if target_index is None or len(node.args) <= target_index:
            continue
        target = node.args[target_index]
        if isinstance(target, ast.Name) and target.id == _TARGET:
            params = node.args[target_index + 1 :]
            found.append((node.lineno, len(params) > _OWNER_POSITION))
    return found


def test_every_similarity_search_identifies_its_caller():
    """The owner clause is only worth having if no live path skips it.

    A guard that covers some retrieval paths and not others is worse than none:
    it reads as protection while leaving a way around. Anything that genuinely
    has no caller identity belongs in OWNERLESS_CALL_SITES with a reason.
    """
    missing: list[str] = []
    for path in _python_sources():
        key = path.as_posix()
        if key in OWNERLESS_CALL_SITES or key == "app/retrievers/stores/vector.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        missing.extend(f"{key}:{line}" for line, has_owner in _invocations(tree) if not has_owner)

    assert not missing, (
        f"similarity_search called without an owner at {sorted(missing)}. "
        "Pass OwnerScope.from_access_scope(scope), or add the module to "
        "OWNERLESS_CALL_SITES with a reason if it genuinely has no caller."
    )


def test_the_ownerless_allowlist_is_not_stale():
    """An allowlisted module that no longer calls similarity_search must be removed."""
    stale = []
    for key in OWNERLESS_CALL_SITES:
        path = Path(key)
        if not path.exists():
            stale.append(key)
            continue
        if not _invocations(ast.parse(path.read_text(encoding="utf-8", errors="ignore"))):
            stale.append(key)

    assert not stale, f"{stale} no longer calls similarity_search; drop the allowlist entry."


# --- P1-5: and it must not be able to lose the owner on the way there --------
#
# The check above only sees *direct* similarity_search calls, so it passed the
# whole time the graph route was reaching the store through
# `run_graph_rag -> _fallback_to_vector_rag -> run_vector_rag ->
# hybrid_search_with_diagnostics -> _safe_similarity_search`. Every hop wrote
# `owner=owner`, which satisfies an AST check, but `_fallback_to_vector_rag`
# declared `owner: OwnerScope | None = None` and two of its three callers relied
# on that default -- so the common fallback (Neo4j down, or an empty graph
# result) searched with the source filter alone and no ownership clause.
#
# The two guards below pin the shape of that bug rather than the one instance:
# an owner cannot be defaulted away, and it cannot be nulled without saying so.


def _is_none_default(node: ast.expr | None) -> bool:
    """True for an explicit `= None`; kw_defaults uses a bare None for "no default"."""
    return node is not None and isinstance(node, ast.Constant) and node.value is None


def _owner_parameters_defaulting_to_none(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        args = node.args
        positional = [*args.posonlyargs, *args.args]
        first_defaulted = len(positional) - len(args.defaults)
        for index, argument in enumerate(positional):
            if argument.arg == "owner" and index >= first_defaulted:
                if _is_none_default(args.defaults[index - first_defaulted]):
                    lines.append(node.lineno)
        for argument, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
            if argument.arg == "owner" and _is_none_default(default):
                lines.append(node.lineno)
    return lines


def _null_owner_arguments(tree: ast.AST) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "owner" and _is_none_default(keyword.value)
    ]


def test_no_retrieval_helper_defaults_its_owner_away():
    """A helper on the way to the store may not make the owner optional.

    `similarity_search` itself is exempt: it is the one place that decides what a
    missing owner means. Everywhere upstream, `owner` must be keyword-only with
    no default, so omitting it is a TypeError at the call site instead of a
    silently ownership-blind search.
    """
    offenders: list[str] = []
    for path in _python_sources():
        key = path.as_posix()
        if key == "app/retrievers/stores/vector.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        offenders.extend(f"{key}:{line}" for line in _owner_parameters_defaulting_to_none(tree))

    assert not offenders, (
        f"`owner` defaults to None at {sorted(offenders)}. Declare it keyword-only "
        "with no default (`*, owner: OwnerScope | None`) so a caller cannot drop it "
        "by omission."
    )


def test_no_module_passes_a_null_owner_without_saying_why():
    """Writing `owner=None` is allowed, but only somewhere the allowlist explains."""
    offenders: list[str] = []
    for path in _python_sources():
        key = path.as_posix()
        if key in OWNERLESS_CALL_SITES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        offenders.extend(f"{key}:{line}" for line in _null_owner_arguments(tree))

    assert not offenders, (
        f"`owner=None` passed at {sorted(offenders)}. Pass "
        "OwnerScope.from_access_scope(scope), or add the module to "
        "OWNERLESS_CALL_SITES with a reason if it genuinely has no caller."
    )
