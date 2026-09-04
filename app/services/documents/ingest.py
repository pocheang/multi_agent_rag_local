import logging
import re
from pathlib import Path
from typing import Any

from app.graph.knowledge.client import Neo4jClient
from app.ingestion.chunking.splitter import split_documents
from app.ingestion.graph_extractor import extract_graph_triplets_with_diagnostics
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

    docs, parsed_documents, images_indexed, tables_indexed = _load_documents(
        paths, metadata_overrides_by_source, persist_evidence
    )
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
    count_triplets, triplet_methods = _write_graph_triplets(chunks, parser_profiles_by_source)

    return {
        # Files, not Document objects: one PDF arrives as one Document per page.
        "loaded_documents": len(sources),
        "chunks_indexed": len(chunks),
        "triplets_written": count_triplets,
        # Which extractor produced the candidates, and how many the confidence
        # threshold dropped. A bare `triplets_written: 0` cannot distinguish "no
        # Neo4j", "nothing extractable" and "everything the rule extractor
        # produced was correctly rejected" -- and the last of those is the
        # default on an installation with no LLM.
        "triplets_discarded_low_confidence": int(triplet_methods.get("discarded_low_confidence", 0)),
        "triplet_methods": {
            name: count for name, count in triplet_methods.items() if name != "discarded_low_confidence"
        },
        "images_indexed": images_indexed,
        "tables_indexed": tables_indexed,
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
) -> tuple[list[Any], list[ParsedDocument], int, int]:
    """Parse each file and stamp every document it yields with its provenance.

    Metadata is layered loader < caller override < canonical, so the identifiers
    the rest of the system scopes on cannot be overwritten by a caller.
    """

    docs: list[Any] = []
    parsed_documents: list[ParsedDocument] = []
    images_indexed = 0
    tables_indexed = 0
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
        images_indexed += _index_images(parsed, image_artifacts, canonical)
        tables_indexed += _index_tables(parsed, canonical)
        docs.extend(loaded)
        parsed_documents.append(parsed)
    return docs, parsed_documents, images_indexed, tables_indexed


# The multimodal source retrieves images by the text something managed to read out
# of them. Nothing was ever writing that text, so `image_descriptions` did not
# exist and the source returned nothing on every visual question it was selected
# for. This is the producer.
_IMAGE_ERROR_MARKER = "[image_ocr_error]"


def _index_images(
    parsed: ParsedDocument,
    image_artifacts: dict[str, str],
    canonical: dict[str, Any],
) -> int:
    """Index each of a document's images, and report how many became searchable.

    Synchronous on purpose. `ingest_paths` is reached from ``asyncio.to_thread``,
    where driving an event loop is the defect this repository has fixed twice, and
    nothing here needs one: `ocr_image_bytes` is synchronous and so is the store.
    """

    if not parsed.images:
        return 0

    try:
        from app.ingestion.extraction.ocr import ocr_image_bytes
        from app.services.multimodal.image_processor import ImageProcessor
        from app.services.multimodal.models import ImageContent
    except ImportError as e:
        # The `multimodal` extra is optional and ingesting a document is not.
        logger.info(f"image_indexing_unavailable error={e}")
        return 0

    processor = ImageProcessor()
    source = Path(str(canonical.get("source", "") or ""))
    indexed = 0

    for image in parsed.images:
        text = _readable_image_text(image, ocr_image_bytes, source)
        if not text:
            # An image nothing could read is not evidence. Indexing the reason --
            # "Tesseract executable not found" -- would make the diagnostic itself
            # retrievable, which is worse than the image being absent.
            continue
        try:
            processor.index_image(
                ImageContent(
                    image_id=image.image_id,
                    doc_id=str(canonical.get("document_id", "") or ""),
                    page_number=image.page,
                    image_data=b"",  # the bytes live in the artifact store, not the index
                    description=text,
                    tenant_id=str(canonical.get("tenant_id", "") or ""),
                    owner_user_id=str(canonical.get("owner_user_id", "") or ""),
                    visibility=str(canonical.get("visibility", "private") or "private"),
                    version=int(canonical.get("version", 1) or 1),
                    artifact_uri=image_artifacts.get(image.image_id, ""),
                    metadata={"source": str(canonical.get("source", "") or ""), "filename": image.filename},
                )
            )
            indexed += 1
        except Exception as e:
            logger.warning(f"image_index_failed image_id={image.image_id} error={e}")
    return indexed


def _readable_image_text(image: Any, ocr_image_bytes: Any, source: Path) -> str:
    """Whatever was actually read out of this image, or "" if that was nothing."""

    parts = [str(image.description or "").strip(), str(image.ocr_text or "").strip()]
    if not any(parts) and image.data:
        try:
            documents = ocr_image_bytes(image.data, source, page=image.page)
        except Exception as e:
            logger.warning(f"image_ocr_failed image_id={image.image_id} error={e}")
            documents = []
        for document in documents:
            content = str(getattr(document, "page_content", "") or "")
            if content and _IMAGE_ERROR_MARKER not in content:
                parts.append(content.strip())
    return "\n\n".join(part for part in parts if part)[:4000]


def _index_tables(
    parsed: ParsedDocument,
    canonical: dict[str, Any],
) -> int:
    """Index each table as a unit, and report how many became searchable.

    The chunker splits by size, so a table longer than a chunk is cut across
    several of them and none of the fragments carries the header row -- the
    classic way a retrieved table answers a question wrongly. Indexed whole, one
    hit is the whole table.

    Synchronous for the same reason as `_index_images`: this runs in a worker
    thread, and nothing here needs an event loop.
    """

    if not parsed.tables:
        return 0

    try:
        from app.services.multimodal.models import TableContent
        from app.services.multimodal.table_extractor import TableExtractor
    except ImportError as e:
        # As above: without the extra a document still ingests, with no tables
        # indexed rather than no ingest at all.
        logger.info(f"table_indexing_unavailable error={e}")
        return 0

    extractor = TableExtractor()
    indexed = 0
    for table in parsed.tables:
        headers, rows = _table_from_markdown(str(table.markdown or ""))
        if not headers and not rows:
            continue
        sheet = str(getattr(table, "sheet", "") or "")
        try:
            extractor.index_table(
                TableContent(
                    table_id=table.table_id,
                    doc_id=str(canonical.get("document_id", "") or ""),
                    page_number=table.page,
                    headers=headers,
                    rows=rows,
                    summary=f"Table on page {table.page}" + (f" (sheet: {sheet})" if sheet else ""),
                    metadata={
                        "document_id": str(canonical.get("document_id", "") or ""),
                        "tenant_id": str(canonical.get("tenant_id", "") or ""),
                        "owner_user_id": str(canonical.get("owner_user_id", "") or ""),
                        "visibility": str(canonical.get("visibility", "private") or "private"),
                        "version": int(canonical.get("version", 1) or 1),
                        "source": str(canonical.get("source", "") or ""),
                        "num_rows": len(rows),
                        "num_cols": len(headers),
                        "extraction_method": "loader_markdown",
                    },
                )
            )
            indexed += 1
        except Exception as e:
            logger.warning(f"table_index_failed table_id={table.table_id} error={e}")
    return indexed


def _table_from_markdown(markdown: str) -> tuple[list[str], list[list[str]]]:
    """Recover the header and body of a pipe table the loader rendered.

    The loader had the rows and flattened them; reading them back makes the
    header a header again, which is the part a fragment loses.
    """

    lines = [line.strip() for line in markdown.splitlines() if line.strip().startswith("|")]
    if not lines:
        return [], []
    parsed_rows = [_markdown_cells(line) for line in lines]
    body = [row for row in parsed_rows[1:] if not _is_separator_row(row)]
    return parsed_rows[0], body


def _markdown_cells(line: str) -> list[str]:
    # Split on pipes the loader did not escape; it writes cell content with `\|`.
    parts = re.split(r"(?<!\\)\|", line)[1:-1]
    return [part.replace("\\|", "|").strip() for part in parts]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(set(cell) <= {"-", ":", " "} and cell for cell in cells)


def _pages_by_source(docs: list[Any]) -> dict[str, set[int]]:
    """Which pages each source contributed.

    A source whose page numbers are all unreadable contributes no entry. It used
    to contribute an empty one, reported downstream as a page count of 0, because
    ``setdefault`` ran before ``int()`` and left the set behind when the parse
    raised. "This document has no readable page numbers" and "this document has
    no pages" are different claims, and only the first one was ever true.
    """

    pages_by_source: dict[str, set[int]] = {}
    for doc in docs:
        source = str((doc.metadata or {}).get("source", ""))
        page = _optional_int((doc.metadata or {}).get("page"))
        if source and page is not None:
            pages_by_source.setdefault(source, set()).add(page)
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


def _write_graph_triplets(
    chunks: list[Any], parser_profiles_by_source: dict[str, dict[str, Any]] | None
) -> tuple[int, dict[str, int]]:
    """Extract and insert graph triplets, or write none without disturbing the run.

    Neo4j is optional throughout this system, so every failure here -- an absent
    server, an unparseable chunk, a rejected batch -- costs the triplets and
    nothing else.

    Returns the count written and a per-extractor breakdown, because "wrote
    nothing" now has several distinct causes and the caller cannot tell them
    apart from a zero.
    """

    try:
        client = Neo4jClient()
    except (ImportError, RuntimeError, ValueError) as e:
        logger.warning(
            f"Neo4j client initialization failed - graph features disabled. "
            f"Error: {e}. Check NEO4J_URI and credentials in environment.",
            exc_info=True,
        )
        return 0, {}

    try:
        rows, extraction_errors, methods = _triplet_rows(chunks, parser_profiles_by_source)
        return _insert_triplets(client, rows, extraction_errors, methods), methods
    except Exception as e:
        logger.exception(f"Unexpected error during graph ingestion: {e}")
        return 0, {}
    finally:
        client.close()


def _triplet_rows(
    chunks: list[Any], parser_profiles_by_source: dict[str, dict[str, Any]] | None
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    """Every triplet the chunks yield, gathered for one batch insert.

    A chunk that will not parse costs that chunk and is counted rather than
    raised: the rest of the batch is still worth inserting.
    """

    rows: list[dict[str, Any]] = []
    methods: dict[str, int] = {}
    extraction_errors = 0
    for chunk_idx, chunk in enumerate(chunks):
        source = str(chunk.metadata.get("source", "unknown"))
        profile = (parser_profiles_by_source or {}).get(source, {})
        if profile.get("enable_graph") is False:
            continue
        provenance = _chunk_provenance(chunk, chunk_idx, source)
        min_confidence = float(profile.get("graph_min_confidence", 0.5) or 0.5)
        try:
            kept, chunk_methods = extract_graph_triplets_with_diagnostics(
                chunk.page_content, min_confidence=min_confidence
            )
            for name, count in chunk_methods.items():
                methods[name] = methods.get(name, 0) + count
            for triplet in kept:
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
    return rows, extraction_errors, methods


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


def _insert_triplets(
    client: Neo4jClient,
    rows: list[dict[str, Any]],
    extraction_errors: int,
    methods: dict[str, int] | None = None,
) -> int:
    if not rows:
        discarded = int((methods or {}).get("discarded_low_confidence", 0))
        if discarded > 0:
            # The common shape on an installation with no working LLM: the rule
            # extractor produced candidates and every one scored below the
            # profile threshold. Say so, with the numbers -- a graph route that
            # silently returns nothing is indistinguishable from a broken one.
            produced = ", ".join(
                f"{name}={count}"
                for name, count in sorted((methods or {}).items())
                if name != "discarded_low_confidence"
            )
            logger.info(
                f"No triplets written: {discarded} candidate(s) scored below the profile's "
                f"graph_min_confidence. Extractors that ran: {produced or 'none'}. "
                f"Rule-extracted triplets are deliberately below every shipped threshold; "
                f"configure a real MODEL_BACKEND for LLM extraction."
            )
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
