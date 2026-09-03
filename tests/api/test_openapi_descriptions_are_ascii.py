"""Every description the OpenAPI document publishes is ASCII.

One router wrote its parameter descriptions in Chinese, and the bytes on disk
were the UTF-8 encoding of a latin-1 misreading of UTF-8 -- so the document
served ``å¼€å§‹æ—¥æœŸ`` where the author had typed ``开始日期``.  Nothing failed:
a mangled description is still a valid string, and only a reader of the docs
page would ever notice.

The other eighty-odd descriptions in ``app/api`` were already English, so this
pins the convention rather than imposing one, and it removes the only way that
particular corruption can happen again unseen.  Prose shown to *users* is
translated elsewhere (``app/agents/clarification/rules.py``); this rule is about
the developer-facing API document only.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_API = _REPO / "app" / "api"


def _descriptions(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "description":
                continue
            if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                found.append((keyword.value.lineno, keyword.value.value))
    return found


_SOURCES = [p for p in sorted(_API.rglob("*.py")) if "__pycache__" not in p.parts]


@pytest.mark.parametrize("path", _SOURCES, ids=lambda p: str(p.relative_to(_REPO)))
def test_api_descriptions_are_ascii(path: Path) -> None:
    offenders = [(line, text) for line, text in _descriptions(path) if not text.isascii()]
    assert not offenders, (
        f"{path.relative_to(_REPO)} publishes non-ASCII OpenAPI descriptions: {offenders}. "
        "Keep them ASCII -- a mis-encoded one reaches the docs page as mojibake and nothing fails."
    )
