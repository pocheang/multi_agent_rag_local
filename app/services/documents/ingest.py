import logging
from pathlib import Path
from typing import Any

from app.graph.knowledge.client import Neo4jClient
from app.ingestion import loaders
from app.ingestion.chunking.splitter import split_documents
from app.ingestion.graph_extractor import extract_graph_triplets
from app.retrievers.bm25_retriever import reset_bm25_cache
from app.retrievers.hybrid.retriever import clear_retrieval_cache
from app.retrievers.stores.corpus import documents_to_records, read_corpus_records, write_corpus_records
from app.retrievers.stores.parent import read_parent_records, write_parent_records
from app.retrievers.stores.vector import add_documents, clear_vector_store_cache, get_vector_store

logger = logging.getLogger(__name__)


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
    parser_profiles_by_source: dict[str, dict[str, Any]] | None = None,
) -> dict:
    docs = loaders.load_documents(paths=paths)
    if not docs:
        return {"loaded_documents": 0, "chunks_indexed": 0, "triplets_written": 0}

    # Count unique source files (not Document objects)
    unique_sources = {str((doc.metadata or {}).get("source", "")) for doc in docs}
    unique_sources.discard("")  # Remove empty strings
    files_loaded = len(unique_sources)

    # Collect page information for each source
    pages_by_source: dict[str, set[int]] = {}
    for doc in docs:
        source = str((doc.metadata or {}).get("source", ""))
        page = (doc.metadata or {}).get("page")
        if source and page is not None:
            try:
                pages_by_source.setdefault(source, set()).add(int(page))
            except (ValueError, TypeError):
                pass

    if metadata_overrides_by_source:
        for doc in docs:
            source = str((doc.metadata or {}).get("source", "")).strip()
            extra = metadata_overrides_by_source.get(source)
            if extra:
                doc.metadata = {**(doc.metadata or {}), **extra}

    chunks, parent_records = split_documents(docs)
    records = documents_to_records(chunks)
    for chunk, record in zip(chunks, records, strict=False):
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
        except (RuntimeError, ValueError) as e:
            logger.warning(f"vector_store_delete_collection_failed: {e}", exc_info=True)
        clear_vector_store_cache()
        store = get_vector_store()
    add_documents(chunks, ids=[record["id"] for record in records])
    clear_retrieval_cache()

    count_triplets = 0
    client = None
    try:
        client = Neo4jClient()
    except (ImportError, RuntimeError, ValueError) as e:
        logger.warning(
            f"Neo4j client initialization failed - graph features disabled. "
            f"Error: {e}. Check NEO4J_URI and credentials in environment.",
            exc_info=True,
        )
        client = None

    if client is not None:
        try:
            # Collect all triplets first for batch processing (10x performance improvement)
            triplets_to_insert = []
            extraction_errors = 0

            for chunk_idx, chunk in enumerate(chunks):
                text = chunk.page_content
                source = str(chunk.metadata.get("source", "unknown"))
                profile = (parser_profiles_by_source or {}).get(source, {})
                if profile.get("enable_graph") is False:
                    continue
                chunk_id = str(chunk.metadata.get("chunk_id", ""))
                page_raw = chunk.metadata.get("page")
                try:
                    page = int(page_raw) if page_raw is not None else None
                except (TypeError, ValueError):
                    page = None
                    logger.debug(f"Invalid page number '{page_raw}' in chunk {chunk_idx} from {source}")

                min_confidence = float(profile.get("graph_min_confidence", 0.5) or 0.5)

                try:
                    for triplet in extract_graph_triplets(text, min_confidence=min_confidence):
                        triplets_to_insert.append(
                            {
                                "head": triplet.head,
                                "relation": triplet.relation,
                                "tail": triplet.tail,
                                "source": source,
                                "chunk_id": chunk_id,
                                "page": page,
                                "confidence": triplet.confidence,
                            }
                        )
                except Exception as e:
                    extraction_errors += 1
                    logger.warning(f"Failed to extract triplets from chunk {chunk_idx} (source: {source}): {e}")

            # Batch insert all triplets at once
            if triplets_to_insert:
                try:
                    count_triplets = client.batch_upsert_triplets(triplets_to_insert)
                    if extraction_errors > 0:
                        logger.warning(
                            f"Graph extraction completed with {extraction_errors} errors. "
                            f"Successfully inserted {count_triplets} triplets."
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to batch insert {len(triplets_to_insert)} triplets to Neo4j: {e}. "
                        f"Graph features may be incomplete.",
                        exc_info=True,
                    )
            elif extraction_errors > 0:
                logger.warning(
                    f"No triplets extracted due to {extraction_errors} extraction errors. "
                    f"Check document format and extraction settings."
                )
        except Exception as e:
            logger.error(f"Unexpected error during graph ingestion: {e}", exc_info=True)
        finally:
            client.close()

    return {
        "loaded_documents": files_loaded,
        "chunks_indexed": len(chunks),
        "triplets_written": count_triplets,
        "pages_by_source": {k: len(v) for k, v in pages_by_source.items()},
    }


def ingest_docs_dir(data_dir: Path, reset_vector_store: bool = True) -> dict:
    paths = [p for p in data_dir.rglob("*") if p.is_file()]
    return ingest_paths(paths, reset_vector_store=reset_vector_store)
