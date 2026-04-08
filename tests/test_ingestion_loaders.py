import importlib
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


@dataclass
class _Doc:
    page_content: str
    metadata: dict = field(default_factory=dict)


class _TextLoader:
    def __init__(self, path: str, encoding: str = "utf-8"):
        self.path = path
        self.encoding = encoding

    def load(self):
        with open(self.path, "r", encoding=self.encoding) as f:
            text = f.read()
        return [_Doc(page_content=text, metadata={"source": self.path})]


class _PdfLoader:
    def __init__(self, path: str):
        self.path = path

    def load(self):
        return [_Doc(page_content="pdf text", metadata={"source": self.path})]


def _install_loader_stubs():
    lc_core = types.ModuleType("langchain_core")
    lc_core_docs = types.ModuleType("langchain_core.documents")
    lc_core_docs.Document = _Doc
    lc_core.documents = lc_core_docs

    lc_comm = types.ModuleType("langchain_community")
    lc_comm_docs = types.ModuleType("langchain_community.document_loaders")
    lc_comm_docs.TextLoader = _TextLoader
    lc_comm_docs.PyPDFLoader = _PdfLoader
    lc_comm.document_loaders = lc_comm_docs

    sys.modules["langchain_core"] = lc_core
    sys.modules["langchain_core.documents"] = lc_core_docs
    sys.modules["langchain_community"] = lc_comm
    sys.modules["langchain_community.document_loaders"] = lc_comm_docs


def _make_tmp_dir(prefix: str) -> Path:
    base = Path("tests/.tmp")
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{prefix}-{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


_install_loader_stubs()
loaders = importlib.import_module("app.ingestion.loaders")


def test_supported_extensions_include_images():
    assert ".pdf" in loaders.SUPPORTED_EXTENSIONS
    assert ".png" in loaders.SUPPORTED_EXTENSIONS
    assert ".jpg" in loaders.SUPPORTED_EXTENSIONS
    assert ".csv" in loaders.SUPPORTED_EXTENSIONS


def test_load_single_path_image_uses_image_loader(monkeypatch):
    tmp_dir = _make_tmp_dir("loaders-image")
    img = tmp_dir / "demo.png"
    img.write_bytes(b"fake")

    monkeypatch.setattr(loaders, "_load_image_file", lambda p: [_Doc(page_content="ocr text", metadata={"source": str(p)})])

    docs = loaders._load_single_path(img)
    assert len(docs) == 1
    assert docs[0].page_content == "ocr text"


def test_load_single_path_pdf_merges_text_and_image_ocr(monkeypatch):
    tmp_dir = _make_tmp_dir("loaders-pdf")
    pdf = tmp_dir / "demo.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(loaders, "_load_pdf_text", lambda p: [_Doc(page_content="pdf text", metadata={"source": str(p)})])
    monkeypatch.setattr(loaders, "_load_pdf_image_ocr", lambda p: [_Doc(page_content="img ocr", metadata={"source": str(p)})])

    docs = loaders._load_single_path(pdf)
    assert [d.page_content for d in docs] == ["pdf text", "img ocr"]


def test_load_documents_skips_unsupported_paths():
    tmp_dir = _make_tmp_dir("loaders-docs")
    ok = tmp_dir / "note.md"
    bad = tmp_dir / "bin.exe"
    ok.write_text("hello", encoding="utf-8")
    bad.write_bytes(b"x")

    docs = loaders.load_documents(paths=[ok, bad])
    assert len(docs) == 1
    assert "hello" in docs[0].page_content


def test_parse_psm_modes_handles_invalid_values():
    assert loaders._parse_psm_modes("6,11,3") == [6, 11, 3]
    assert loaders._parse_psm_modes("a,,99,-1,4") == [4]
    assert loaders._parse_psm_modes("") == [6, 11, 3]


def test_normalize_ocr_text_collapses_blank_lines():
    text = "  a  \n\n b \n   \n c"
    assert loaders._normalize_ocr_text(text) == "a\nb\nc"


def test_text_loader_fallbacks_to_gb18030():
    tmp_dir = _make_tmp_dir("loaders-gb18030")
    txt = tmp_dir / "cn.txt"
    txt.write_bytes("中文内容".encode("gb18030"))

    docs = loaders.load_documents(paths=[txt])
    assert len(docs) == 1
    assert "中文内容" in docs[0].page_content


def test_detect_people_disabled_returns_safe_defaults():
    settings = SimpleNamespace(people_detection_enabled=False, people_detection_mode="face")
    info = loaders._detect_people_in_image(image=None, settings=settings)
    assert info["status"] == "disabled"
    assert info["person_count"] == 0
    assert info["human_present"] is False


def test_build_people_summary_contains_key_fields():
    summary = loaders._build_people_summary(
        {"status": "ok", "human_present": True, "person_count": 2, "face_count": 1, "detector_mode": "face"}
    )
    assert "[image_people]" in summary
    assert "human_present=true" in summary
    assert "person_count=2" in summary


def test_describe_image_with_vision_disabled():
    settings = SimpleNamespace(image_caption_enabled=False, image_caption_backend="auto", model_backend="ollama")
    info = loaders._describe_image_with_vision(b"img", settings)
    assert info["status"] == "disabled"
    assert info["caption"] == ""


def test_build_vision_summary_includes_caption():
    text = loaders._build_vision_summary({"status": "ok", "model": "demo", "caption": "图中有一只猫在窗台上。"})
    assert "[image_scene]" in text
    assert "图中有一只猫在窗台上。" in text
