import logging
from pathlib import Path
from typing import Any

from app.graph.knowledge.client import Neo4jClient
from app.ingestion.chunking.splitter import split_documents
from app.ingestion.graph_extractor import extract_graph_triplets
from app.ingestion.loaders.dispatch import load_document_with_evidence
from app.retrievers.bm25_retriever import reset_bm25_cache
from app.retrievers.hybrid.retriever import clear_retrieval_cache
from app.retrievers.stores.corpus import documents_to_records, read_corpus_records, write_corpus_records
from app.retrievers.stores.parent import read_parent_records, write_parent_records
from app.retrievers.stores.vector import add_documents, clear_vector_store_cache, get_vector_store
from app.services.evidence import ArtifactStore, ManifestStore, ParsedDocument, build_manifest

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
    persist_evidence: bool = True,
) -> dict:
    """Load, index and graph-extract a set of files, and report what happened."""

    docs, parsed_documents = _load_documents(paths, metadata_overrides_by_source, persist_evidence)
    if not docs:
        # Deliberately shorter than the result below: there is no chunk, page or
        # manifest to report. Evidence has still been persisted for whatever
        # parsed to no text -- this discards the manifest it just wrote.
        return {"loaded_documents": 0, "chunks_indexed": 0, "triplets_written": 0}

    pages_by_source = _pages_by_source(docs)
    sources = {str((doc.metadata or {}).get("source", "")) for doc in docs}
    sources.discard("")

    chunks, parent_records = split_documents(docs)
    records = _write_records(chunks, parent_records, reset_vector_store=reset_vector_store)
    _rebuild_vector_index(chunks, [record["id"] for record in records], reset_vector_store=reset_vector_store)
    count_triplets = _write_graph_triplets(chunks, parser_profiles_by_source)

    return {
        # Files, not Document objects: one PDF arrives as one Document per page.
        "loaded_documents": len(sources),
        "chunks_indexed": len(chunks),
        "triplets_written": count_triplets,
        "pages_by_source": {source: len(pages) for source, pages in pages_by_source.items()},
        "evidence_manifests": [
            {
                "document_id": parsed.document.document_id,
                "version": parsed.document.version,
                "tenant_id": parsed.document.tenant_id,
            }
            for parsed in parsed_documents
        ],
    }


def _load_documents(
    paths: list[Path],
    metadata_overrides_by_source: dict[str, dict[str, Any]] | None,
    persist_evidence: bool,
) -> tuple[list[Any], list[ParsedDocument]]:
    """Parse each file and stamp every document it yields with its provenance.

    Metadata is layered loader < caller override < canonical, so the identifiers
    the rest of the system scopes on cannot be overwritten by a caller.
    """

    docs: list[Any] = []
    parsed_documents: list[ParsedDocument] = []
    for path in paths:
        source = str(path)
        metadata = dict((metadata_overrides_by_source or {}).get(source, {}))
        parsed, loaded = load_document_with_evidence(path, metadata)
        image_artifacts = _persist_evidence(parsed, path) if persist_evidence else _existing_image_artifacts(parsed)
        canonical = _canonical_metadata(parsed)
        for doc in loaded:
            doc.metadata = {**(doc.metadata or {}), **metadata, **canonical}
            image_id = str(doc.metadata.get("image_id", "") or "")
            if image_id in image_artifacts:
                doc.metadata["artifact_uri"] = image_artifacts[image_id]
        docs.extend(loaded)
        parsed_documents.append(parsed)
    return docs, parsed_documents


def _pages_by_source(docs: list[Any]) -> dict[str, set[int]]:
    """Which pages each source contributed.

    A source whose page numbers are all unreadable is registered with an empty
    set rather than left out -- ``setdefault`` runs before ``int()``.
    """

    pages_by_source: dict[str, set[int]] = {}
    for doc in docs:
        source = str((doc.metadata or {}).get("source", ""))
        page = (doc.metadata or {}).get("page")
        if source and page is not None:
            try:
                pages_by_source.setdefault(source, set()).add(int(page))
            except (ValueError, TypeError):
                pass
    return pages_by_source


def _write_records(chunks: list[Any], parent_records: list[dict], *, reset_vector_store: bool) -> list[dict]:
    """Persist the corpus and parent rows, and hand each chunk its record metadata.

    A reset run starts from nothing; every other run merges by id, so re-ingesting
    one file replaces its rows and leaves the rest of the corpus alone.
    """

    records = documents_to_records(chunks)
    for chunk, record in zip(chunks, records, strict=False):
        chunk.metadata = record["metadata"]

    existing = [] if reset_vector_store else read_corpus_records()
    write_corpus_records(_merge_records_by_id(existing, records))

    existing_parents = [] if reset_vector_store else read_parent_records()
    write_parent_records(_merge_records_by_id(existing_parents, parent_records))

    reset_bm25_cache()
    return records


def _rebuild_vector_index(chunks: list[Any], record_ids: list[str], *, reset_vector_store: bool) -> None:
    store = get_vector_store()
    if reset_vector_store:
        try:
            store.delete_collection()
        except (RuntimeError, ValueError) as e:
            logger.warning(f"vector_store_delete_collection_failed: {e}", exc_info=True)
        clear_vector_store_cache()
        get_vector_store()  # reopen behind the cleared cache, so the collection exists again
    add_documents(chunks, ids=record_ids)
    clear_retrieval_cache()


def _write_graph_triplets(chunks: list[Any], parser_profiles_by_source: dict[str, dict[str, Any]] | None) -> int:
    """Extract and insert graph triplets, or return 0 without disturbing the run.

    Neo4j is optional throughout this system, so every failure here -- an absent
    server, an unparseable chunk, a rejected batch -- costs the triplets and
    nothing else.
    """

    try:
        client = Neo4jClient()
    except (ImportError, RuntimeError, ValueError) as e:
        logger.warning(
            f"Neo4j client initialization failed - graph features disabled. "
            f"Error: {e}. Check NEO4J_URI and credentials in environment.",
            exc_info=True,
        )
        return 0

    try:
        rows, extraction_errors = _triplet_rows(chunks, parser_profiles_by_source)
        return _insert_triplets(client, rows, extraction_errors)
    except Exception as e:
        logger.exception(f"Unexpected error during graph ingestion: {e}")
        return 0
    finally:
        client.close()


def _triplet_rows(
    chunks: list[Any], parser_profiles_by_source: dict[str, dict[str, Any]] | None
) -> tuple[list[dict[str, Any]], int]:
    """Every triplet the chunks yield, gathered for one batch insert.

    A chunk that will not parse costs that chunk and is counted rather than
    raised: the rest of the batch is still worth inserting.
    """

    rows: list[dict[str, Any]] = []
    extraction_errors = 0
    for chunk_idx, chunk in enumerate(chunks):
        source = str(chunk.metadata.get("source", "unknown"))
        profile = (parser_profiles_by_source or {}).get(source, {})
        if profile.get("enable_graph") is False:
            continue
        provenance = _chunk_provenance(chunk, chunk_idx, source)
        min_confidence = float(profile.get("graph_min_confidence", 0.5) or 0.5)
        try:
            for triplet in extract_graph_triplets(chunk.page_content, min_confidence=min_confidence):
                rows.append(
                    {
                        "head": triplet.head,
                        "relation": triplet.relation,
                        "tail": triplet.tail,
                        **provenance,
                        "confidence": triplet.confidence,
                    }
                )
        except Exception as e:
            extraction_errors += 1
            logger.warning(f"Failed to extract triplets from chunk {chunk_idx} (source: {source}): {e}")
    return rows, extraction_errors


def _chunk_provenance(chunk: Any, chunk_idx: int, source: str) -> dict[str, Any]:
    """The scoping fields every triplet carries back to the chunk it came from."""

    page_raw = chunk.metadata.get("page")
    page = _optional_int(page_raw)
    if page is None and page_raw is not None:
        logger.debug(f"Invalid page number '{page_raw}' in chunk {chunk_idx} from {source}")
    return {
        "source": source,
        "chunk_id": str(chunk.metadata.get("chunk_id", "")),
        "page": page,
        "document_id": str(chunk.metadata.get("document_id", "") or ""),
        "version": _optional_int(chunk.metadata.get("version")),
        "tenant_id": str(chunk.metadata.get("tenant_id", "") or ""),
        "owner_user_id": str(chunk.metadata.get("owner_user_id", "") or ""),
        "visibility": str(chunk.metadata.get("visibility", "private") or "private"),
        "acl_tags": str(chunk.metadata.get("acl_tags", "") or ""),
    }


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _insert_triplets(client: Neo4jClient, rows: list[dict[str, Any]], extraction_errors: int) -> int:
    if not rows:
        if extraction_errors > 0:
            logger.warning(
                f"No triplets extracted due to {extraction_errors} extraction errors. "
                f"Check document format and extraction settings."
            )
        return 0

    try:
        count = client.batch_upsert_triplets(rows)
    except Exception:
        logger.exception(f"Failed to batch insert {len(rows)} triplets to Neo4j. Graph features may be incomplete.")
        return 0

    if extraction_errors > 0:
        logger.warning(
            f"Graph extraction completed with {extraction_errors} errors. Successfully inserted {count} triplets."
        )
    return count


def ingest_docs_dir(data_dir: Path, reset_vector_store: bool = True) -> dict:
    paths = [p for p in data_dir.rglob("*") if p.is_file()]
    return ingest_paths(paths, reset_vector_store=reset_vector_store)


def _canonical_metadata(parsed: ParsedDocument) -> dict[str, Any]:
    document = parsed.document
    return {
        "source": document.source,
        "filename": document.filename,
        "document_id": document.document_id,
        "version": document.version,
        "tenant_id": document.tenant_id,
        "owner_user_id": document.owner_user_id,
        "visibility": document.visibility,
        "acl_tags": ",".join(document.acl_tags),
        "sha256": document.sha256,
        "parser": parsed.parser,
    }


def _persist_evidence(parsed: ParsedDocument, path: Path) -> dict[str, str]:
    store = ArtifactStore()
    document = parsed.document
    artifacts = [
        store.put_file(
            path,
            tenant_id=document.tenant_id,
            document_id=document.document_id,
            version=document.version,
        )
    ]
    image_uris: dict[str, str] = {}
    for image in parsed.images:
        suffix = Path(image.filename).suffix or ".bin"
        artifact = store.put_bytes(
            image.data,
            tenant_id=document.tenant_id,
            document_id=document.document_id,
            version=document.version,
            relative_path=f"images/{image.image_id}{suffix}",
            kind="image",
            media_type=image.media_type,
            page=image.page,
            image_id=image.image_id,
        )
        artifacts.append(artifact)
        image_uris[image.image_id] = artifact.uri
    parsed_artifact = store.put_json(
        parsed.model_dump(mode="json"),
        tenant_id=document.tenant_id,
        document_id=document.document_id,
        version=document.version,
        relative_path="parsed/document.json",
    )
    artifacts.append(parsed_artifact)
    manifest = build_manifest(parsed, tuple(artifacts))
    manifests = ManifestStore(store)
    try:
        manifests.save(manifest)
    except FileExistsError:
        existing = manifests.load(document.tenant_id, document.document_id, document.version)
        if existing.sha256 != manifest.sha256:
            raise RuntimeError("existing manifest version has a different source hash") from None
    return image_uris


def _existing_image_artifacts(parsed: ParsedDocument) -> dict[str, str]:
    document = parsed.document
    manifest = ManifestStore(ArtifactStore()).load(document.tenant_id, document.document_id, document.version)
    return {
        str(artifact.image_id): artifact.uri
        for artifact in manifest.artifacts
        if artifact.kind in {"image", "masked_image"} and artifact.image_id
    }
