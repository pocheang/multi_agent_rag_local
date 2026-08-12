"""Canonical corpus scoping for Agent classes.

Specialist classes may only retrieve documents explicitly labeled for that
class.  An empty specialist scope remains empty; only ``general`` receives no
source restriction.
"""

from __future__ import annotations

from typing import Any

from app.retrievers.stores.corpus import read_corpus_records


def get_sources_by_agent_class(agent_class: str) -> list[str] | None:
    """Return allowed sources for an Agent class, or ``None`` for general."""
    if agent_class == "general":
        return None

    sources = {
        source
        for record in read_corpus_records()
        if (metadata := record.get("metadata", {})).get("agent", "") == agent_class
        and (source := metadata.get("source", ""))
    }

    # Do not widen an empty specialist scope to all corpus records.
    # Stable ordering keeps filters, diagnostics, and serialized responses
    # deterministic without changing the scope itself.
    return sorted(sources)


def get_agent_filter_stats() -> dict[str, dict[str, Any]]:
    """Return serializable document and chunk counts grouped by Agent class."""
    stats: dict[str, dict[str, Any]] = {}
    for record in read_corpus_records():
        metadata = record.get("metadata", {})
        agent = metadata.get("agent", "未分类")
        source = metadata.get("source", "")
        data = stats.setdefault(agent, {"sources": set(), "chunks": 0})
        data["chunks"] += 1
        if source:
            data["sources"].add(source)

    return {
        agent: {
            "document_count": len(data["sources"]),
            "chunk_count": data["chunks"],
            "sources": sorted(data["sources"]),
        }
        for agent, data in stats.items()
    }


__all__ = [
    "get_agent_filter_stats",
    "get_sources_by_agent_class",
    "read_corpus_records",
]
