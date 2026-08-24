"""Immutable input model for the orchestration engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.domain.contracts import ImmutableContract


class RequestActor(ImmutableContract):
    """Identity and permissions available to a single execution."""

    user_id: str | None = None
    tenant_id: str | None = None
    username: str | None = None
    role: str | None = None
    permissions: frozenset[str] = Field(default_factory=frozenset)


class RequestScope(ImmutableContract):
    """Source restrictions propagated from the public pipeline contract."""

    allowed_sources: frozenset[str] | None = None
    document_ids: frozenset[str] | None = None
    acl_tags: frozenset[str] | None = None
    allowed_fields: frozenset[str] | None = None
    agent_class_hint: str | None = None


class ConversationTurn(ImmutableContract):
    """A compact prior message that may inform routing or synthesis."""

    role: str = Field(min_length=1)
    content: str


class RetryBudget(ImmutableContract):
    """Request-owned retry budget shared by every orchestration stage."""

    max_attempts: int = Field(default=2, ge=0)
    consumed: int = Field(default=0, ge=0)

    def consume(self) -> RetryBudget:
        """Return a new budget after one attempt, or fail closed when empty."""
        if self.consumed >= self.max_attempts:
            raise RuntimeError("retry budget exhausted")
        return self.model_copy(update={"consumed": self.consumed + 1})

    @property
    def remaining(self) -> int:
        return max(0, self.max_attempts - self.consumed)


class OrchestrationRequest(ImmutableContract):
    """All typed request data available to orchestration stages."""

    question: str = Field(min_length=1)
    profile: str = "standard"
    session_id: str | None = None
    conversation: tuple[ConversationTurn, ...] = Field(default_factory=tuple)
    actor: RequestActor | None = None
    source_scope: RequestScope = Field(default_factory=RequestScope)
    retrieval_strategy: str | None = None
    use_reasoning: bool = False
    use_web_fallback: bool = False
    deadline_at: datetime | None = None
    enable_decomposition: bool = False
    enable_self_rag: bool = False
    enable_context_tracking: bool = True
    force_language: str = ""
    request_id: str | None = None
    execution_id: str | None = None
    retry_budget: RetryBudget = Field(default_factory=RetryBudget)
    runtime_context: Any | None = Field(default=None, exclude=True)

    @property
    def context_key(self) -> tuple[str, str] | None:
        """Return the tenant-scoped context key when both identities exist."""
        if self.actor is None or not self.actor.user_id or not self.session_id:
            return None
        return self.actor.user_id, self.session_id
