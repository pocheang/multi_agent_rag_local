"""Unified evidence item construction from heterogeneous retriever payloads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.domain.contracts import EvidenceBundle, EvidenceItem


class EvidenceItemBuilder:
    """Build EvidenceItem from various retriever payload formats.

    Handles field name variations and type conversions consistently.
    """

    def __init__(self, retriever: str):
        self.retriever = retriever

    def from_legacy_citation(self, citation: Mapping[str, Any]) -> EvidenceItem | None:
        """Build from graph/web citation format (dict with optional metadata)."""
        metadata = citation.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}

        source = self._extract_text(citation, metadata, "source", "url")
        document_id = self._extract_text(citation, metadata, "document_id", "doc_id", "id") or source
        content = self._extract_text(citation, metadata, "content", "snippet", "text")

        if not source or not document_id or not content:
            return None

        score = self._extract_value(
            citation, metadata, "score", "rerank_score", "hybrid_score", "dense_score", "bm25_score"
        )
        page = self._extract_value(citation, metadata, "page")

        return self._build_item(content, source, document_id, page, score, metadata)

    def from_vector_match(self, match: tuple[Any, Any]) -> EvidenceItem | None:
        """Build from vector retriever format (document, relevance_score tuple)."""
        if not isinstance(match, tuple) or len(match) != 2:
            return None

        document, relevance = match
        metadata = getattr(document, "metadata", {})
        metadata = metadata if isinstance(metadata, Mapping) else {}

        source = self._extract_text({}, metadata, "source", "url")
        document_id = self._extract_text({}, metadata, "document_id", "doc_id", "id") or source
        content = str(getattr(document, "page_content", "") or "").strip()

        if not source or not document_id or not content:
            return None

        page = self._extract_value({}, metadata, "page")

        return self._build_item(content, source, document_id, page, relevance, metadata)

    def from_bm25_record(self, record: Mapping[str, Any]) -> EvidenceItem | None:
        """Build from BM25 retriever format (flat dict with optional metadata)."""
        if not isinstance(record, Mapping):
            return None

        metadata = record.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}

        source = self._extract_text(record, metadata, "source", "url")
        document_id = self._extract_text(record, metadata, "id", "document_id", "doc_id") or source
        content = self._extract_text(record, metadata, "text", "content", "snippet")

        if not source or not document_id or not content:
            return None

        page = self._extract_value(record, metadata, "page")
        score = self._extract_value(record, metadata, "bm25_score", "score")

        return self._build_item(content, source, document_id, page, score, metadata)

    def _build_item(
        self,
        content: str,
        source: str,
        document_id: str,
        page: Any,
        score: Any,
        metadata: Mapping[str, Any],
    ) -> EvidenceItem | None:
        """Construct EvidenceItem with type conversion and validation."""
        modality = str(metadata.get("modality") or "text").lower()
        if modality == "chart":
            modality = "image"
        if modality not in {"text", "table", "image", "page", "graph"}:
            modality = "text"
        image_id = self._extract_text({}, metadata, "image_id") or None
        if modality == "image" and image_id is None:
            modality = "text"
        layer = {
            "wiki": "knowledge",
            "memory": "memory",
            "web": "web",
            "tool": "tool",
        }.get(self.retriever, str(metadata.get("layer") or "evidence"))
        if layer not in {"evidence", "knowledge", "memory", "web", "tool"}:
            layer = "evidence"
        raw_acl = metadata.get("acl_tags", ()) or ()
        if isinstance(raw_acl, str):
            raw_acl = (raw_acl,)
        try:
            return EvidenceItem(
                content=content,
                source=source,
                document_id=document_id,
                version=self._normalize_page(metadata.get("version")),
                page=self._normalize_page(page),
                chunk_id=self._extract_text({}, metadata, "chunk_id") or None,
                image_id=image_id,
                artifact_uri=self._extract_text({}, metadata, "artifact_uri", "original_image") or None,
                modality=modality,
                layer=layer,
                acl_tags=frozenset(str(tag) for tag in raw_acl),
                retriever=self.retriever,
                score=self._normalize_score(score),
                conflict_group=self._extract_text({}, metadata, "conflict_group") or None,
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_text(
        record: Mapping[str, Any],
        metadata: Mapping[str, Any],
        *field_names: str,
    ) -> str:
        """Extract first non-empty text value from field name candidates."""
        value = EvidenceItemBuilder._extract_value(record, metadata, *field_names)
        return str(value or "").strip()

    @staticmethod
    def _extract_value(
        record: Mapping[str, Any],
        metadata: Mapping[str, Any],
        *field_names: str,
    ) -> Any:
        """Extract first non-None value from field name candidates."""
        for name in field_names:
            value = record.get(name)
            if value is not None:
                return value
            value = metadata.get(name)
            if value is not None:
                return value
        return None

    @staticmethod
    def _normalize_page(value: Any) -> int | None:
        """Convert page value to positive integer or None."""
        try:
            page = int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
        return page if page and page > 0 else None

    @staticmethod
    def _normalize_score(value: Any) -> float | None:
        """Convert score value to float in [0.0, 1.0] or None."""
        try:
            score = float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
        return min(1.0, max(0.0, score)) if score is not None else None


def bundle_from_legacy_payload(
    payload: Any,
    retriever: str,
    *,
    fallback_document_id: str | None = None,
) -> EvidenceBundle:
    """Build EvidenceBundle from legacy graph/web result payload.

    Handles both citation-based format and graph context fallback.
    """
    if not isinstance(payload, Mapping):
        return EvidenceBundle()

    error = str(payload.get("error") or "").strip()
    if error:
        from app.agents.rag.service import RetrieverSoftFailure

        raise RetrieverSoftFailure(error)

    # Try citation-based format
    citations = payload.get("citations")
    if isinstance(citations, Sequence) and not isinstance(citations, str | bytes):
        builder = EvidenceItemBuilder(retriever)
        items = tuple(
            item
            for citation in citations
            if isinstance(citation, Mapping)
            if (item := builder.from_legacy_citation(citation)) is not None
        )
        if items:
            return EvidenceBundle(items=items)

    # Fallback for graph context (no citations)
    if retriever == "graph":
        context = str(payload.get("context") or "").strip()
        if context and fallback_document_id:
            score = EvidenceItemBuilder._normalize_score(payload.get("graph_signal_score"))
            return EvidenceBundle(
                items=(
                    EvidenceItem(
                        content=context,
                        source="knowledge_graph",
                        document_id=fallback_document_id,
                        retriever="graph",
                        score=score,
                    ),
                )
            )

    return EvidenceBundle()


def bundle_from_vector_matches(matches: Any) -> EvidenceBundle:
    """Build EvidenceBundle from vector retriever results."""
    if not isinstance(matches, Sequence) or isinstance(matches, str | bytes):
        return EvidenceBundle()

    builder = EvidenceItemBuilder("vector")
    items = [item for match in matches if (item := builder.from_vector_match(match)) is not None]
    return EvidenceBundle(items=tuple(items))


def bundle_from_bm25_records(records: Any) -> EvidenceBundle:
    """Build EvidenceBundle from BM25 retriever results."""
    if not isinstance(records, Sequence) or isinstance(records, str | bytes):
        return EvidenceBundle()

    builder = EvidenceItemBuilder("bm25")
    items = [item for record in records if (item := builder.from_bm25_record(record)) is not None]
    return EvidenceBundle(items=tuple(items))
