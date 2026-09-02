import logging
import sqlite3
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import get_settings
from app.services.models.runtime import get_embedding_model

logger = logging.getLogger(__name__)

_VECTOR_OP_LOCK = threading.RLock()


@dataclass(frozen=True, slots=True)
class OwnerScope:
    """Who is asking, for the store's own metadata check.

    Deliberately not AccessScope: the store needs an identity to compare chunk
    metadata against, not the caller's whole authorization decision, and keeping
    it small stops the store from growing opinions about authorization.
    """

    user_id: str
    tenant_id: str

    @classmethod
    def from_access_scope(cls, scope) -> "OwnerScope | None":
        """Build from an AccessScope, or None if it has no usable identity."""
        user_id = str(getattr(scope, "user_id", "") or "").strip()
        if not user_id:
            return None
        return cls(user_id=user_id, tenant_id=str(getattr(scope, "tenant_id", "") or "").strip() or user_id)


def _repair_chroma_segments_foreign_key(persist_directory: str) -> None:
    """Repair Chroma's historical singular collection-table reference."""
    db_path = Path(persist_directory) / "chroma.sqlite3"
    if not db_path.is_file():
        return

    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='segments'").fetchone()
        schema = str(row[0] or "") if row else ""
        normalized_schema = " ".join(schema.lower().split())
        if "references collection(" not in normalized_schema:
            return

        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                CREATE TABLE segments_querymind_fixed (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    collection TEXT NOT NULL REFERENCES collections(id)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO segments_querymind_fixed(id, type, scope, collection)
                SELECT id, type, scope, collection FROM segments
                """
            )
            conn.execute("DROP TABLE segments")
            conn.execute("ALTER TABLE segments_querymind_fixed RENAME TO segments")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"Chroma foreign-key repair left {len(violations)} violation(s)")
    finally:
        conn.close()


@lru_cache(maxsize=4)
def _get_vector_store_cached(
    collection_name: str,
    persist_directory: str,
    embedding_backend: str,
    embedding_model: str,
    embedding_base_url: str,
) -> Chroma:
    store = Chroma(
        collection_name=collection_name,
        embedding_function=get_embedding_model(),
        persist_directory=persist_directory,
    )
    _repair_chroma_segments_foreign_key(persist_directory)
    return store


def get_vector_store() -> Chroma:
    settings = get_settings()
    backend = str(getattr(settings, "model_backend", "local") or "local").strip().lower()
    if backend == "openai":
        embed_model = str(getattr(settings, "openai_embed_model", "") or "")
        embed_base_url = str(getattr(settings, "openai_base_url", "") or "")
    elif backend == "local":
        embed_model = "local-hash-384"
        embed_base_url = ""
    else:
        embed_model = str(getattr(settings, "ollama_embed_model", "") or "")
        embed_base_url = str(getattr(settings, "ollama_base_url", "") or "")
    collection_name = settings.chroma_collection
    if backend == "local" and not collection_name.endswith("_local"):
        collection_name = f"{collection_name}_local"
    return _get_vector_store_cached(
        collection_name=collection_name,
        persist_directory=str(settings.chroma_path),
        embedding_backend=backend,
        embedding_model=embed_model,
        embedding_base_url=embed_base_url,
    )


def get_named_vector_store(collection_name: str) -> Chroma:
    """Return a named collection through the canonical vector-store factory."""

    settings = get_settings()
    backend = str(getattr(settings, "model_backend", "local") or "local").strip().lower()
    if backend == "openai":
        embed_model = str(getattr(settings, "openai_embed_model", "") or "")
        embed_base_url = str(getattr(settings, "openai_base_url", "") or "")
    elif backend == "local":
        embed_model = "local-hash-384"
        embed_base_url = ""
    else:
        embed_model = str(getattr(settings, "ollama_embed_model", "") or "")
        embed_base_url = str(getattr(settings, "ollama_base_url", "") or "")
    return _get_vector_store_cached(
        collection_name=collection_name,
        persist_directory=str(settings.chroma_path),
        embedding_backend=backend,
        embedding_model=embed_model,
        embedding_base_url=embed_base_url,
    )


def get_chroma_client():
    """Compatibility access to the client owned by the canonical vector store."""

    return get_vector_store()._client  # noqa: SLF001 - legacy named collections share this owner


# Ingest gives a document with no explicit owner tenant_id="shared" (see
# app/ingestion/loaders/dispatch.py:181), which is how the shared data/docs/
# corpus is distinguished from an upload -- uploads always carry the uploader as
# both owner_user_id and tenant_id.
SHARED_CORPUS_TENANT = "shared"


def _owner_clause(owner: OwnerScope) -> dict:
    """Metadata predicate for 'this chunk is readable by this owner'."""
    return {
        "$or": [
            {"owner_user_id": {"$eq": owner.user_id}},
            {"visibility": {"$eq": "public"}},
            {"tenant_id": {"$eq": SHARED_CORPUS_TENANT}},
        ]
    }


def _verify_sources(matches, allowed_sources: list[str]):
    """Post-condition: the store must not return a chunk outside the filter.

    Chroma applies the `$in` itself, so this only fires if the filter did not do
    what we asked -- a malformed clause, or a very large `$in` behaving
    unexpectedly. Cheap insurance on the one call that decides what a user reads.
    """
    permitted = set(allowed_sources)
    kept = [
        row
        for row in matches
        if isinstance(row, tuple) and str((getattr(row[0], "metadata", {}) or {}).get("source", "")) in permitted
    ]
    if len(kept) != len(matches):
        logger.error(
            "similarity_search: store returned %d chunk(s) outside the source filter; dropped",
            len(matches) - len(kept),
        )
    return kept


def similarity_search(
    query: str,
    k: int | None = None,
    allowed_sources: list[str] | None = None,
    require_source_filter: bool = True,
    owner: OwnerScope | None = None,
):
    """
    执行向量相似度搜索。

    Args:
        query: 查询文本
        k: 返回结果数量
        allowed_sources: 允许的文档源列表（用于用户隔离）
        require_source_filter: 是否强制要求提供 allowed_sources（默认 True，用于安全隔离）

    Returns:
        相似文档列表及其相关性分数

    Raises:
        ValueError: 如果 require_source_filter=True 但未提供 allowed_sources
    """
    settings = get_settings()

    # 安全检查：强制要求源过滤以防止跨用户数据泄漏
    if require_source_filter and allowed_sources is None:
        logger.error("similarity_search called without allowed_sources - potential security violation")
        raise ValueError(
            "allowed_sources is required for user data isolation. "
            "Pass allowed_sources parameter or set require_source_filter=False for system operations."
        )

    with _VECTOR_OP_LOCK:
        store = get_vector_store()
        if allowed_sources is not None:
            if not allowed_sources:
                # 空列表表示用户没有任何可访问的文档
                logger.debug("similarity_search: empty allowed_sources, returning no results")
                return []

            # 安全修复：验证 allowed_sources 是字符串列表
            if not isinstance(allowed_sources, list):
                logger.error(f"allowed_sources must be a list, got {type(allowed_sources)}")
                raise TypeError(f"allowed_sources must be a list, got {type(allowed_sources).__name__}")

            if not all(isinstance(s, str) for s in allowed_sources):
                logger.error("allowed_sources must contain only strings")
                raise TypeError("allowed_sources must contain only strings")

            source_clause: dict = {"source": {"$in": allowed_sources}}
            # Defence in depth: the source list is derived from the caller's
            # visible documents, so a bug there would hand the store the wrong
            # paths. The owner metadata is written independently at ingest, so
            # requiring both narrows what a wrong source list can reach.
            where = source_clause if owner is None else {"$and": [source_clause, _owner_clause(owner)]}
            matches = store.similarity_search_with_relevance_scores(
                query,
                k=k or settings.top_k,
                filter=where,
            )
            return _verify_sources(matches, allowed_sources)

        # 仅在显式允许时才不使用过滤（系统级操作）
        logger.warning("similarity_search: performing unfiltered search (require_source_filter=False)")
        return store.similarity_search_with_relevance_scores(query, k=k or settings.top_k)


def add_documents(documents, ids: list[str] | None = None):
    with _VECTOR_OP_LOCK:
        store = get_vector_store()
        if ids:
            store.add_documents(documents, ids=ids)
        else:
            store.add_documents(documents)


def delete_documents_by_ids(ids: list[str]):
    if not ids:
        return
    with _VECTOR_OP_LOCK:
        store = get_vector_store()
        store.delete(ids=ids)


def reset_vector_store_from_records(records: list[dict]):
    with _VECTOR_OP_LOCK:
        _get_vector_store_cached.cache_clear()
        store = get_vector_store()
        try:
            store.delete_collection()
        except (RuntimeError, ValueError) as e:
            logger.warning(f"vector_store_reset_delete_failed: {e}", exc_info=True)
        except Exception as e:
            logger.exception(f"Unexpected error deleting vector store collection: {e}")
        _get_vector_store_cached.cache_clear()
        store = get_vector_store()
        documents = [
            Document(page_content=row.get("text", ""), metadata=row.get("metadata", {}) or {}) for row in records
        ]
        ids = [str(row.get("id")) for row in records if row.get("id")]
        if documents:
            store.add_documents(documents, ids=ids if len(ids) == len(documents) else None)


def clear_vector_store_cache() -> None:
    _get_vector_store_cached.cache_clear()
