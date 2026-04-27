"""PDF document loader."""

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


def load_pdf_text(path: Path) -> list[Document]:
    """Load text content from PDF using PyPDFLoader."""
    loader = PyPDFLoader(str(path))
    return loader.load()


def load_pdf_image_ocr(path: Path) -> list[Document]:
    """Extract and OCR images from PDF pages."""
    try:
        from pypdf import PdfReader
    except Exception:
        return []

    from app.ingestion.utils.ocr_utils import ocr_image_bytes

    docs: list[Document] = []
    try:
        reader = PdfReader(str(path))
    except Exception:
        return docs

    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            images = list(page.images or [])
        except Exception:
            images = []
        for img_idx, img_obj in enumerate(images, start=1):
            img_bytes = getattr(img_obj, "data", None)
            if not img_bytes:
                continue
            docs.extend(ocr_image_bytes(img_bytes, source=path, page=page_idx, image_index=img_idx))
    return docs
