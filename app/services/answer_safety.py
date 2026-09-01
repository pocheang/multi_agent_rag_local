import re

from app.core.config import get_settings

_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|PRIVATE) KEY-----"),
    # Bounded whitespace: see app/privacy/streaming.py for why an unbounded run
    # makes safe incremental redaction impossible.
    re.compile(r"\b(?:password|passwd|token|secret)\s{0,8}[:=]\s{0,8}\S{4,}", flags=re.IGNORECASE),
]


def sanitize_answer(text: str) -> tuple[str, dict]:
    """Redact credential-shaped strings from a finalized answer.

    Returns the sanitized text plus a report.  ``ANSWER_SAFETY_SCAN_ENABLED=false``
    disables the scan entirely; the report then says so rather than claiming a
    scan ran, which is what the previously hardcoded ``enabled: True`` did.

    This covers credentials only.  SSN / credit-card / email / phone patterns
    live on the separate validation-cascade path in
    ``app/agents/validation/rules.py``.
    """
    raw = str(text or "")
    if not bool(getattr(get_settings(), "answer_safety_scan_enabled", True)):
        return raw, {"enabled": False, "redactions": 0}

    redactions = 0
    sanitized = raw
    for pattern in _PATTERNS:
        sanitized, n = pattern.subn("[REDACTED]", sanitized)
        redactions += int(n)
    return sanitized, {"enabled": True, "redactions": redactions}
