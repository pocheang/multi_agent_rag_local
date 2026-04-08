import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings

if TYPE_CHECKING:
    from langchain_core.documents import Document


def normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in metadata.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            out[k] = str(v)
    return out


def documents_to_records(documents: list["Document"]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for i, doc in enumerate(documents):
        metadata = normalize_metadata(dict(doc.metadata))
        chunk_id = metadata.get("chunk_id") or f"chunk-{i}-{uuid.uuid4().hex[:8]}"
        metadata["chunk_id"] = chunk_id
        records.append({"id": chunk_id, "text": doc.page_content, "metadata": metadata})
    return records


def write_corpus_records(records: list[dict[str, Any]], path: Path | None = None) -> None:
    settings = get_settings()
    target = path or settings.corpus_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_corpus_records(path: Path | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    target = path or settings.corpus_path
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows
