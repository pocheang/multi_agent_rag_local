"""GBrain-compatible governed long-term memory provider."""

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path

from app.core.config import Settings, get_settings
from app.domain.knowledge import AccessScope, MemoryItem
from app.memory.resolver import MemoryResolver
from app.services.sessions.memory_store import (
    MemoryStore,
    memory_item_from_row,
    retrieve_relevant_long_term_memories,
)

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.@-]{1,128}$")


class GBrainLongTermMemory:
    """Provider-neutral facade using the existing owner-scoped local store."""

    def __init__(self, *, settings: Settings | None = None, base_root: Path | None = None) -> None:
        self._settings = settings or get_settings()
        self._base_root = base_root or self._settings.sessions_path
        self._resolver = MemoryResolver(self._settings)

    async def search(self, query: str, scope: AccessScope, top_k: int) -> tuple[MemoryItem, ...]:
        store = self._store(scope)
        rows = await asyncio.to_thread(store.list_global)
        items = tuple(item for row in rows if (item := memory_item_from_row(row)) is not None)
        current = self._resolver.propose(query)
        resolution = self._resolver.resolve((current,) if current else (), items)
        active_ids = {
            item.memory_id for item in resolution.items if current is None or item.memory_id != current.memory_id
        }
        eligible_rows = [row for row in rows if str(row.get("candidate_id")) in active_ids]
        selected = retrieve_relevant_long_term_memories(
            query,
            eligible_rows,
            top_k=max(1, top_k),
            fallback_k=min(2, max(1, top_k)),
        )
        return tuple(item for row in selected if (item := memory_item_from_row(row)) is not None)[: max(1, top_k)]

    async def upsert(self, item: MemoryItem, scope: AccessScope) -> MemoryItem:
        return await asyncio.to_thread(self._store(scope).upsert_memory, item)

    async def expire(self, memory_id: str, scope: AccessScope) -> bool:
        return await asyncio.to_thread(self._store(scope).expire_memory, memory_id)

    def _store(self, scope: AccessScope) -> MemoryStore:
        return MemoryStore(base_dir=memory_base_dir(self._base_root, tenant_id=scope.tenant_id, user_id=scope.user_id))


def memory_base_dir(base_root: Path, *, tenant_id: str, user_id: str) -> Path:
    owner = _segment(user_id)
    tenant = _segment(tenant_id)
    if tenant == owner:
        return base_root / owner / "_long_memory"
    return base_root / tenant / owner / "_long_memory"


def _segment(value: str) -> str:
    normalized = str(value or "").strip()
    if _SAFE_SEGMENT.fullmatch(normalized):
        return normalized
    return f"id-{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:24]}"


__all__ = ["GBrainLongTermMemory", "memory_base_dir"]
