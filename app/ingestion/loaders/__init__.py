"""Document loaders by file type."""

from app.ingestion.loaders.pdf_loader import load_pdf_text, load_pdf_image_ocr
from app.ingestion.loaders.image_loader import load_image_file
from app.ingestion.loaders.text_loader import load_text_file

__all__ = [
    "load_pdf_text",
    "load_pdf_image_ocr",
    "load_image_file",
    "load_text_file",
]
