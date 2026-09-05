"""Multi-modal retrieval service for RAG."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import get_settings
from app.domain.contracts import EvidenceItem
from app.domain.knowledge import AccessScope

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Multi-modal retrieval result."""

    id: str
    content: str
    score: float
    modality: Literal["text", "image", "table"]
    doc_id: str
    page_number: int
    metadata: dict[str, Any]

    @property
    def is_multimodal(self) -> bool:
        """Check if result is non-text modality."""
        return self.modality in ["image", "table"]


class MultiModalRetriever:
    """Retrieve content across images and tables."""

    def __init__(self):
        self.settings = get_settings()
        self.default_top_k = 10

        # Fusion method
        self.fusion_method = getattr(self.settings, "multimodal_fusion_method", "rrf")  # rrf|weighted

        # Modality weights for weighted fusion
        self.text_weight = getattr(self.settings, "text_weight", 0.4)
        self.image_weight = getattr(self.settings, "image_weight", 0.3)
        self.table_weight = getattr(self.settings, "table_weight", 0.3)

    async def retrieve(
        self,
        query: str,
        scope: AccessScope,
        modalities: list[str] | None = None,
        top_k: int | None = None,
        **kwargs: Any,
    ) -> list[RetrievalResult]:
        """Multi-modal retrieval across specified modalities.

        Args:
            query: Search query
            modalities: List of modalities to search (image, table)
                       If None, searches all modalities
            top_k: Number of results to return
            **kwargs: Additional retrieval parameters

        Returns:
            List of RetrievalResult objects
        """
        # Two modalities, and the two that are gone were removed for opposite
        # reasons. `text` queried a `text_chunks` collection nothing has ever
        # created, and text is what the `vector` source is for. `chart` had a
        # producer that nothing constructed, so `chart_descriptions` could not
        # exist -- and a chart reaches the index as an image now, captioned by
        # the configured vision backend.
        modalities = modalities or ["image", "table"]
        top_k = top_k or self.default_top_k
        where = _scope_filter(scope)
        if where is None:
            return []
        kwargs = {**kwargs, "where": where}

        try:
            # Retrieve from each modality in parallel
            retrieval_tasks = []

            if "image" in modalities:
                retrieval_tasks.append(self._retrieve_images(query, top_k, **kwargs))

            if "table" in modalities:
                retrieval_tasks.append(self._retrieve_tables(query, top_k, **kwargs))

            # Execute all retrievals concurrently
            all_results = await asyncio.gather(*retrieval_tasks, return_exceptions=True)

            # Filter out exceptions and flatten results
            valid_results: list[list[RetrievalResult]] = []
            for i, result in enumerate(all_results):
                if isinstance(result, Exception):
                    logger.error(f"Retrieval error for modality {modalities[i]}: {result}")
                else:
                    valid_results.append(result)

            # Flatten all results
            flattened: list[RetrievalResult] = []
            for results in valid_results:
                flattened.extend(results)

            # Fuse and rank results
            if self.fusion_method == "rrf":
                fused = self._reciprocal_rank_fusion(valid_results, top_k)
            else:  # weighted
                fused = self._weighted_fusion(valid_results, top_k)

            logger.info(f"Retrieved {len(fused)} results from {len(modalities)} modalities")

            return fused

        except Exception:
            logger.exception("Multi-modal retrieval error")
            raise

    async def retrieve_evidence(
        self,
        query: str,
        scope: AccessScope,
        modalities: list[str] | None = None,
        top_k: int | None = None,
        **kwargs: Any,
    ) -> tuple[EvidenceItem, ...]:
        """Return canonical evidence after database and in-process authorization checks."""

        rows = await self.retrieve(query, scope, modalities=modalities, top_k=top_k, **kwargs)
        evidence: list[EvidenceItem] = []
        for row in rows:
            item = _to_evidence_item(row)
            if item is not None and _matches_scope(item, row.metadata, scope):
                evidence.append(item)
        return tuple(evidence)

    async def _retrieve_images(self, query: str, top_k: int, **kwargs: Any) -> list[RetrievalResult]:
        """Retrieve image descriptions."""
        try:
            from app.retrievers.stores.vector import get_chroma_client

            client = get_chroma_client()

            try:
                collection = client.get_collection(name="image_descriptions")
            except Exception:
                logger.info("Image collection not found, skipping image retrieval")
                collection = None

            # Query collection
            results = (
                collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=kwargs.get("where"),
                    include=["documents", "metadatas", "distances"],
                )
                if collection is not None
                else {"ids": [], "documents": [], "metadatas": [], "distances": []}
            )

            # Convert to RetrievalResult
            retrieval_results: list[RetrievalResult] = []

            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 1.0
                    score = 1.0 / (1.0 + distance)

                    result = RetrievalResult(
                        id=doc_id,
                        content=results["documents"][0][i],
                        score=score,
                        modality="image",
                        doc_id=metadata.get("doc_id", ""),
                        page_number=metadata.get("page_number", 0),
                        metadata=metadata,
                    )
                    retrieval_results.append(result)

            return retrieval_results[:top_k]

        except Exception:
            logger.exception("Image retrieval error")
            return []

    async def _retrieve_tables(self, query: str, top_k: int, **kwargs: Any) -> list[RetrievalResult]:
        """Retrieve table summaries."""
        try:
            from app.retrievers.stores.vector import get_chroma_client

            client = get_chroma_client()

            try:
                collection = client.get_collection(name="table_summaries")
            except Exception:
                logger.info("Table collection not found, skipping table retrieval")
                return []

            # Query collection
            results = collection.query(
                query_texts=[query],
                n_results=top_k,
                where=kwargs.get("where"),
                include=["documents", "metadatas", "distances"],
            )

            # Convert to RetrievalResult
            retrieval_results: list[RetrievalResult] = []

            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 1.0
                    score = 1.0 / (1.0 + distance)

                    result = RetrievalResult(
                        id=doc_id,
                        content=results["documents"][0][i],
                        score=score,
                        modality="table",
                        doc_id=metadata.get("doc_id", ""),
                        page_number=metadata.get("page_number", 0),
                        metadata=metadata,
                    )
                    retrieval_results.append(result)

            return retrieval_results

        except Exception:
            logger.exception("Table retrieval error")
            return []

    def _reciprocal_rank_fusion(
        self, results_by_modality: list[list[RetrievalResult]], top_k: int
    ) -> list[RetrievalResult]:
        """Fuse results using Reciprocal Rank Fusion (RRF).

        Args:
            results_by_modality: List of result lists, one per modality
            top_k: Number of results to return

        Returns:
            Fused and ranked results
        """
        k = 60  # RRF constant

        # Calculate RRF scores
        rrf_scores: dict[str, float] = {}
        result_map: dict[str, RetrievalResult] = {}

        for results in results_by_modality:
            for rank, result in enumerate(results, start=1):
                # RRF score = 1 / (k + rank)
                rrf_score = 1.0 / (k + rank)

                if result.id in rrf_scores:
                    rrf_scores[result.id] += rrf_score
                else:
                    rrf_scores[result.id] = rrf_score
                    result_map[result.id] = result

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        # Create fused results with updated scores
        fused: list[RetrievalResult] = []
        for result_id in sorted_ids[:top_k]:
            result = result_map[result_id]
            # Update score to RRF score
            result.score = rrf_scores[result_id]
            fused.append(result)

        return fused

    def _weighted_fusion(self, results_by_modality: list[list[RetrievalResult]], top_k: int) -> list[RetrievalResult]:
        """Fuse results using weighted scoring.

        Args:
            results_by_modality: List of result lists, one per modality
            top_k: Number of results to return

        Returns:
            Fused and ranked results
        """
        weighted_scores: dict[str, float] = {}
        result_map: dict[str, RetrievalResult] = {}

        # Weight map
        weight_map = {
            "text": self.text_weight,
            "image": self.image_weight,
            "table": self.table_weight,
        }

        for results in results_by_modality:
            for result in results:
                weight = weight_map.get(result.modality, 0.25)
                weighted_score = result.score * weight

                if result.id in weighted_scores:
                    weighted_scores[result.id] += weighted_score
                else:
                    weighted_scores[result.id] = weighted_score
                    result_map[result.id] = result

        # Sort by weighted score
        sorted_ids = sorted(weighted_scores.keys(), key=lambda x: weighted_scores[x], reverse=True)

        # Create fused results
        fused: list[RetrievalResult] = []
        for result_id in sorted_ids[:top_k]:
            result = result_map[result_id]
            result.score = weighted_scores[result_id]
            fused.append(result)

        return fused


def _scope_filter(scope: AccessScope) -> dict[str, Any] | None:
    """Build a Chroma filter that never searches outside the authorized tenant.

    Two independent checks, the same pair `similarity_search` applies: the source
    or document list, which is *derived* from the caller's visible documents, and
    the owner metadata, which is written independently at index time. A bug in one
    does not widen what the other allows.
    """

    from app.retrievers.stores.vector import OwnerScope, _owner_clause

    constraints: list[dict[str, Any]] = [{"tenant_id": scope.tenant_id}]
    owner = OwnerScope.from_access_scope(scope)
    if owner is not None:
        constraints.append(_owner_clause(owner))
    if scope.document_ids:
        document_ids = sorted(scope.document_ids)
        constraints.append(
            {"document_id": document_ids[0]} if len(document_ids) == 1 else {"document_id": {"$in": document_ids}}
        )
    elif scope.allowed_sources:
        sources = sorted(scope.allowed_sources)
        constraints.append({"source": sources[0]} if len(sources) == 1 else {"source": {"$in": sources}})
    else:
        # A tenant identity alone does not prove document-level access.
        return None
    return constraints[0] if len(constraints) == 1 else {"$and": constraints}


def _to_evidence_item(row: RetrievalResult) -> EvidenceItem | None:
    metadata = row.metadata
    document_id = str(row.doc_id or metadata.get("document_id") or metadata.get("doc_id") or "").strip()
    source = str(metadata.get("source") or metadata.get("artifact_uri") or document_id).strip()
    content = str(row.content or "").strip()
    if not document_id or not source or not content:
        return None
    raw_acl = metadata.get("acl_tags", ()) or ()
    if isinstance(raw_acl, str):
        raw_acl = tuple(value.strip() for value in raw_acl.split(",") if value.strip())
    raw_modality = str(row.modality or "text")
    modality = "image" if raw_modality == "image" else "table" if raw_modality == "table" else "text"
    image_id = str(metadata.get("image_id") or row.id or "").strip() if modality == "image" else None
    try:
        return EvidenceItem(
            content=content,
            source=source,
            document_id=document_id,
            version=_positive_int(metadata.get("version")),
            page=_positive_int(row.page_number or metadata.get("page")),
            chunk_id=_optional_text(metadata.get("chunk_id")),
            image_id=image_id or None,
            artifact_uri=_optional_text(metadata.get("artifact_uri") or metadata.get("original_image")),
            modality=modality,
            layer="evidence",
            acl_tags=frozenset(str(value) for value in raw_acl),
            retriever="multimodal",
            score=min(1.0, max(0.0, float(row.score))),
        )
    except (TypeError, ValueError):
        return None


def _matches_scope(item: EvidenceItem, metadata: dict[str, Any], scope: AccessScope) -> bool:
    if str(metadata.get("tenant_id") or "") != scope.tenant_id:
        return False
    if scope.document_ids and item.document_id not in scope.document_ids:
        return False
    if scope.allowed_sources and item.source not in scope.allowed_sources:
        return False
    return not item.acl_tags or bool(item.acl_tags.intersection(scope.acl_tags))


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_int(value: object) -> int | None:
    try:
        number = int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return number if number is not None and number > 0 else None
