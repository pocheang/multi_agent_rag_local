"""Explicit Wiki update, diff, and rollback service."""

from __future__ import annotations

from app.wiki.models import WikiArticleVersion, WikiDiff, WikiSourceReference
from app.wiki.store import WikiStore


class WikiUpdater:
    def __init__(self, store: WikiStore | None = None) -> None:
        self._store = store or WikiStore()

    def update(
        self,
        *,
        tenant_id: str,
        title: str,
        content: str,
        source_references: tuple[WikiSourceReference, ...],
        slug: str | None = None,
        change_note: str = "manual_update",
    ) -> WikiArticleVersion:
        return self._store.upsert(
            tenant_id=tenant_id,
            title=title,
            content=content,
            source_references=source_references,
            slug=slug,
            change_note=change_note,
        )

    def diff(self, tenant_id: str, article_id: str, from_version: int, to_version: int) -> WikiDiff:
        return self._store.diff(tenant_id, article_id, from_version, to_version)

    def rollback(self, tenant_id: str, article_id: str, target_version: int) -> WikiArticleVersion:
        return self._store.rollback(tenant_id, article_id, target_version)


__all__ = ["WikiUpdater"]
