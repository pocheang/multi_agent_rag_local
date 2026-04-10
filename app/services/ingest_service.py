from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from app.graph.neo4j_client import Neo4jClient
from app.ingestion.chunker import split_documents
from app.ingestion.graph_extractor import extract_triplets
from app.ingestion.loaders import load_documents
from app.retrievers.bm25_retriever import reset_bm25_cache
from app.retrievers.corpus_store import documents_to_records, read_corpus_records, write_corpus_records
from app.retrievers.hybrid_retriever import clear_retrieval_cache
from app.retrievers.parent_store import read_parent_records, write_parent_records
from app.retrievers.vector_store import add_documents, clear_vector_store_cache, get_vector_store


def _merge_records_by_id(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for row in existing + incoming:
        row_id = str(row.get("id", "") or "").strip()
        if not row_id:
            continue
        if row_id not in merged:
            order.append(row_id)
        merged[row_id] = row
    return [merged[row_id] for row_id in order]


def ingest_paths(
    paths: list[Path],
    reset_vector_store: bool = False,
    metadata_overrides_by_source: dict[str, dict[str, Any]] | None = None,
) -> dict:
    docs = load_documents(paths=paths)
    if not docs:
        return {"loaded_documents": 0, "chunks_indexed": 0, "triplets_written": 0}

    if metadata_overrides_by_source:
        for doc in docs:
            source = str((doc.metadata or {}).get("source", "")).strip()
            extra = metadata_overrides_by_source.get(source)
            if extra:
                doc.metadata = {**(doc.metadata or {}), **extra}

    chunks, parent_records = split_documents(docs)
    records = documents_to_records(chunks)
    for chunk, record in zip(chunks, records):
        chunk.metadata = record["metadata"]

    existing = [] if reset_vector_store else read_corpus_records()
    merged_records = _merge_records_by_id(existing, records)
    write_corpus_records(merged_records)

    existing_parents = [] if reset_vector_store else read_parent_records()
    merged_parents = _merge_records_by_id(existing_parents, parent_records)
    write_parent_records(merged_parents)

    reset_bm25_cache()

    store = get_vector_store()
    if reset_vector_store:
        try:
            store.delete_collection()
        except Exception:
            pass
        clear_vector_store_cache()
        store = get_vector_store()
    add_documents(chunks, ids=[record["id"] for record in records])
    clear_retrieval_cache()

    count_triplets = 0
    client = None
    try:
        client = Neo4jClient()
    except Exception:
        client = None

    if client is not None:
        try:
            for chunk in chunks:
                text = chunk.page_content
                source = str(chunk.metadata.get("source", "unknown"))
                for head, relation, tail in extract_triplets(text):
                    client.upsert_triplet(head=head, relation=relation, tail=tail, source=source)
                    count_triplets += 1
        finally:
            client.close()

    return {
        "loaded_documents": len(docs),
        "chunks_indexed": len(chunks),
        "triplets_written": count_triplets,
    }


def ingest_docs_dir(data_dir: Path, reset_vector_store: bool = True) -> dict:
    paths = [p for p in data_dir.rglob("*") if p.is_file()]
    return ingest_paths(paths, reset_vector_store=reset_vector_store)
