import re

_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|PRIVATE) KEY-----"),
    re.compile(r"\b(?:password|passwd|token|secret)\s*[:=]\s*\S{4,}", flags=re.IGNORECASE),
]


def sanitize_answer(text: str) -> tuple[str, dict]:
    raw = str(text or "")
    redactions = 0
    sanitized = raw
    for p in _PATTERNS:
        sanitized, n = p.subn("[REDACTED]", sanitized)
        redactions += int(n)
    return sanitized, {"enabled": True, "redactions": redactions}
