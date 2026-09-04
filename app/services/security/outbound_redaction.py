from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.domain.text import normalize_string

logger = logging.getLogger(__name__)

EXTERNAL_PROVIDERS = {"openai", "anthropic", "deepseek", "custom"}
_STRUCTURAL_STRING_KEYS = {
    "role",
    "type",
    "media_type",
    "mime_type",
    "finish_reason",
    "tool_name",
    "tool_call_id",
    "id",
}
_BINARY_PAYLOAD_KEYS = {"data", "b64_json", "image", "images"}

_SECRET_PATTERNS = [
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_\-]{6,}\b"),
    # The whitespace runs are bounded, not `\s+`/`\s*`. An unbounded run means no
    # finite look-back can prove a match does not straddle a chunk boundary, which
    # is what app/privacy/streaming.py needs in order to redact a stream safely.
    # Eight is far past anything a real credential line contains.
    re.compile(r"\bBearer\s{1,8}[A-Za-z0-9._\-]{8,}\b", flags=re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|token|secret|password)\s{0,8}[:=]\s{0,8}\S+\b", flags=re.IGNORECASE),
]
_URL_RE = re.compile(r"https?://[^\s'\"<>]+", flags=re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b")
_WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:\\(?:[^\\\s]+\\)*[^\\\s]*")
_UNIX_PATH_RE = re.compile(r"/(?:[^/\s]+/)+[^/\s]+")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d()\-\s]{7,}\d)(?!\w)")

# An IPv6 address contains no whitespace, so app/privacy/streaming.py's second
# property covers it and BASE_SAFETY_MARGIN does not need to grow for its length.
_IPV6_RE = re.compile(
    r"(?<![:.\w])(?:"
    r"(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,7}:"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,5}(?::[0-9A-Fa-f]{1,4}){1,2}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,4}(?::[0-9A-Fa-f]{1,4}){1,3}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,3}(?::[0-9A-Fa-f]{1,4}){1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,2}(?::[0-9A-Fa-f]{1,4}){1,5}"
    r"|[0-9A-Fa-f]{1,4}:(?::[0-9A-Fa-f]{1,4}){1,6}"
    r"|::(?:[0-9A-Fa-f]{1,4}:){0,6}[0-9A-Fa-f]{1,4}"
    r")(?![:.\w])"
)

# China-specific identifiers. Until 2026-09-04 there were none, and the three
# most common ones were caught only by accident: an ID card, a bank card and a
# mainland mobile number are all long digit runs, so _PHONE_RE swallowed them
# and reported every one as a PHONE. Coverage was real; the label was wrong,
# which makes a privacy report describe something that did not happen. A
# passport number fell through entirely -- eight digits, one short of _PHONE_RE.
#
# These must stay ahead of _PHONE_RE in _BASE_PATTERNS: patterns are applied in
# order and the first to match owns the span, so the generic rule has to run
# last or it takes the specific ones' matches and mislabels them again.
_ID_CARD_CN_RE = re.compile(r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)")
# The boundary is non-alphanumeric, not merely non-digit. `(?!\d)` is satisfied by
# a letter, so this rule took the seventeen leading digits out of a credit code
# ending in its checksum letter (91110108551385095Q) and reported a bank card.
_BANK_CARD_RE = re.compile(r"(?<![A-Za-z0-9])\d{16,19}(?![A-Za-z0-9])")
_MOBILE_CN_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
# A letter plus eight digits is also the shape of an ordinary date-coded document
# id -- E20260904, H20250101 -- and an adversarial pass found exactly that, so the
# eight digits must not read as a date. The trade is deliberate and one-sided: a
# passport number whose digits happen to spell a recent calendar date is rare, and
# redacting every document reference of that shape corrupts text the model has to
# reason about.
_PASSPORT_CN_RE = re.compile(
    r"(?<![A-Za-z0-9])[EGDSPH](?!(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?![A-Za-z0-9]))\d{8}(?![A-Za-z0-9])"
)
# Unified social credit code: 18 characters from a checksum alphabet that omits
# I, O, Z, S and V, with the six-digit administrative division in the middle.
_USCC_RE = re.compile(r"(?<![A-Za-z0-9])[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}(?![A-Za-z0-9])")

_BASE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("SECRET", _SECRET_PATTERNS[2]),
    ("SECRET", _SECRET_PATTERNS[1]),
    ("SECRET", _SECRET_PATTERNS[0]),
    ("URL", _URL_RE),
    ("EMAIL", _EMAIL_RE),
    ("IP", _IPV4_RE),
    ("IP", _IPV6_RE),
    ("UUID", _UUID_RE),
    ("PATH", _WINDOWS_PATH_RE),
    ("PATH", _UNIX_PATH_RE),
    ("ID_CARD_CN", _ID_CARD_CN_RE),
    # BANK_CARD ahead of USCC_CN: the credit-code alphabet includes digits, so an
    # 18-digit order number matched USCC first and was reported as a company
    # registration. A real credit code carries letters in its organization part
    # and so is not touched by the digits-only rule above it.
    ("BANK_CARD", _BANK_CARD_RE),
    ("USCC_CN", _USCC_RE),
    ("MOBILE_CN", _MOBILE_CN_RE),
    ("PASSPORT_CN", _PASSPORT_CN_RE),
    ("PHONE", _PHONE_RE),
]


@dataclass
class _RedactionState:
    counters: dict[str, int] = field(default_factory=dict)
    replacements: dict[str, int] = field(default_factory=dict)
    seen: dict[tuple[str, str], str] = field(default_factory=dict)

    def token_for(self, kind: str, raw: str) -> str:
        value = str(raw or "").strip()
        if not value:
            return value
        self.replacements[kind] = int(self.replacements.get(kind, 0)) + 1
        key = (kind, _normalize_seen_value(kind, value))
        existing = self.seen.get(key)
        if existing:
            return existing
        next_index = int(self.counters.get(kind, 0)) + 1
        self.counters[kind] = next_index
        token = f"<{kind}_{next_index}>"
        self.seen[key] = token
        return token


def is_external_provider(provider: str) -> bool:
    return normalize_string(provider, lowercase=True) in EXTERNAL_PROVIDERS


def _normalize_seen_value(kind: str, value: str) -> str:
    normalized = str(value or "").strip()
    if kind in {"EMAIL", "URL", "IP", "UUID"}:
        return normalize_string(normalized, lowercase=True)
    return normalized


def outbound_redaction_enabled(*, for_embeddings: bool = False) -> bool:
    settings = get_settings()
    if for_embeddings:
        return bool(getattr(settings, "outbound_embedding_redaction_enabled", True))
    return bool(getattr(settings, "outbound_llm_redaction_enabled", True))


def _split_custom_entries(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r"[\r\n,;]+", str(raw or "")) if item.strip()]


@lru_cache(maxsize=16)
def _custom_patterns(custom_terms: str, custom_regexes: str) -> tuple[tuple[str, re.Pattern[str]], ...]:
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for term in sorted(_split_custom_entries(custom_terms), key=len, reverse=True):
        patterns.append(("CUSTOM", re.compile(re.escape(term), flags=re.IGNORECASE)))
    for expr in _split_custom_entries(custom_regexes):
        try:
            patterns.append(("CUSTOM", re.compile(expr, flags=re.IGNORECASE)))
        except re.error:
            logger.warning("Ignoring invalid outbound redaction regex: %s", expr[:120])
            continue
    return tuple(patterns)


def _active_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    settings = get_settings()
    return tuple(_BASE_PATTERNS) + _custom_patterns(
        str(getattr(settings, "outbound_redaction_custom_terms", "") or ""),
        str(getattr(settings, "outbound_redaction_custom_regexes", "") or ""),
    )


def _redact_text_with_state(
    text: str,
    state: _RedactionState,
    *,
    allowed_kinds: frozenset[str] | None = None,
) -> str:
    sanitized = str(text or "")
    for kind, pattern in _active_patterns():
        if allowed_kinds is not None and kind not in allowed_kinds:
            continue
        sanitized = pattern.sub(lambda m, k=kind: state.token_for(k, m.group(0)), sanitized)
    return sanitized


def redact_sensitive_text(
    text: str,
    *,
    allowed_kinds: frozenset[str] | None = None,
) -> tuple[str, dict[str, int]]:
    """Redact text deterministically and return safe aggregate counts.

    This provider-neutral entry point lets input, context, and output privacy
    services reuse the exact same patterns and stable tokenization as outbound
    provider redaction without exposing matched sensitive values.
    """

    state = _RedactionState()
    sanitized = _redact_text_with_state(str(text or ""), state, allowed_kinds=allowed_kinds)
    return sanitized, dict(sorted(state.replacements.items()))


def _should_passthrough_string(parent_key: str, value: str) -> bool:
    key = normalize_string(parent_key, lowercase=True)
    text = str(value or "")
    if not key:
        return False
    if key in _STRUCTURAL_STRING_KEYS:
        return True
    if key in _BINARY_PAYLOAD_KEYS:
        return True
    if key == "url" and text.startswith("data:"):
        return True
    return False


def redact_text_for_provider(text: str, *, provider: str, for_embeddings: bool = False) -> str:
    if not is_external_provider(provider) or not outbound_redaction_enabled(for_embeddings=for_embeddings):
        return str(text or "")
    return _redact_text_with_state(str(text or ""), _RedactionState())


def redact_texts_for_provider(texts: list[str], *, provider: str, for_embeddings: bool = False) -> list[str]:
    values = [str(item or "") for item in list(texts or [])]
    if not is_external_provider(provider) or not outbound_redaction_enabled(for_embeddings=for_embeddings):
        return values
    state = _RedactionState()
    return [_redact_text_with_state(item, state) for item in values]


def _redact_message_item(item: Any, state: _RedactionState, *, parent_key: str = ""):
    if isinstance(item, str):
        if _should_passthrough_string(parent_key, item):
            return item
        return _redact_text_with_state(item, state)
    if isinstance(item, tuple):
        if len(item) < 2:
            return item
        rebuilt = list(item)
        rebuilt[1] = _redact_message_item(rebuilt[1], state, parent_key="content")
        return tuple(rebuilt)
    if isinstance(item, list):
        return [_redact_message_item(value, state, parent_key=parent_key) for value in item]
    if isinstance(item, dict) and "content" in item:
        rebuilt = dict(item)
        for field_name, field_value in list(rebuilt.items()):
            rebuilt[field_name] = _redact_message_item(field_value, state, parent_key=str(field_name))
        return rebuilt
    if isinstance(item, dict):
        rebuilt = dict(item)
        for field_name, field_value in list(rebuilt.items()):
            rebuilt[field_name] = _redact_message_item(field_value, state, parent_key=str(field_name))
        return rebuilt
    return item


def redact_messages_for_provider(messages: Any, *, provider: str):
    if not is_external_provider(provider) or not outbound_redaction_enabled():
        return messages
    state = _RedactionState()
    if isinstance(messages, str):
        return _redact_text_with_state(messages, state)
    if isinstance(messages, tuple):
        return _redact_message_item(messages, state, parent_key="content")
    if isinstance(messages, dict):
        return _redact_message_item(messages, state, parent_key="content")
    if isinstance(messages, list):
        return [_redact_message_item(item, state, parent_key="content") for item in messages]
    return messages
