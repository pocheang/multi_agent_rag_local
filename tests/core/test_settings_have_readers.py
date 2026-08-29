"""Every Settings field must have at least one reader.

The 2026-08-29 audit found 33 of 261 fields that no code read. Inert knobs are
worse than absent ones: an operator sets QUERY_RATE_LIMIT_ADMIN, sees no error,
and believes role-based rate limiting is on when no such feature exists.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

CONFIG_PATH = Path("app/core/config.py")

# Fields whose only consumer is outside app/ (e.g. a deploy-time script). Keep
# this list empty unless there is a genuine reason, and say what it is.
ALLOWED_WITHOUT_READERS: dict[str, str] = {}


def _settings_fields() -> list[str]:
    src = CONFIG_PATH.read_text(encoding="utf-8")
    return [
        st.target.id
        for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.ClassDef) and node.name == "Settings"
        for st in node.body
        if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name)
    ]


def _searchable_source() -> str:
    """All first-party source, with config.py's own field declarations stripped.

    A field declaring itself is not a reader; a property returning it is.
    """
    src = CONFIG_PATH.read_text(encoding="utf-8")
    chunks = [
        "\n".join(line for line in src.splitlines() if not re.match(r"\s*\w+\s*:\s*[\w\[\]| ]+\s*=\s*Field\(", line))
    ]
    for base in ("app", "tests"):
        for dirpath, _dirnames, filenames in os.walk(base):
            if "__pycache__" in dirpath:
                continue
            for filename in filenames:
                path = Path(dirpath) / filename
                if path.suffix == ".py" and path != CONFIG_PATH:
                    chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def test_no_settings_field_is_unread():
    blob = _searchable_source()
    unread = [
        field
        for field in _settings_fields()
        if field not in ALLOWED_WITHOUT_READERS and not re.search(rf"\b{re.escape(field)}\b", blob)
    ]
    assert not unread, (
        "Settings fields with no reader anywhere in app/ or tests/: "
        f"{unread}. Either wire them up or delete them; an inert setting "
        "misleads whoever configures it."
    )
