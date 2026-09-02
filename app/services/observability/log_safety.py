"""Helpers for referring to user content in logs without reproducing it."""

from __future__ import annotations

import hashlib

__all__ = ["question_ref"]


def question_ref(question: str | None) -> str:
    """A stable, non-reversible handle for a user's question.

    Logs used to carry the question itself, at INFO, on ordinary retrieval paths
    -- so anyone with log access read what every user asked, and truncating to
    the first 50 characters still reproduced the substance. The digest keeps the
    one property the logs actually needed: the same question produces the same
    handle, so a request can still be followed across lines and across services.

    Length is kept because it is useful for spotting empty or runaway inputs and
    reveals nothing on its own.
    """

    text = str(question or "")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"q[{digest} len={len(text)}]"
