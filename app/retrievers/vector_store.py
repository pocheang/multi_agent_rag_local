from functools import lru_cache
import threading

from langchain_core.documents import Document

from langchain_chroma import Chroma

from app.core.config import get_settings
from app.core.models import get_embedding_model

_VECTOR_OP_LOCK = threading.RLock()


@lru_cache(maxsize=4)
def _get_vector_store_cached(collection_name: str, persist_directory: str) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embedding_model(),
        persist_directory=persist_directory,
    )


def get_vector_store() -> Chroma:
    settings = get_settings()
    return _get_vector_store_cached(
        collection_name=settings.chroma_collection,
        persist_directory=str(settings.chroma_path),
    )


def similarity_search(query: str, k: int | None = None, allowed_sources: list[str] | None = None):
    settings = get_settings()
    with _VECTOR_OP_LOCK:
        store = get_vector_store()
        if allowed_sources is not None:
            if not allowed_sources:
                return []
            return store.similarity_search_with_relevance_scores(
                query,
                k=k or settings.top_k,
                filter={"source": {"$in": allowed_sources}},
            )
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
        except Exception:
            pass
        _get_vector_store_cached.cache_clear()
        store = get_vector_store()
        documents = [Document(page_content=row.get("text", ""), metadata=row.get("metadata", {}) or {}) for row in records]
        ids = [str(row.get("id")) for row in records if row.get("id")]
        if documents:
            store.add_documents(documents, ids=ids if len(ids) == len(documents) else None)


def clear_vector_store_cache() -> None:
    _get_vector_store_cached.cache_clear()
