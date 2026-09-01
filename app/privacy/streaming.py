"""Redact an answer while it is still being written.

`output_filter` is the last boundary before a user sees an answer, and it is
deliberately the one stage with no degraded path: skipping output DLP is a hole,
not a degradation. Streaming tokens straight to a browser is that same hole
spread over time -- the user sees the secret, and the redacted version arrives
afterwards.

So a stream is emitted only up to a point where redaction is *provably* the same
answer it would give on the finished text. Two properties make that possible:

1. **No pattern spans whitespace without a bound.** The credential patterns in
   `app/services/answer_safety.py` and `app/services/security/outbound_redaction.py`
   use `\\s{0,8}` rather than `\\s*` for exactly this reason. Their fixed parts
   ("Bearer", "-----BEGIN OPENSSH PRIVATE KEY-----", "api_key") are short.
2. **Everything unbounded is a single run of non-whitespace.** `\\S+`,
   `[A-Za-z0-9]{16,}`, URLs, paths, emails: a key may be any length, but it never
   contains a space.

Cutting at a whitespace character therefore never splits an unbounded match, and
holding back a fixed margin covers every bounded one. What is emitted has been
through the same redaction the final answer gets; what is held back is emitted on
the next chunk, or at the end.

Admin-configured CUSTOM terms are arbitrary text, so the margin grows to cover
the longest one rather than assuming it is short.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.privacy.text import OUTPUT_KINDS, inspect_text
from app.services.answer_safety import sanitize_answer

_WHITESPACE_RE = re.compile(r"\s")

BASE_SAFETY_MARGIN = 64
"""Covers the longest bounded whitespace-spanning pattern with room to spare.

The largest is `-----BEGIN OPENSSH PRIVATE KEY-----` at 35 characters;
`api_key` + two 8-character whitespace runs + a separator is 24.
"""


def _custom_term_margin() -> int:
    """How far back a configured CUSTOM term could reach.

    These are arbitrary strings from admin settings, so their length is a runtime
    fact rather than something this module can bound at import time.
    """
    try:
        from app.core.config import get_settings
        from app.services.security.outbound_redaction import _split_custom_entries

        raw = str(getattr(get_settings(), "outbound_redaction_custom_terms", "") or "")
        return max((len(term) for term in _split_custom_entries(raw)), default=0)
    except Exception:  # pragma: no cover - configuration must not break streaming
        return 0


def redact_final(text: str) -> str:
    """Apply the same two passes `filter_output` applies to an answer."""
    secret_safe, _report = sanitize_answer(str(text or ""))
    return inspect_text(secret_safe, kinds=OUTPUT_KINDS).text


@dataclass
class StreamingRedactor:
    """Emit redacted prefixes of a growing answer, never a partial match.

    ``push`` returns the newly safe text, which may be empty; ``finish`` returns
    whatever is left once no more is coming.
    """

    margin: int = field(default_factory=lambda: BASE_SAFETY_MARGIN + _custom_term_margin())
    _raw: str = ""
    _released: int = 0
    _emitted: str = ""

    def push(self, chunk: str) -> str:
        """Add generated text and return the part that is now safe to show."""
        self._raw += str(chunk or "")
        return self._release(self._safe_boundary())

    def finish(self) -> str:
        """Release the remainder; nothing further can change the match set."""
        return self._release(len(self._raw))

    @property
    def raw(self) -> str:
        """The unredacted text so far, for the caller's own final pass."""
        return self._raw

    def _release(self, boundary: int) -> str:
        if boundary <= self._released:
            return ""
        redacted = redact_final(self._raw[:boundary])
        if not redacted.startswith(self._emitted):
            # A match reached back into text already shown. The boundary rule is
            # meant to make this impossible; refusing to emit is the safe answer
            # if it ever is not, since the alternative is contradicting ourselves.
            return ""
        delta = redacted[len(self._emitted) :]
        self._released = boundary
        self._emitted = redacted
        return delta

    def _safe_boundary(self) -> int:
        """The latest whitespace whose redaction cannot still change.

        Two rules, and both are needed. Cutting at whitespace keeps the unbounded
        patterns whole, because none of them can contain a space. The stability
        check keeps the *bounded* whitespace-spanning ones whole: `password =
        hunter2` starts before a boundary and ends after it, so a margin measured
        from the end of the buffer does not protect it -- only comparing the
        prefix's redaction against the redaction of that prefix plus the margin
        does. Redacting more text may never change text already released.
        """
        limit = len(self._raw) - self.margin
        if limit <= 0:
            return 0
        for match in reversed(list(_WHITESPACE_RE.finditer(self._raw, 0, limit))):
            boundary = match.end()
            if boundary <= self._released:
                break
            settled = redact_final(self._raw[:boundary])
            if redact_final(self._raw[: boundary + self.margin]).startswith(settled):
                return boundary
        return self._released


__all__ = ["BASE_SAFETY_MARGIN", "StreamingRedactor", "redact_final"]
