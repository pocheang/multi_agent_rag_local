"""Document loaders by file type."""

from pathlib import Path

from langchain_core.documents import Document

from app.ingestion.loaders.pdf_loader import load_pdf_text, load_pdf_image_ocr
from app.ingestion.loaders.image_loader import load_image_file
from app.ingestion.loaders.text_loader import load_text_file

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml", ".toml", ".ini"}
SUPPORTED_EXTENSIONS = {".pdf", *IMAGE_EXTENSIONS, *TEXT_EXTENSIONS}


def _load_single_path(path: Path) -> list[Document]:
    """Load a single supported file into LangChain documents."""
    if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return []
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return load_pdf_text(path) + load_pdf_image_ocr(path)
    if suffix in IMAGE_EXTENSIONS:
        return load_image_file(path)
    return load_text_file(path)


def load_documents(data_dir: Path | None = None, paths: list[Path] | None = None) -> list[Document]:
    """Compatibility loader used by ingestion services."""
    docs: list[Document] = []
    if paths is not None:
        for path in paths:
            docs.extend(_load_single_path(path))
        return docs
    if data_dir is None:
        return docs
    for path in data_dir.rglob("*"):
        docs.extend(_load_single_path(path))
    return docs

__all__ = [
    "load_documents",
    "load_pdf_text",
    "load_pdf_image_ocr",
    "load_image_file",
    "load_text_file",
    "IMAGE_EXTENSIONS",
    "TEXT_EXTENSIONS",
    "SUPPORTED_EXTENSIONS",
]
