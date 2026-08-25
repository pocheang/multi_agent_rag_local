"""LLM Wiki generation over authorized original Evidence only."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from app.core.config import Settings, get_settings
from app.domain.contracts import EvidenceItem
from app.domain.knowledge import AccessScope
from app.wiki.models import WikiArticleVersion
from app.wiki.source_mapping import governed_evidence, references_from_evidence
from app.wiki.store import WikiStore

WikiContentGenerator = Callable[[str, tuple[EvidenceItem, ...]], Awaitable[str]]


class WikiGenerator:
    """Generate derived articles without changing or replacing source Evidence."""

    def __init__(
        self,
        store: WikiStore | None = None,
        generate: WikiContentGenerator | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or (Settings() if store is not None else get_settings())
        self._store = store or WikiStore(settings=self._settings)
        self._generate = generate or _default_generate

    async def generate(
        self,
        *,
        tenant_id: str,
        title: str,
        evidence: Iterable[EvidenceItem],
        scope: AccessScope,
        slug: str | None = None,
        change_note: str = "llm_generation",
    ) -> WikiArticleVersion:
        if tenant_id != scope.tenant_id:
            raise PermissionError("Wiki tenant does not match the authorized scope")
        safe_evidence = governed_evidence(evidence, scope)
        if not safe_evidence:
            raise ValueError("Wiki generation requires authorized, versioned original Evidence")
        content = await asyncio.wait_for(
            self._generate(title, safe_evidence),
            timeout=self._settings.wiki_generation_timeout_ms / 1000,
        )
        if not str(content or "").strip():
            raise RuntimeError("Wiki generator returned empty content")
        references = references_from_evidence(safe_evidence)
        return await asyncio.to_thread(
            self._store.upsert,
            tenant_id=tenant_id,
            title=title,
            content=content,
            source_references=references,
            slug=slug,
            change_note=change_note,
        )


async def _default_generate(title: str, evidence: tuple[EvidenceItem, ...]) -> str:
    from app.services.models.runtime import get_chat_model

    rendered = "\n\n".join(
        f"[S{index}] document={item.document_id}, version={item.version}, page={item.page}, "
        f"chunk={item.chunk_id}, image={item.image_id}, source={item.source}\n{item.content}"
        for index, item in enumerate(evidence, start=1)
    )
    system = (
        "Create a concise Markdown knowledge article from the supplied original evidence only. "
        "Preserve uncertainty and conflicts, cite claims with [S#], and never present this derived article "
        "as the source of truth. Do not add unsupported facts."
    )
    model = get_chat_model(temperature=0)
    response = await asyncio.to_thread(
        model.invoke,
        [("system", system), ("human", f"Title: {title}\n\nOriginal evidence:\n{rendered}")],
    )
    return _response_text(response)


def _response_text(response: Any) -> str:
    if isinstance(response, dict):
        return str(response.get("content") or response.get("text") or "").strip()
    return str(getattr(response, "content", response) or "").strip()


__all__ = ["WikiContentGenerator", "WikiGenerator"]
