"""User questions must not be reproduced in logs.

Retrieval used to log the question itself at INFO on ordinary paths, so anyone
with log access read what every user asked. Truncating to the first 50
characters was no better -- it still reproduced the substance, and a question is
often the whole of what a user considers private about a session.

`question_ref` keeps the property the logs actually needed: the same question
yields the same handle, so a request stays followable across lines, without the
text. See P2-10 in
docs/superpowers/plans/2026-08-29-user-data-isolation.md.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from app.services.observability.log_safety import question_ref

# Names that hold user-supplied text. A logging call may not take one directly.
USER_TEXT_NAMES = frozenset({"question", "query", "answer", "content", "text", "prompt"})

_LOG_METHODS = frozenset({"debug", "info", "warning", "error", "exception", "critical"})

# Call sites that legitimately log one of these names, and why.
#
# Keyed on `path::enclosing_function`, not on a line number. Line numbers made
# this allowlist fail on any edit *above* the exempt call -- inserting a comment
# was enough -- which trains readers to re-point the entry rather than look at
# whether a real leak appeared.
ALLOWED_LOGGED_TEXT: dict[str, str] = {
    "app/evaluation/baselines/api_retriever.py::retrieve": (
        "offline evaluation harness; the query comes from a fixed eval dataset, "
        "not from a user, and seeing it is the point of the run"
    ),
}


def _python_sources() -> list[Path]:
    found: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk("app"):
        if "__pycache__" in dirpath:
            continue
        found.extend(Path(dirpath) / name for name in filenames if name.endswith(".py"))
    return found


def _is_logger_call(node: ast.Call) -> bool:
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in _LOG_METHODS:
        return False
    target = func.value
    return isinstance(target, ast.Name) and "log" in target.id.lower()


# Wrapping a name in one of these makes it safe to log.
SAFE_WRAPPERS = frozenset({"question_ref", "len", "bool", "type", "id", "sorted", "hash"})


def _leaked_names(node: ast.Call) -> set[str]:
    """User-text names passed to a logging call, directly or via an f-string.

    Does not descend into a safe wrapper: `question_ref(question)` mentions
    `question` but does not log it.
    """
    found: set[str] = set()

    def walk(expression: ast.AST) -> None:
        if isinstance(expression, ast.Call):
            callee = expression.func
            name = callee.id if isinstance(callee, ast.Name) else getattr(callee, "attr", "")
            if name in SAFE_WRAPPERS:
                return
        if isinstance(expression, ast.Name) and expression.id in USER_TEXT_NAMES:
            found.add(expression.id)
        # `question[:50]` reproduces the substance just as well.
        if isinstance(expression, ast.Subscript) and isinstance(expression.value, ast.Name):
            if expression.value.id in USER_TEXT_NAMES:
                found.add(expression.value.id)
        for child in ast.iter_child_nodes(expression):
            walk(child)

    for argument in [*node.args, *(kw.value for kw in node.keywords)]:
        walk(argument)
    return found


def _enclosing_functions(tree: ast.AST) -> dict[int, str]:
    """Map each node id to the function that contains it."""
    owner: dict[int, str] = {}

    def walk(node: ast.AST, current: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) else current
            owner[id(child)] = name
            walk(child, name)

    walk(tree, "<module>")
    return owner


def test_no_logging_call_passes_user_text():
    offenders: list[str] = []
    for path in _python_sources():
        key = path.as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        owner = _enclosing_functions(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_logger_call(node):
                continue
            leaked = _leaked_names(node)
            if leaked and f"{key}::{owner.get(id(node), '<module>')}" not in ALLOWED_LOGGED_TEXT:
                offenders.append(f"{key}:{node.lineno} -> {sorted(leaked)}")

    assert not offenders, (
        f"Logging calls carrying user text: {sorted(offenders)}. "
        "Wrap it in question_ref(), log a count or a category instead, or add "
        "`path::enclosing_function` to ALLOWED_LOGGED_TEXT with a reason."
    )


def test_the_allowlist_is_not_stale():
    """An entry must name a file and a function that still exist.

    A stale exemption is worse than none: it silently covers whatever ends up
    with that name later."""
    for key in ALLOWED_LOGGED_TEXT:
        path, separator, function = key.partition("::")
        assert separator, f"{key} must be path::enclosing_function"
        assert Path(path).exists(), f"{key} names a file that no longer exists"
        tree = ast.parse(Path(path).read_text(encoding="utf-8", errors="ignore"))
        defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)}
        assert function in defined, f"{key} names a function that no longer exists"


# --- the helper itself ------------------------------------------------------


def test_the_same_question_yields_the_same_handle():
    """Correlating a request across log lines is the property worth keeping.

    The two questions are built separately so they are distinct objects with
    equal content. Passing the same literal twice would also pass if the handle
    were keyed on identity or memoised per object, and neither of those survives
    the trip between processes that this property exists for.
    """
    asked = "what is my salary"
    asked_again = "".join(["what is my ", "salary"])  # joined, not concatenated: literals get folded

    assert asked is not asked_again, "the interpreter folded these; the test would prove less"
    assert question_ref(asked) == question_ref(asked_again)


def test_different_questions_yield_different_handles():
    assert question_ref("what is my salary") != question_ref("what is my bonus")


def test_the_handle_does_not_contain_the_question():
    secret = "acquisition of Northwind closes in March"
    handle = question_ref(secret)

    assert secret not in handle
    for word in secret.split():
        assert word not in handle


@pytest.mark.parametrize("value", ["", None])
def test_empty_input_is_handled(value):
    assert question_ref(value) == "q[e3b0c44298fc len=0]"


def test_length_is_reported():
    """Useful for spotting empty or runaway input; reveals nothing on its own."""
    assert "len=17" in question_ref("what is my salary")
