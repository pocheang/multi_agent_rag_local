from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.domain.text import normalize_string
from app.core.config import get_settings

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
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{8,}\b", flags=re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S+\b", flags=re.IGNORECASE),
]
_URL_RE = re.compile(r"https?://[^\s'\"<>]+", flags=re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b")
_WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:\\(?:[^\\\s]+\\)*[^\\\s]*")
_UNIX_PATH_RE = re.compile(r"/(?:[^/\s]+/)+[^/\s]+")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d()\-\s]{7,}\d)(?!\w)")

_BASE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("SECRET", _SECRET_PATTERNS[2]),
    ("SECRET", _SECRET_PATTERNS[1]),
    ("SECRET", _SECRET_PATTERNS[0]),
    ("URL", _URL_RE),
    ("EMAIL", _EMAIL_RE),
    ("IP", _IPV4_RE),
    ("UUID", _UUID_RE),
    ("PATH", _WINDOWS_PATH_RE),
    ("PATH", _UNIX_PATH_RE),
    ("PHONE", _PHONE_RE),
]


@dataclass
class _RedactionState:
    counters: dict[str, int] = field(default_factory=dict)
    seen: dict[tuple[str, str], str] = field(default_factory=dict)

    def token_for(self, kind: str, raw: str) -> str:
        value = str(raw or "").strip()
        if not value:
            return value
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


def _redact_text_with_state(text: str, state: _RedactionState) -> str:
    sanitized = str(text or "")
    for kind, pattern in _active_patterns():
        sanitized = pattern.sub(lambda m, k=kind: state.token_for(k, m.group(0)), sanitized)
    return sanitized


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




