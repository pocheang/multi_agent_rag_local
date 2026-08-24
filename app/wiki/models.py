"""Immutable derived-knowledge contracts with original evidence mappings."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WikiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WikiSourceReference(WikiModel):
    source: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    document_version: int = Field(ge=1)
    page: int | None = Field(default=None, ge=1)
    chunk_id: str | None = None
    image_id: str | None = None
    acl_tags: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("source", "document_id")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source reference identifiers must not be blank")
        return value


class WikiArticleVersion(WikiModel):
    tenant_id: str = Field(min_length=1)
    article_id: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    version: int = Field(ge=1)
    content_hash: str = Field(min_length=64, max_length=64)
    source_references: tuple[WikiSourceReference, ...] = Field(min_length=1)
    change_note: str = Field(min_length=1)
    created_at: str = Field(min_length=1)


class WikiVersionSummary(WikiModel):
    article_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    content_hash: str = Field(min_length=64, max_length=64)
    change_note: str = Field(min_length=1)
    created_at: str = Field(min_length=1)


class WikiDiff(WikiModel):
    article_id: str = Field(min_length=1)
    from_version: int = Field(ge=1)
    to_version: int = Field(ge=1)
    unified_diff: str


__all__ = ["WikiArticleVersion", "WikiDiff", "WikiSourceReference", "WikiVersionSummary"]
