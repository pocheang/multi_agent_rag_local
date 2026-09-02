"""Image file loader with OCR."""

import logging
from pathlib import Path

from langchain_core.documents import Document

from app.ingestion.extraction.ocr import ocr_image_bytes

logger = logging.getLogger(__name__)


def load_image_file(path: Path) -> list[Document]:
    """Load and OCR an image file."""
    try:
        img_bytes = path.read_bytes()
    except OSError as e:
        logger.warning(f"Failed to read image file {path}: {e}")
        return []
    return ocr_image_bytes(img_bytes, source=path)
