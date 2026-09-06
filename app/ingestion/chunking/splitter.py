"""Canonical document splitting and separator selection."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None  # type: ignore[assignment]

from app.core.config import get_settings

from .metadata import enhance_chunk_metadata

# ============================================================================
# 智能分隔符选择
# ============================================================================


def get_smart_separators(doc_type: str | None = None, language: str = "mixed") -> list[str]:
    """
    Select smart separators based on document type and language

    Args:
        doc_type: Document type (markdown, code, pdf, etc.)
        language: Language (zh, en, mixed)

    Returns:
        List of separators (ordered by priority)
    """
    # Markdown文档
    if doc_type == "markdown":
        return [
            "\n## ",  # 二级标题
            "\n### ",  # 三级标题
            "\n\n",  # 段落
            "\n- ",  # 列表项
            "\n* ",  # 列表项
            "\n1. ",  # 数字列表
            "\n",  # 换行
            ". ",  # 句子
            " ",  # 空格
            "",  # 字符
        ]

    # 代码文档
    if doc_type == "code":
        return [
            "\nclass ",  # 类定义
            "\ndef ",  # 函数定义
            "\n\n",  # 空行
            "\n",  # 换行
            ";",  # 语句结束
            " ",  # 空格
            "",  # 字符
        ]

    # PDF文档（可能包含多列）
    if doc_type == "pdf":
        if language == "zh":
            return [
                "\n\n",  # 段落
                "。\n",  # 句号+换行
                "。",  # 句号
                "；",  # 分号
                "，",  # 逗号
                "\n",  # 换行
                " ",  # 空格
                "",  # 字符
            ]
        else:
            return [
                "\n\n",  # 段落
                ". \n",  # 句号+换行
                ". ",  # 句号
                "; ",  # 分号
                ", ",  # 逗号
                "\n",  # 换行
                " ",  # 空格
                "",  # 字符
            ]

    # 默认：混合语言
    return [
        "\n\n",  # 段落
        "。\n",  # 中文句号+换行
        ". \n",  # 英文句号+换行
        "。",  # 中文句号
        ". ",  # 英文句号
        "！",  # 感叹号
        "？",  # 问号
        "；",  # 分号
        "\n",  # 换行
        " ",  # 空格
        "",  # 字符
    ]


# ============================================================================
# 优化的文档切分函数
# ============================================================================


def _clone_document(doc: Any, text: str, metadata: dict[str, Any]):
    """Clone document object"""
    cls = doc.__class__
    return cls(page_content=text, metadata=metadata)


def _sanitize_chunk_params(chunk_size: int, chunk_overlap: int) -> tuple[int, int]:
    """Sanitize chunk parameters"""
    size = max(1, int(chunk_size))
    overlap = max(0, int(chunk_overlap))
    if overlap >= size:
        overlap = min(size - 1, size // 5)
    return size, overlap


class _SimpleTextSplitter:
    """Simple text splitter (fallback)"""

    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.chunk_size, self.chunk_overlap = _sanitize_chunk_params(chunk_size, chunk_overlap)

    def split_text(self, text: str) -> list[str]:
        source = str(text or "")
        if not source:
            return []
        if len(source) <= self.chunk_size:
            return [source]
        step = max(1, self.chunk_size - self.chunk_overlap)
        out: list[str] = []
        i = 0
        while i < len(source):
            out.append(source[i : i + self.chunk_size])
            if i + self.chunk_size >= len(source):
                break
            i += step
        return out


def _build_splitter(chunk_size: int, chunk_overlap: int, separators: list[str]):
    """Build text splitter"""
    size, overlap = _sanitize_chunk_params(chunk_size, chunk_overlap)
    if RecursiveCharacterTextSplitter is None:
        return _SimpleTextSplitter(chunk_size=size, chunk_overlap=overlap)
    return RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=separators,
    )


def _neighbours(texts: list[str], index: int) -> tuple[str | None, str | None]:
    """The raw chunks either side of `index`, for `enhance_chunk_metadata`.

    Raw, not stripped: the caller strips the chunk it is describing, and the
    neighbours are read from the splitter's own output. The two are different
    strings whenever a chunk begins or ends on whitespace, so this is a property
    of the original and not an oversight to tidy up.
    """
    previous = texts[index - 1] if index > 0 else None
    following = texts[index + 1] if index < len(texts) - 1 else None
    return previous, following


def _parent_id(identity: str, doc_idx: int, parent_idx: int, parent_text: str) -> str:
    """Stable across re-ingests when the document has an identity, random when not.

    `identity` is `{document_id}|v{version}` where both are present and the source
    path otherwise; with neither, there is nothing to be stable against and a
    uuid4 is the honest answer.
    """
    if not identity:
        return f"parent-{doc_idx}-{parent_idx}-{uuid.uuid4().hex[:8]}"
    text_hash = hashlib.sha1(parent_text.encode("utf-8")).hexdigest()[:12]
    parent_seed = f"{identity}|{doc_idx}|{parent_idx}|{text_hash}"
    return f"parent-{hashlib.sha1(parent_seed.encode('utf-8')).hexdigest()[:16]}"


def _split_parent(
    doc: Any,
    parent_text: str,
    splitter: Any,
    *,
    base_metadata: dict[str, Any],
    parent_id: str,
    parent_idx: int,
    enhance: bool,
) -> list[Any]:
    """The child chunks of one parent, each carrying its parent linkage."""
    child_texts = splitter.split_text(parent_text) or [parent_text]
    total_children = len(child_texts)
    children: list[Any] = []

    for child_idx, raw_child in enumerate(child_texts):
        child_text = (raw_child or "").strip()
        if not child_text:
            continue

        metadata = dict(base_metadata)
        metadata["parent_id"] = parent_id
        metadata["parent_index"] = parent_idx
        metadata["child_index"] = child_idx

        if enhance:
            metadata = enhance_chunk_metadata(
                child_text, metadata, child_idx, total_children, *_neighbours(child_texts, child_idx)
            )

        children.append(_clone_document(doc, text=child_text, metadata=metadata))

    return children


def _split_document(
    doc: Any,
    doc_idx: int,
    *,
    settings: Any,
    enhance: bool,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """One document's child chunks and parent records, in order.

    Note that a blank chunk is skipped but still *counts*: `child_idx`,
    `parent_idx` and the totals handed to `enhance_chunk_metadata` are positions
    in the splitter's output, not in the kept subset. Renumbering them would
    change what "chunk 3 of 7" means to every consumer of that metadata.
    """
    base_metadata = dict(getattr(doc, "metadata", {}) or {})
    raw_text = str(getattr(doc, "page_content", "") or "").strip()
    if not raw_text:
        return [], []

    # 智能选择分隔符
    separators = get_smart_separators(
        base_metadata.get("doc_type") or base_metadata.get("file_type"),
        base_metadata.get("language", "mixed"),
    )
    parent_splitter = _build_splitter(
        chunk_size=settings.parent_chunk_size,
        chunk_overlap=settings.parent_chunk_overlap,
        separators=separators,
    )
    child_splitter = _build_splitter(
        chunk_size=settings.child_chunk_size,
        chunk_overlap=settings.child_chunk_overlap,
        separators=separators,
    )

    document_id = str(base_metadata.get("document_id", "") or "")
    version = str(base_metadata.get("version", "") or "")
    identity = f"{document_id}|v{version}" if document_id and version else str(base_metadata.get("source", "") or "")

    parent_texts = parent_splitter.split_text(raw_text) or [raw_text]
    total_parents = len(parent_texts)
    children: list[Any] = []
    records: list[dict[str, Any]] = []

    for parent_idx, raw_parent in enumerate(parent_texts):
        parent_text = (raw_parent or "").strip()
        if not parent_text:
            continue

        parent_id = _parent_id(identity, doc_idx, parent_idx, parent_text)
        parent_meta = dict(base_metadata)
        parent_meta.update({"parent_id": parent_id, "parent_index": parent_idx})

        if enhance:
            parent_meta = enhance_chunk_metadata(
                parent_text, parent_meta, parent_idx, total_parents, *_neighbours(parent_texts, parent_idx)
            )

        records.append({"id": parent_id, "text": parent_text, "metadata": parent_meta})
        children.extend(
            _split_parent(
                doc,
                parent_text,
                child_splitter,
                base_metadata=base_metadata,
                parent_id=parent_id,
                parent_idx=parent_idx,
                enhance=enhance,
            )
        )

    return children, records


def split_documents_enhanced(
    documents: list[Any],
    enable_metadata_enhancement: bool = True,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """
    Enhanced document splitting with intelligent classification and metadata enhancement

    Args:
        documents: List of documents
        enable_metadata_enhancement: Enable metadata enhancement, which is also
            what performs chunk classification -- `enhance_chunk_metadata` calls
            `classify_chunk_type`. There used to be a separate
            `enable_classification` parameter here, documented as "Enable chunk
            classification" and read by nothing: passing False left classification
            running, and only this switch ever turned it off.

    Returns:
        (child_chunks, parent_records)
    """
    settings = get_settings()
    child_chunks: list[Any] = []
    parent_records: list[dict[str, Any]] = []

    for doc_idx, doc in enumerate(documents):
        children, records = _split_document(doc, doc_idx, settings=settings, enhance=enable_metadata_enhancement)
        child_chunks.extend(children)
        parent_records.extend(records)

    return child_chunks, parent_records


def split_documents(documents: list[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    """Backward compatible document splitting."""
    return split_documents_enhanced(documents, enable_metadata_enhancement=True)
