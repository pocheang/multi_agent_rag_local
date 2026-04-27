"""Document loaders for various file types.

This module provides a unified interface for loading documents from different file formats.
Supported formats: PDF, images (PNG, JPG, etc.), and text files.
"""

from pathlib import Path

from langchain_core.documents import Document

from app.ingestion.loaders.image_loader import load_image_file
from app.ingestion.loaders.pdf_loader import load_pdf_image_ocr, load_pdf_text
from app.ingestion.loaders.text_loader import load_text_file

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml", ".toml", ".ini"}
SUPPORTED_EXTENSIONS = {".pdf", *IMAGE_EXTENSIONS, *TEXT_EXTENSIONS}


def _load_single_path(path: Path) -> list[Document]:
    """Load documents from a single file path."""
    if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return []

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text_docs = load_pdf_text(path)
        ocr_docs = load_pdf_image_ocr(path)
        return text_docs + ocr_docs

    if suffix in IMAGE_EXTENSIONS:
        return load_image_file(path)

    return load_text_file(path)


def load_documents(data_dir: Path | None = None, paths: list[Path] | None = None) -> list[Document]:
    """Load documents from directory or specific paths.

    Args:
        data_dir: Directory to recursively load documents from
        paths: Specific file paths to load

    Returns:
        List of loaded Document objects
    """
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


# Backward compatibility exports
__all__ = [
    "load_documents",
    "IMAGE_EXTENSIONS",
    "TEXT_EXTENSIONS",
    "SUPPORTED_EXTENSIONS",
]
