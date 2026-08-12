"""Document loader dispatch and fallback policy."""

import logging
from pathlib import Path

from langchain_core.documents import Document

from app.core.config import get_settings
from app.ingestion.loaders.image_loader import load_image_file as _load_image_file
from app.ingestion.loaders.pdf_loader import (
    load_pdf_enhanced as _load_pdf_enhanced,
    load_pdf_image_ocr as _load_pdf_image_ocr,
    load_pdf_text as _load_pdf_text,
    load_pdf_with_docling as _load_pdf_with_docling,
)
from app.ingestion.loaders.text_loader import load_text_file as _load_text_file

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml", ".toml", ".ini"}
SUPPORTED_EXTENSIONS = {".pdf", *IMAGE_EXTENSIONS, *TEXT_EXTENSIONS}

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
]
