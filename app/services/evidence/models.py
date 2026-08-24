"""Immutable contracts for parsed, versioned source evidence."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceDocument(EvidenceModel):
    document_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    tenant_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    owner_user_id: str = ""
    visibility: str = "private"
    acl_tags: tuple[str, ...] = Field(default_factory=tuple)


class ParsedPage(EvidenceModel):
    page: int = Field(ge=1)
    sheet: str | None = None
    text: str = ""


class TextBlock(EvidenceModel):
    block_id: str = Field(min_length=1)
    page: int = Field(ge=1)
    text: str
    kind: Literal["text", "heading", "ocr"] = "text"
    sheet: str | None = None


class TableBlock(EvidenceModel):
    table_id: str = Field(min_length=1)
    page: int = Field(ge=1)
    markdown: str
    sheet: str | None = None


class ImageBlock(EvidenceModel):
    image_id: str = Field(min_length=1)
    page: int = Field(ge=1)
    filename: str = Field(min_length=1)
    media_type: str = "application/octet-stream"
    data: bytes = Field(default=b"", exclude=True, repr=False)
    ocr_text: str = ""
    description: str = ""


class ParsedDocument(EvidenceModel):
    document: EvidenceDocument
    pages: tuple[ParsedPage, ...] = Field(default_factory=tuple)
    text_blocks: tuple[TextBlock, ...] = Field(default_factory=tuple)
    tables: tuple[TableBlock, ...] = Field(default_factory=tuple)
    images: tuple[ImageBlock, ...] = Field(default_factory=tuple)
    parser: str = Field(min_length=1)
    fallback_chain: tuple[str, ...] = Field(default_factory=tuple)


class ArtifactRecord(EvidenceModel):
    artifact_id: str = Field(min_length=1)
    kind: Literal["original", "parsed", "image", "masked_image", "manifest"]
    uri: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    media_type: str = "application/octet-stream"
    page: int | None = Field(default=None, ge=1)
    image_id: str | None = None


class EvidenceManifest(EvidenceModel):
    document_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    tenant_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    parser: str = Field(min_length=1)
    fallback_chain: tuple[str, ...] = Field(default_factory=tuple)
    artifacts: tuple[ArtifactRecord, ...] = Field(default_factory=tuple)
    status: Literal["ready", "failed"]
    error_type: str | None = None
    created_at: str = Field(min_length=1)


__all__ = [
    "ArtifactRecord",
    "EvidenceDocument",
    "EvidenceManifest",
    "ImageBlock",
    "ParsedDocument",
    "ParsedPage",
    "TableBlock",
    "TextBlock",
]
