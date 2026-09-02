from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.documents.registry import list_document_records


def _count_field(row: dict[str, Any], field: str) -> int:
    """Read persisted counters defensively for health reporting."""
    try:
        return max(0, int(row.get(field, 0) or 0))
    except (OverflowError, TypeError, ValueError):
        return 0


def build_index_health_report(path: Path | None = None) -> dict[str, Any]:
    rows = list_document_records(path=path)
    ready = [r for r in rows if r.get("status") == "ready"]
    failed = [r for r in rows if r.get("status") == "failed"]
    indexing = [r for r in rows if r.get("status") in {"pending", "indexing"}]
    return {
        "total_documents": len(rows),
        "ready_documents": len(ready),
        "failed_documents": len(failed),
        "indexing_documents": len(indexing),
        "total_chunks": sum(_count_field(r, "chunks_indexed") for r in rows),
        "total_triplets": sum(_count_field(r, "triplets_written") for r in rows),
        "documents": rows,
    }
