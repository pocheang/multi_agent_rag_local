"""Canonical knowledge, provenance, access, and memory value objects."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

KnowledgeSource = Literal[
    "vector",
    "bm25",
    "graph",
    "wiki",
    "memory",
    "multimodal",
    "web",
    "tool",
]
EvidenceLayer = Literal["evidence", "knowledge", "memory", "web", "tool"]
Modality = Literal["text", "table", "image", "page", "graph"]


class ImmutableKnowledgeContract(BaseModel):
    """Base contract for immutable cross-layer knowledge values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceRef(ImmutableKnowledgeContract):
    """Stable pointer to an immutable evidence artifact."""

    document_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    page: int | None = Field(default=None, ge=1)
    chunk_id: str | None = None
    image_id: str | None = None

    @field_validator("document_id", "chunk_id", "image_id")
    @classmethod
    def reject_blank_identifiers(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("identifier must not be blank")
        return value


class KnowledgeSourcePlan(ImmutableKnowledgeContract):
    """One bounded retrieval request selected by the Knowledge Agent."""

    source: KnowledgeSource
    queries: tuple[str, ...] = Field(min_length=1)
    top_k: int = Field(ge=1, le=100)
    timeout_ms: int = Field(ge=100, le=120_000)
    required: bool = False

    @field_validator("queries")
    @classmethod
    def reject_blank_queries(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("queries must not contain blank values")
        return values


class KnowledgeStrategy(ImmutableKnowledgeContract):
    """Structured source-selection output; it never executes retrieval."""

    sources: tuple[KnowledgeSourcePlan, ...] = Field(min_length=1)
    rewrite: bool = True
    rerank: bool = True
    visual_required: bool = False
    rationale: str = Field(min_length=1)


class AccessScope(ImmutableKnowledgeContract):
    """Fail-closed authorization scope propagated to every knowledge source."""

    tenant_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    permissions: frozenset[str] = Field(default_factory=frozenset)
    document_ids: frozenset[str] = Field(default_factory=frozenset)
    allowed_sources: frozenset[str] = Field(default_factory=frozenset)
    acl_tags: frozenset[str] = Field(default_factory=frozenset)
    allowed_fields: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("tenant_id", "user_id", "role")
    @classmethod
    def reject_blank_scope_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("scope identity must not be blank")
        return value


class MemoryItem(ImmutableKnowledgeContract):
    """A governed long-term memory record eligible for resolution."""

    memory_id: str = Field(min_length=1)
    kind: Literal["preference", "stable_fact", "task", "explicit_remember"]
    content: str = Field(min_length=1)
    updated_at: str
    expires_at: str | None = None
    supersedes: str | None = None


__all__ = [
    "AccessScope",
    "EvidenceLayer",
    "EvidenceRef",
    "ImmutableKnowledgeContract",
    "KnowledgeSource",
    "KnowledgeSourcePlan",
    "KnowledgeStrategy",
    "MemoryItem",
    "Modality",
]
