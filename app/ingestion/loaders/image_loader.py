"""Image file loader with OCR."""

from pathlib import Path

from langchain_core.documents import Document

from app.ingestion.utils.ocr_utils import ocr_image_bytes


def load_image_file(path: Path) -> list[Document]:
    """Load and OCR an image file."""
    try:
        img_bytes = path.read_bytes()
    except Exception:
        return []
    return ocr_image_bytes(img_bytes, source=path)
