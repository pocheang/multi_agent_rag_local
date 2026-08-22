"""Backward-compatible facade for enhanced ingestion chunking.

Canonical implementations live under app.ingestion.chunking.
"""

from app.ingestion.chunking.classification import (
    ChunkType,
    classify_chunk_type,
)
from app.ingestion.chunking.metadata import (
    calculate_importance_score,
    enhance_chunk_metadata,
    extract_entities,
    extract_keywords,
)
from app.ingestion.chunking.splitter import (
    get_smart_separators,
    split_documents,
    split_documents_enhanced,
)

__all__ = [
    "ChunkType",
    "calculate_importance_score",
    "classify_chunk_type",
    "enhance_chunk_metadata",
    "extract_entities",
    "extract_keywords",
    "get_smart_separators",
    "split_documents",
    "split_documents_enhanced",
]
