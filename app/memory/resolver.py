"""Deterministic long-term memory promotion and conflict resolution."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.core.config import Settings, get_settings
from app.domain.knowledge import MemoryItem
from app.privacy.text import INPUT_KINDS, inspect_text

MemoryKind = Literal["preference", "stable_fact", "task", "explicit_remember"]

_PROMOTION_RULES: tuple[tuple[MemoryKind, re.Pattern[str]], ...] = (
    ("explicit_remember", re.compile(r"(?:请|帮我)?记住|remember(?:\s+that)?", re.IGNORECASE)),
    (
        "preference",
        re.compile(
            r"我(?:现在|目前|更)?(?:喜欢|偏好|习惯)|i\s+(?:now\s+)?(?:prefer|like)|my\s+preference", re.IGNORECASE
        ),
    ),
    ("task", re.compile(r"提醒我|待办|需要完成|todo|remind\s+me", re.IGNORECASE)),
    ("stable_fact", re.compile(r"(?:^|[，,。.]\s*)我是|我的.{1,24}是|\bi\s+am\b|\bmy\s+.{1,24}\s+is\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class MemoryResolution:
    items: tuple[MemoryItem, ...]
    expired_count: int = 0
    duplicate_count: int = 0
    conflict_count: int = 0


class MemoryResolver:
    """Keep current explicit context ahead of older long-term memory."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def propose(
        self,
        question: str,
        *,
        source_session_id: str | None = None,
        now: datetime | None = None,
    ) -> MemoryItem | None:
        text = " ".join(str(question or "").split())
        if not text or not self._settings.long_term_memory_enabled:
            return None
        inspection = inspect_text(text, kinds=INPUT_KINDS)
        if inspection.findings:
            return None
        kind = _memory_kind(text)
        if kind is None:
            return None
        active_now = now or datetime.now(UTC)
        expires_at = _expiry(kind, active_now, self._settings)
        content = _memory_content(kind, text)
        return MemoryItem(
            memory_id=uuid.uuid4().hex,
            kind=kind,
            content=content,
            memory_key=_semantic_key(kind, content),
            updated_at=active_now.isoformat(),
            expires_at=expires_at.isoformat() if expires_at else None,
            source_session_id=source_session_id,
        )

    @staticmethod
    def normalize_item(item: MemoryItem) -> MemoryItem:
        if item.memory_key:
            return item
        return item.model_copy(update={"memory_key": _semantic_key(item.kind, item.content)})

    def resolve(
        self,
        current_context: tuple[MemoryItem, ...],
        long_term: tuple[MemoryItem, ...],
        *,
        now: datetime | None = None,
    ) -> MemoryResolution:
        active_now = now or datetime.now(UTC)
        current_ids = {item.memory_id for item in current_context}
        superseded = {item.supersedes for item in (*long_term, *current_context) if item.supersedes}
        winners: dict[str, MemoryItem] = {}
        expired_count = 0
        duplicate_count = 0
        conflict_count = 0
        for item in (*long_term, *current_context):
            item = self.normalize_item(item)
            if item.memory_id in superseded or _expired(item, active_now):
                expired_count += 1
                continue
            key = item.memory_key or _semantic_key(item.kind, item.content)
            existing = winners.get(key)
            if existing is None:
                winners[key] = item
                continue
            if _normalized(existing.content) == _normalized(item.content):
                duplicate_count += 1
            else:
                conflict_count += 1
            if item.memory_id in current_ids or (
                existing.memory_id not in current_ids and _updated_at(item) >= _updated_at(existing)
            ):
                winners[key] = item
        ordered = sorted(
            winners.values(),
            key=lambda item: (item.memory_id in current_ids, _updated_at(item)),
            reverse=True,
        )
        return MemoryResolution(
            items=tuple(ordered),
            expired_count=expired_count,
            duplicate_count=duplicate_count,
            conflict_count=conflict_count,
        )


def _memory_kind(text: str) -> MemoryKind | None:
    for kind, pattern in _PROMOTION_RULES:
        if pattern.search(text):
            return kind
    return None


def _memory_content(kind: MemoryKind, text: str) -> str:
    if kind == "explicit_remember":
        stripped = _PROMOTION_RULES[0][1].sub("", text, count=1).strip(" ：:,，")
        return stripped or text
    return text


def _semantic_key(kind: str, content: str) -> str:
    normalized = _normalized(content)
    key_kind = kind
    if kind == "explicit_remember":
        inferred = _memory_kind(normalized)
        if inferred and inferred != "explicit_remember":
            key_kind = inferred
    if key_kind == "preference":
        topic = _preference_topic(normalized)
        return f"preference:{topic}"
    subject = normalized
    for separator in ("是", "=", ":"):
        if separator in normalized:
            candidate = normalized.split(separator, 1)[0].strip()
            if 1 < len(candidate) <= 48:
                subject = candidate
                break
    digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:24]
    return f"{key_kind}:{digest}"


def _preference_topic(content: str) -> str:
    if re.search(r"语言|中文|英文|language|chinese|english", content, re.IGNORECASE):
        return "language"
    if re.search(r"格式|简洁|详细|列表|表格|markdown|format|concise|detailed", content, re.IGNORECASE):
        return "response_format"
    if re.search(r"颜色|主题|深色|浅色|蓝色|红色|color|theme|dark|light", content, re.IGNORECASE):
        return "theme"
    return "general"


def _expiry(kind: MemoryKind, now: datetime, settings: Settings) -> datetime | None:
    if kind == "task":
        return now + timedelta(days=settings.memory_task_ttl_days)
    if kind == "stable_fact":
        return now + timedelta(days=settings.memory_stable_fact_ttl_days)
    return None


def _expired(item: MemoryItem, now: datetime) -> bool:
    if not item.expires_at:
        return False
    try:
        expires = datetime.fromisoformat(item.expires_at)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return expires <= now
    except ValueError:
        return True


def _updated_at(item: MemoryItem) -> datetime:
    try:
        updated = datetime.fromisoformat(item.updated_at)
        return updated if updated.tzinfo else updated.replace(tzinfo=UTC)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


__all__ = ["MemoryResolution", "MemoryResolver"]
