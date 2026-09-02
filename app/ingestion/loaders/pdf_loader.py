"""PDF document loader."""

import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def load_pdf_text(path: Path) -> list[Document]:
    """Load text content from PDF using PyPDFLoader."""
    try:
        loader = PyPDFLoader(str(path))
        return loader.load()
    except Exception as e:
        logger.exception(f"PyPDF loading failed for {path.name}: {e}")
        return []


def load_pdf_enhanced(
    path: Path,
    by_page: bool = True,
    enable_cleaning: bool = True,
    enable_table_merging: bool = True,
    enable_nested_table_handling: bool = True,
) -> list[Document]:
    """Load PDF with enhanced processing, forwarding the processing switches.

    This wrapper took only `path` and `by_page` and forwarded only those, while
    `dispatch.py` called it with `enable_cleaning`, `enable_table_merging` and
    `enable_nested_table_handling` -- so `PDF_LOADER_MODE=docling_enhanced` and
    `docling_advanced` raised `TypeError` on the first PDF, and
    `PDF_ENABLE_CLEANING` / `PDF_ENABLE_TABLE_MERGING` were settings nothing
    could act on. The implementation underneath has supported all three from the
    start (`pdf_loader_enhanced.load_pdf_enhanced`), and `pdf_loader_advanced`
    calls it that way directly; only this forwarding layer dropped them.

    Note what the fallbacks cannot carry: `load_pdf_with_docling` has no such
    switches, so a deployment that loses the enhanced loader silently gets
    unprocessed output. That is a narrower version of the same problem and is
    logged rather than hidden.
    """

    try:
        from app.ingestion.loaders.pdf_loader_enhanced import load_pdf_enhanced as _load_enhanced

        return _load_enhanced(
            path,
            by_page,
            enable_cleaning=enable_cleaning,
            enable_table_merging=enable_table_merging,
            enable_nested_table_handling=enable_nested_table_handling,
        )
    except ImportError as e:
        logger.warning("Enhanced loader not available (%s); falling back to docling without cleaning", e)
        return load_pdf_with_docling(path, by_page)
    except Exception as e:
        logger.exception(f"Enhanced loading failed for {path.name}: {e}")
        logger.warning("Falling back to docling for %s; cleaning and table merging will not run", path.name)
        return load_pdf_with_docling(path, by_page)


def load_pdf_with_docling(path: Path, by_page: bool = True) -> list[Document]:
    """Load PDF using Docling with Markdown conversion (preserves tables)."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as e:
        logger.warning(f"Docling not available: {e}")
        return []

    try:
        converter = DocumentConverter()
        result = converter.convert(str(path))

        if not by_page:
            markdown_content = result.document.export_to_markdown()
            return [
                Document(
                    page_content=markdown_content,
                    metadata={
                        "source": str(path),
                        "format": "markdown",
                        "converter": "docling",
                    },
                )
            ]

        docs: list[Document] = []
        for page_idx, page in enumerate(result.document.pages, start=1):
            page_markdown = page.export_to_markdown()
            if page_markdown and page_markdown.strip():
                docs.append(
                    Document(
                        page_content=page_markdown,
                        metadata={
                            "source": str(path),
                            "page": page_idx,
                            "format": "markdown",
                            "converter": "docling",
                        },
                    )
                )

        if not docs:
            logger.warning(f"No content extracted from {path.name} using Docling")
        return docs
    except Exception as e:
        logger.exception(f"Docling conversion failed for {path.name}: {e}")
        return []


def load_pdf_image_ocr(path: Path) -> list[Document]:
    """Extract and OCR images from PDF pages."""
    try:
        from pypdf import PdfReader
    except ImportError as e:
        logger.warning(f"pypdf not available for image OCR: {e}")
        return []

    from app.ingestion.extraction.ocr_enhanced import ocr_image_bytes_with_structure

    docs: list[Document] = []
    try:
        reader = PdfReader(str(path))
    except Exception as e:
        logger.warning(f"Failed to read PDF for image OCR {path}: {e}")
        return docs

    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            images = list(page.images or [])
        except (AttributeError, TypeError) as e:
            logger.debug(f"Failed to extract images from page {page_idx}: {e}")
            images = []
        for img_idx, img_obj in enumerate(images, start=1):
            img_bytes = getattr(img_obj, "data", None)
            if not img_bytes:
                continue
            docs.extend(ocr_image_bytes_with_structure(img_bytes, source=path, page=page_idx, image_index=img_idx))
    return docs
