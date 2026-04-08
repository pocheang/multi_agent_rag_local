from io import BytesIO
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

from app.core.config import get_settings

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", *IMAGE_EXTENSIONS}


def _load_pdf_text(path: Path) -> list[Document]:
    loader = PyPDFLoader(str(path))
    return loader.load()


def _load_pdf_image_ocr(path: Path) -> list[Document]:
    try:
        from pypdf import PdfReader
    except Exception:
        return []

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
            docs.extend(_ocr_image_bytes(img_bytes, source=path, page=page_idx, image_index=img_idx))
    return docs


def _ocr_image_bytes(img_bytes: bytes, source: Path, page: int | None = None, image_index: int | None = None) -> list[Document]:
    try:
        from PIL import Image
    except Exception:
        return []

    try:
        image = Image.open(BytesIO(img_bytes))
    except Exception:
        return []

    width, height = image.size
    mode = image.mode or "unknown"
    file_format = (image.format or "unknown").lower()
    summary = f"[image_meta] format={file_format}; mode={mode}; size={width}x{height}."

    metadata = {
        "source": str(source),
        "modality": "image_ocr",
        "width": width,
        "height": height,
        "image_mode": mode,
        "image_format": file_format,
    }
    if page is not None:
        metadata["page"] = page
    if image_index is not None:
        metadata["image_index"] = image_index

    try:
        import pytesseract
    except Exception:
        content = f"{summary}\n[image_ocr_error]\npytesseract not installed"
        return [Document(page_content=content, metadata=metadata)]

    ocr_text = ""
    settings = get_settings()
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    try:
        ocr_text = (pytesseract.image_to_string(image, lang=settings.tesseract_lang or "chi_sim+eng") or "").strip()
    except Exception:
        try:
            ocr_text = (pytesseract.image_to_string(image) or "").strip()
        except Exception:
            ocr_text = ""

    if not ocr_text:
        content = f"{summary}\n[image_ocr_error]\nOCR engine unavailable or language data missing"
        return [Document(page_content=content, metadata=metadata)]

    content = f"{summary}\n[image_ocr]\n{ocr_text}"

    return [Document(page_content=content, metadata=metadata)]


def _load_image_file(path: Path) -> list[Document]:
    try:
        img_bytes = path.read_bytes()
    except Exception:
        return []
    return _ocr_image_bytes(img_bytes, source=path)


def _load_single_path(path: Path) -> list[Document]:
    if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return []

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text_docs = _load_pdf_text(path)
        ocr_docs = _load_pdf_image_ocr(path)
        return text_docs + ocr_docs

    if suffix in IMAGE_EXTENSIONS:
        return _load_image_file(path)

    loader = TextLoader(str(path), encoding="utf-8")
    return loader.load()


def load_documents(data_dir: Path | None = None, paths: list[Path] | None = None) -> list[Document]:
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
