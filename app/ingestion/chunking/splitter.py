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


def split_documents_enhanced(
    documents: list[Any],
    enable_classification: bool = True,
    enable_metadata_enhancement: bool = True,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """
    Enhanced document splitting with intelligent classification and metadata enhancement

    Args:
        documents: List of documents
        enable_classification: Enable chunk classification
        enable_metadata_enhancement: Enable metadata enhancement

    Returns:
        (child_chunks, parent_records)
    """
    settings = get_settings()

    child_chunks = []
    parent_records: list[dict[str, Any]] = []

    for doc_idx, doc in enumerate(documents):
        base_metadata = dict(getattr(doc, "metadata", {}) or {})
        raw_text = str(getattr(doc, "page_content", "") or "").strip()
        if not raw_text:
            continue

        source = str(base_metadata.get("source", "") or "")
        doc_type = base_metadata.get("doc_type") or base_metadata.get("file_type")
        language = base_metadata.get("language", "mixed")

        # 智能选择分隔符
        separators = get_smart_separators(doc_type, language)

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

        parent_texts = parent_splitter.split_text(raw_text) or [raw_text]
        total_parents = len(parent_texts)

        for parent_idx, parent_text in enumerate(parent_texts):
            parent_text = (parent_text or "").strip()
            if not parent_text:
                continue

            # 生成parent ID
            if source:
                text_hash = hashlib.sha1(parent_text.encode("utf-8")).hexdigest()[:12]
                parent_seed = f"{source}|{doc_idx}|{parent_idx}|{text_hash}"
                parent_id = f"parent-{hashlib.sha1(parent_seed.encode('utf-8')).hexdigest()[:16]}"
            else:
                parent_id = f"parent-{doc_idx}-{parent_idx}-{uuid.uuid4().hex[:8]}"

            parent_meta = dict(base_metadata)
            parent_meta.update({"parent_id": parent_id, "parent_index": parent_idx})

            # Parent元数据增强
            if enable_metadata_enhancement:
                prev_parent = parent_texts[parent_idx - 1] if parent_idx > 0 else None
                next_parent = parent_texts[parent_idx + 1] if parent_idx < total_parents - 1 else None
                parent_meta = enhance_chunk_metadata(
                    parent_text, parent_meta, parent_idx, total_parents, prev_parent, next_parent
                )

            parent_records.append({"id": parent_id, "text": parent_text, "metadata": parent_meta})

            # 切分子chunks
            child_texts = child_splitter.split_text(parent_text) or [parent_text]
            total_children = len(child_texts)

            for child_idx, child_text in enumerate(child_texts):
                child_text = (child_text or "").strip()
                if not child_text:
                    continue

                metadata = dict(base_metadata)
                metadata["parent_id"] = parent_id
                metadata["parent_index"] = parent_idx
                metadata["child_index"] = child_idx

                # Child元数据增强
                if enable_metadata_enhancement:
                    prev_child = child_texts[child_idx - 1] if child_idx > 0 else None
                    next_child = child_texts[child_idx + 1] if child_idx < total_children - 1 else None
                    metadata = enhance_chunk_metadata(
                        child_text, metadata, child_idx, total_children, prev_child, next_child
                    )

                child_chunks.append(_clone_document(doc, text=child_text, metadata=metadata))

    return child_chunks, parent_records


def split_documents(documents: list[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    """Backward compatible document splitting."""
    return split_documents_enhanced(documents, True, True)
