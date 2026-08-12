import logging
import threading
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import get_settings
from app.services.models.runtime import get_embedding_model

logger = logging.getLogger(__name__)

_VECTOR_OP_LOCK = threading.RLock()


@lru_cache(maxsize=4)
def _get_vector_store_cached(
    collection_name: str,
    persist_directory: str,
    embedding_backend: str,
    embedding_model: str,
    embedding_base_url: str,
) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embedding_model(),
        persist_directory=persist_directory,
    )


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


def similarity_search(
    query: str, k: int | None = None, allowed_sources: list[str] | None = None, require_source_filter: bool = True
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

            return store.similarity_search_with_relevance_scores(
                query,
                k=k or settings.top_k,
                filter={"source": {"$in": allowed_sources}},
            )

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
            logger.error(f"Unexpected error deleting vector store collection: {e}", exc_info=True)
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


