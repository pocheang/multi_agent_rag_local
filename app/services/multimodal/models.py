"""Data models for multi-modal content."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ImageContent:
    """Image content with metadata."""

    image_id: str
    doc_id: str
    page_number: int
    image_data: bytes
    description: str  # GPT-4V generated
    ocr_text: str | None = None  # OCR result
    bbox: tuple[float, float, float, float] | None = None  # (x, y, w, h)
    image_type: str = "unknown"  # diagram|chart|photo|screenshot
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)
    tenant_id: str = "shared"
    owner_user_id: str = ""
    # Fail closed: an image whose visibility nobody set is nobody's to read
    # but its owner's.
    visibility: str = "private"
    version: int = 1
    artifact_uri: str | None = None
    masked_artifact_uri: str | None = None
    masked_image_data: bytes | None = field(default=None, repr=False)
    embedding_model: str | None = None
    visual_embedding: tuple[float, ...] = field(default_factory=tuple, repr=False)

    @property
    def document_id(self) -> str:
        """Canonical name while retaining the existing ``doc_id`` attribute."""

        return self.doc_id


@dataclass
class TableContent:
    """Table content with structured data."""

    table_id: str
    doc_id: str
    page_number: int
    headers: list[str]
    rows: list[list[Any]]
    summary: str
    bbox: tuple[float, float, float, float] | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChartContent:
    """Chart/graph content with extracted data."""

    chart_id: str
    doc_id: str
    page_number: int
    chart_type: str  # bar|line|pie|scatter|area|etc
    title: str | None = None
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)  # Extracted chart data
    bbox: tuple[float, float, float, float] | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentChunk:
    """Smart document chunk with multi-modal content."""

    chunk_id: str
    doc_id: str
    heading: str | None = None
    text_content: str = ""
    page_numbers: list[int] = field(default_factory=list)
    images: list[ImageContent] = field(default_factory=list)
    tables: list[TableContent] = field(default_factory=list)
    charts: list[ChartContent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def has_multimodal_content(self) -> bool:
        """Check if chunk contains multi-modal content."""
        return bool(self.images or self.tables or self.charts)

    @property
    def modality_types(self) -> list[str]:
        """Get list of modalities present in this chunk."""
        types = []
        if self.text_content:
            types.append("text")
        if self.images:
            types.append("image")
        if self.tables:
            types.append("table")
        if self.charts:
            types.append("chart")
        return types
