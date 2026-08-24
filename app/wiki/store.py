"""Tenant-scoped Wiki persistence with immutable versions and source mappings."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings, get_settings
from app.domain.knowledge import AccessScope
from app.wiki.models import WikiArticleVersion, WikiDiff, WikiSourceReference, WikiVersionSummary
from app.wiki.versioning import unified_content_diff, wiki_content_hash

_SLUG_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
_TOKEN_RE = re.compile(r"[a-z0-9_-]{2,}|[\u4e00-\u9fff]", re.IGNORECASE)


class WikiStore:
    """Store derived knowledge separately from immutable original Evidence."""

    def __init__(self, db_path: Path | None = None, *, settings: Settings | None = None) -> None:
        active = settings or (Settings() if db_path is not None else get_settings())
        self.db_path = (db_path or active.wiki_db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._timeout = active.sqlite_busy_timeout_seconds
        self._scan_limit = active.wiki_scan_limit
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=self._timeout)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {int(self._timeout * 1000)}")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS wiki_articles (
                    tenant_id TEXT NOT NULL,
                    article_id TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    title TEXT NOT NULL,
                    current_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, article_id),
                    UNIQUE (tenant_id, slug)
                );
                CREATE TABLE IF NOT EXISTS wiki_versions (
                    tenant_id TEXT NOT NULL,
                    article_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    change_note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, article_id, version),
                    FOREIGN KEY (tenant_id, article_id)
                        REFERENCES wiki_articles(tenant_id, article_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS wiki_source_mappings (
                    tenant_id TEXT NOT NULL,
                    article_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    ordinal INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    document_version INTEGER NOT NULL,
                    page INTEGER,
                    chunk_id TEXT,
                    image_id TEXT,
                    acl_tags_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, article_id, version, ordinal),
                    FOREIGN KEY (tenant_id, article_id, version)
                        REFERENCES wiki_versions(tenant_id, article_id, version) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_wiki_articles_current
                    ON wiki_articles(tenant_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_wiki_sources_document
                    ON wiki_source_mappings(tenant_id, document_id, document_version);
                """
            )

    def upsert(
        self,
        *,
        tenant_id: str,
        title: str,
        content: str,
        source_references: tuple[WikiSourceReference, ...],
        slug: str | None = None,
        change_note: str = "update",
    ) -> WikiArticleVersion:
        tenant = _required(tenant_id, "tenant_id")
        normalized_title = _required(title, "title")
        normalized_content = _required(content, "content")
        references = _unique_references(source_references)
        if not references:
            raise ValueError("Wiki versions require at least one original source reference")
        normalized_slug = _slug(slug or normalized_title)
        note = _required(change_note, "change_note")
        digest = wiki_content_hash(normalized_content)
        now = datetime.now(UTC).isoformat()

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            article = connection.execute(
                "SELECT article_id, current_version FROM wiki_articles WHERE tenant_id=? AND slug=?",
                (tenant, normalized_slug),
            ).fetchone()
            if article is None:
                article_id = uuid.uuid4().hex
                version = 1
                connection.execute(
                    """
                    INSERT INTO wiki_articles(
                        tenant_id, article_id, slug, title, current_version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (tenant, article_id, normalized_slug, normalized_title, version, now, now),
                )
            else:
                article_id = str(article["article_id"])
                current = self._load_version(connection, tenant, article_id, int(article["current_version"]))
                if current.content_hash == digest and current.source_references == references:
                    return current
                version = int(article["current_version"]) + 1

            connection.execute(
                """
                INSERT INTO wiki_versions(
                    tenant_id, article_id, version, title, content, content_hash, change_note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (tenant, article_id, version, normalized_title, normalized_content, digest, note, now),
            )
            for ordinal, reference in enumerate(references):
                connection.execute(
                    """
                    INSERT INTO wiki_source_mappings(
                        tenant_id, article_id, version, ordinal, source, document_id,
                        document_version, page, chunk_id, image_id, acl_tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tenant,
                        article_id,
                        version,
                        ordinal,
                        reference.source,
                        reference.document_id,
                        reference.document_version,
                        reference.page,
                        reference.chunk_id,
                        reference.image_id,
                        json.dumps(sorted(reference.acl_tags), ensure_ascii=False),
                    ),
                )
            connection.execute(
                """
                UPDATE wiki_articles
                SET title=?, current_version=?, updated_at=?
                WHERE tenant_id=? AND article_id=?
                """,
                (normalized_title, version, now, tenant, article_id),
            )
            return self._load_version(connection, tenant, article_id, version)

    def get_current(self, tenant_id: str, article_id: str) -> WikiArticleVersion | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT current_version FROM wiki_articles WHERE tenant_id=? AND article_id=?",
                (tenant_id, article_id),
            ).fetchone()
            return self._load_version(connection, tenant_id, article_id, int(row["current_version"])) if row else None

    def get_version(self, tenant_id: str, article_id: str, version: int) -> WikiArticleVersion | None:
        with self._connect() as connection:
            try:
                return self._load_version(connection, tenant_id, article_id, version)
            except KeyError:
                return None

    def list_versions(self, tenant_id: str, article_id: str) -> tuple[WikiVersionSummary, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT article_id, version, title, content_hash, change_note, created_at
                FROM wiki_versions WHERE tenant_id=? AND article_id=? ORDER BY version DESC
                """,
                (tenant_id, article_id),
            ).fetchall()
        return tuple(WikiVersionSummary.model_validate(dict(row)) for row in rows)

    def diff(self, tenant_id: str, article_id: str, from_version: int, to_version: int) -> WikiDiff:
        before = self.get_version(tenant_id, article_id, from_version)
        after = self.get_version(tenant_id, article_id, to_version)
        if before is None or after is None:
            raise KeyError("Wiki version not found")
        return WikiDiff(
            article_id=article_id,
            from_version=from_version,
            to_version=to_version,
            unified_diff=unified_content_diff(
                before.content,
                after.content,
                from_version=from_version,
                to_version=to_version,
            ),
        )

    def rollback(self, tenant_id: str, article_id: str, target_version: int) -> WikiArticleVersion:
        target = self.get_version(tenant_id, article_id, target_version)
        if target is None:
            raise KeyError("Wiki version not found")
        return self.upsert(
            tenant_id=tenant_id,
            title=target.title,
            content=target.content,
            source_references=target.source_references,
            slug=target.slug,
            change_note=f"rollback_from:v{target_version}",
        )

    def search(self, query: str, scope: AccessScope, *, top_k: int) -> tuple[tuple[WikiArticleVersion, float], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT article_id, current_version
                FROM wiki_articles WHERE tenant_id=? ORDER BY updated_at DESC LIMIT ?
                """,
                (scope.tenant_id, self._scan_limit),
            ).fetchall()
            candidates = [
                self._load_version(connection, scope.tenant_id, str(row["article_id"]), int(row["current_version"]))
                for row in rows
            ]
        authorized = [article for article in candidates if _article_authorized(article, scope)]
        ranked = sorted(
            ((article, _lexical_score(query, f"{article.title}\n{article.content}")) for article in authorized),
            key=lambda pair: (pair[1], pair[0].version, pair[0].created_at),
            reverse=True,
        )
        return tuple(pair for pair in ranked if pair[1] > 0)[: max(1, top_k)]

    def _load_version(
        self,
        connection: sqlite3.Connection,
        tenant_id: str,
        article_id: str,
        version: int,
    ) -> WikiArticleVersion:
        row = connection.execute(
            """
            SELECT a.slug, v.tenant_id, v.article_id, v.version, v.title, v.content,
                   v.content_hash, v.change_note, v.created_at
            FROM wiki_versions v
            JOIN wiki_articles a ON a.tenant_id=v.tenant_id AND a.article_id=v.article_id
            WHERE v.tenant_id=? AND v.article_id=? AND v.version=?
            """,
            (tenant_id, article_id, version),
        ).fetchone()
        if row is None:
            raise KeyError("Wiki version not found")
        source_rows = connection.execute(
            """
            SELECT source, document_id, document_version, page, chunk_id, image_id, acl_tags_json
            FROM wiki_source_mappings
            WHERE tenant_id=? AND article_id=? AND version=? ORDER BY ordinal
            """,
            (tenant_id, article_id, version),
        ).fetchall()
        references = tuple(
            WikiSourceReference(
                source=str(source["source"]),
                document_id=str(source["document_id"]),
                document_version=int(source["document_version"]),
                page=int(source["page"]) if source["page"] is not None else None,
                chunk_id=str(source["chunk_id"]) if source["chunk_id"] else None,
                image_id=str(source["image_id"]) if source["image_id"] else None,
                acl_tags=frozenset(json.loads(str(source["acl_tags_json"]))),
            )
            for source in source_rows
        )
        return WikiArticleVersion(**dict(row), source_references=references)


def _article_authorized(article: WikiArticleVersion, scope: AccessScope) -> bool:
    for reference in article.source_references:
        if scope.document_ids and reference.document_id not in scope.document_ids:
            return False
        if scope.allowed_sources and reference.source not in scope.allowed_sources:
            return False
        if reference.acl_tags and not reference.acl_tags.intersection(scope.acl_tags):
            return False
    return bool(article.source_references) and bool(scope.document_ids or scope.allowed_sources)


def _lexical_score(query: str, content: str) -> float:
    normalized_query = " ".join(query.casefold().split())
    normalized_content = " ".join(content.casefold().split())
    if not normalized_query:
        return 0.0
    if normalized_query in normalized_content:
        return 1.0
    tokens = set(_TOKEN_RE.findall(normalized_query))
    if not tokens:
        return 0.0
    matches = sum(1 for token in tokens if token in normalized_content)
    return matches / len(tokens)


def _unique_references(values: tuple[WikiSourceReference, ...]) -> tuple[WikiSourceReference, ...]:
    unique: dict[tuple[object, ...], WikiSourceReference] = {}
    for reference in values:
        key = (
            reference.source,
            reference.document_id,
            reference.document_version,
            reference.page,
            reference.chunk_id,
            reference.image_id,
            tuple(sorted(reference.acl_tags)),
        )
        unique[key] = reference
    return tuple(unique.values())


def _slug(value: str) -> str:
    normalized = _SLUG_RE.sub("-", value.casefold()).strip("-")
    return normalized[:120] or uuid.uuid4().hex


def _required(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{label} must not be blank")
    return normalized


__all__ = ["WikiStore"]
