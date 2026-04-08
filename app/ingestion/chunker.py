from __future__ import annotations

import uuid
from typing import Any

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception:  # pragma: no cover - optional dependency fallback
    RecursiveCharacterTextSplitter = None  # type: ignore[assignment]

from app.core.config import get_settings


def _clone_document(doc: Any, text: str, metadata: dict[str, Any]):
    cls = doc.__class__
    return cls(page_content=text, metadata=metadata)


class _SimpleTextSplitter:
    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.chunk_size = max(1, int(chunk_size))
        self.chunk_overlap = max(0, int(chunk_overlap))

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
    if RecursiveCharacterTextSplitter is None:
        return _SimpleTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
    )


def split_documents(documents):
    settings = get_settings()
    separators = ["\n\n", "\n", "。", ". ", " ", ""]

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

    child_chunks = []
    parent_records: list[dict[str, Any]] = []

    for doc_idx, doc in enumerate(documents):
        base_metadata = dict(getattr(doc, "metadata", {}) or {})
        raw_text = str(getattr(doc, "page_content", "") or "").strip()
        if not raw_text:
            continue

        parent_texts = parent_splitter.split_text(raw_text) or [raw_text]
        for parent_idx, parent_text in enumerate(parent_texts):
            parent_text = (parent_text or "").strip()
            if not parent_text:
                continue

            parent_id = f"parent-{doc_idx}-{parent_idx}-{uuid.uuid4().hex[:8]}"
            parent_meta = dict(base_metadata)
            parent_meta.update({"parent_id": parent_id, "parent_index": parent_idx})
            parent_records.append({"id": parent_id, "text": parent_text, "metadata": parent_meta})

            child_texts = child_splitter.split_text(parent_text) or [parent_text]
            for child_idx, child_text in enumerate(child_texts):
                child_text = (child_text or "").strip()
                if not child_text:
                    continue
                metadata = dict(base_metadata)
                metadata["parent_id"] = parent_id
                metadata["parent_index"] = parent_idx
                metadata["child_index"] = child_idx
                child_chunks.append(_clone_document(doc, text=child_text, metadata=metadata))

    return child_chunks, parent_records
