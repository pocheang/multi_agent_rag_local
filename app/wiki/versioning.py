"""Pure Wiki version helpers."""

from __future__ import annotations

import hashlib
from difflib import unified_diff


def wiki_content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def unified_content_diff(before: str, after: str, *, from_version: int, to_version: int) -> str:
    return "".join(
        unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"v{from_version}",
            tofile=f"v{to_version}",
        )
    )


__all__ = ["unified_content_diff", "wiki_content_hash"]
