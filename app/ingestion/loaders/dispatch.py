"""Document loader dispatch and fallback policy."""

import hashlib
import logging
from pathlib import Path

from langchain_core.documents import Document

from app.core.config import get_settings
from app.ingestion.loaders.image_loader import load_image_file as _load_image_file
from app.ingestion.loaders.office_loader import (
    OFFICE_EXTENSIONS,
    load_office_document,
    parsed_to_documents,
)
from app.ingestion.loaders.pdf_loader import (
    load_pdf_enhanced as _load_pdf_enhanced,
)
from app.ingestion.loaders.pdf_loader import (
    load_pdf_image_ocr as _load_pdf_image_ocr,
)
from app.ingestion.loaders.pdf_loader import (
    load_pdf_text as _load_pdf_text,
)
from app.ingestion.loaders.pdf_loader import (
    load_pdf_with_docling as _load_pdf_with_docling,
)
from app.ingestion.loaders.text_loader import load_text_file as _load_text_file
from app.services.evidence.models import EvidenceDocument, ParsedDocument, ParsedPage, TextBlock

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml", ".toml", ".ini"}
SUPPORTED_EXTENSIONS = {".pdf", *IMAGE_EXTENSIONS, *TEXT_EXTENSIONS, *OFFICE_EXTENSIONS}

# Backward-compatible aliases used by tests and older call sites.
load_image_file = _load_image_file
load_pdf_enhanced = _load_pdf_enhanced
load_pdf_image_ocr = _load_pdf_image_ocr
load_pdf_text = _load_pdf_text
load_pdf_with_docling = _load_pdf_with_docling
load_text_file = _load_text_file


def _extract_charts_once(path: Path, settings) -> list[Document]:
    """Extract charts from PDF exactly once."""
    try:
        from app.ingestion.loaders.pdf_chart_loader import extract_charts_from_pdf

        chart_docs = extract_charts_from_pdf(path, use_vision=True, vision_model=settings.pdf_chart_vision_model)
        if chart_docs:
            logger.info(f"Extracted {len(chart_docs)} charts from {path.name}")
        return chart_docs
    except Exception as e:
        logger.error(f"Chart extraction failed for {path.name}: {e}")
        return []


def _load_pdf_with_mode(path: Path, pdf_mode: str, settings) -> list[Document]:
    """Load PDF text content with fallback chain (no chart extraction)."""
    if pdf_mode == "docling_advanced":
        try:
            from app.ingestion.loaders.pdf_loader_advanced import load_pdf_advanced

            advanced_docs = load_pdf_advanced(
                path,
                by_page=True,
                enable_structure=settings.pdf_enable_structure_analysis,
                enable_coreference=settings.pdf_enable_coreference,
                enable_formula_enrichment=settings.pdf_enable_formula_enrichment,
                enable_cleaning=settings.pdf_enable_cleaning,
                enable_table_merging=settings.pdf_enable_table_merging,
            )
            if advanced_docs:
                logger.info(f"Loaded {path.name} with advanced processing")
                return advanced_docs
        except Exception as e:
            logger.warning(f"Advanced processing failed for {path.name}: {e}")

        enhanced_docs = _load_pdf_enhanced(
            path,
            by_page=True,
            enable_cleaning=settings.pdf_enable_cleaning,
            enable_table_merging=settings.pdf_enable_table_merging,
        )
        if enhanced_docs:
            logger.info(f"Loaded {path.name} with enhanced processing (fallback)")
            return enhanced_docs

        logger.warning(f"Using pypdf fallback for {path.name}")
        return _load_pdf_text(path)

    if pdf_mode == "docling_enhanced":
        enhanced_docs = _load_pdf_enhanced(
            path,
            by_page=True,
            enable_cleaning=settings.pdf_enable_cleaning,
            enable_table_merging=settings.pdf_enable_table_merging,
            enable_nested_table_handling=True,
        )
        if enhanced_docs:
            logger.info(f"Loaded {path.name} with enhanced processing")
            return enhanced_docs

        docling_docs = _load_pdf_with_docling(path, by_page=True)
        if docling_docs:
            logger.info(f"Loaded {path.name} with docling (fallback)")
            return docling_docs

        logger.warning(f"Using pypdf fallback for {path.name}")
        return _load_pdf_text(path)

    if pdf_mode == "docling":
        docling_docs = _load_pdf_with_docling(path, by_page=True)
        if docling_docs:
            logger.info(f"Loaded {path.name} with docling")
            return docling_docs

        logger.warning(f"Using pypdf fallback for {path.name}")
        return _load_pdf_text(path)

    if pdf_mode == "hybrid":
        docling_docs = _load_pdf_with_docling(path, by_page=True)
        ocr_docs = _load_pdf_image_ocr(path)
        if docling_docs:
            logger.info(f"Loaded {path.name} with hybrid mode (docling + OCR)")
            return docling_docs + ocr_docs

        logger.warning(f"Using pypdf + OCR fallback for {path.name}")
        text_docs = _load_pdf_text(path)
        return text_docs + ocr_docs

    logger.info(f"Loaded {path.name} with pypdf mode")
    text_docs = _load_pdf_text(path)
    ocr_docs = _load_pdf_image_ocr(path)
    return text_docs + ocr_docs


def _load_single_path(path: Path) -> list[Document]:
    """Load documents from a single file path."""
    if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return []

    suffix = path.suffix.lower()
    if suffix in OFFICE_EXTENSIONS:
        return parsed_to_documents(load_parsed_document(path))
    if suffix == ".pdf":
        settings = get_settings()
        pdf_mode = settings.pdf_loader_mode.lower()
        text_docs = _load_pdf_with_mode(path, pdf_mode, settings)
        if text_docs and settings.pdf_enable_chart_extraction:
            chart_docs = _extract_charts_once(path, settings)
            return text_docs + chart_docs
        return text_docs

    if suffix in IMAGE_EXTENSIONS:
        return _load_image_file(path)

    return _load_text_file(path)


def load_parsed_document(path: Path, metadata: dict[str, object] | None = None) -> ParsedDocument:
    """Normalize every supported file into one versioned parsed-document contract."""

    parsed, _ = load_document_with_evidence(path, metadata)
    return parsed


def load_document_with_evidence(
    path: Path,
    metadata: dict[str, object] | None = None,
) -> tuple[ParsedDocument, list[Document]]:
    """Parse once and return both canonical evidence and legacy LangChain documents."""

    values = dict(metadata or {})
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    document = EvidenceDocument(
        document_id=str(values.get("document_id") or f"doc-{digest[:24]}"),
        version=int(values.get("version", 1) or 1),
        tenant_id=str(values.get("tenant_id") or values.get("owner_user_id") or "shared"),
        source=str(values.get("source") or path),
        filename=path.name,
        sha256=digest,
        owner_user_id=str(values.get("owner_user_id") or ""),
        visibility=str(values.get("visibility") or "private"),
        acl_tags=tuple(str(value) for value in values.get("acl_tags", ()) or ()),
    )
    if path.suffix.lower() in OFFICE_EXTENSIONS:
        parsed = load_office_document(path, document)
        return parsed, parsed_to_documents(parsed)
    documents = _load_single_path(path)
    pages = []
    blocks = []
    for index, loaded in enumerate(documents, start=1):
        raw_page = (loaded.metadata or {}).get("page", index)
        try:
            page = max(1, int(raw_page))
        except (TypeError, ValueError):
            page = index
        text = str(loaded.page_content or "")
        pages.append(ParsedPage(page=page, text=text))
        if text.strip():
            blocks.append(TextBlock(block_id=f"block-{digest[:16]}-{index}", page=page, text=text))
    parser = str((documents[0].metadata or {}).get("converter", "legacy")) if documents else "legacy"
    fallback_chain = [parser]
    if path.suffix.lower() == ".pdf":
        requested = str(get_settings().pdf_loader_mode or "pypdf").lower()
        fallback_chain = list(dict.fromkeys((f"requested:{requested}", parser)))
    parsed = ParsedDocument(
        document=document,
        pages=tuple(pages),
        text_blocks=tuple(blocks),
        parser=parser,
        fallback_chain=tuple(fallback_chain),
    )
    canonical = {
        "source": document.source,
        "filename": document.filename,
        "document_id": document.document_id,
        "version": document.version,
        "tenant_id": document.tenant_id,
        "owner_user_id": document.owner_user_id,
        "visibility": document.visibility,
        "acl_tags": ",".join(document.acl_tags),
        "parser": parser,
    }
    for loaded in documents:
        loaded.metadata = {**(loaded.metadata or {}), **canonical}
    return parsed, documents


def load_documents(data_dir: Path | None = None, paths: list[Path] | None = None) -> list[Document]:
    """Load documents from directory or specific paths."""
    docs: list[Document] = []
    if paths is not None:
        for path in paths:
            docs.extend(_load_single_path(path))
        return docs

    if data_dir is None:
        return docs

    for path in data_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        docs.extend(_load_single_path(path))
    return docs


__all__ = [
    "load_documents",
    "IMAGE_EXTENSIONS",
    "TEXT_EXTENSIONS",
    "SUPPORTED_EXTENSIONS",
    "load_parsed_document",
    "load_document_with_evidence",
]
