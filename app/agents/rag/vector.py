"""
Unified Vector RAG Agent - Optimized version integrating all features.

This agent combines:
- Basic vector retrieval (from vector_rag_agent.py)
- Self-RAG evaluation (from enhanced_vector_rag_agent.py)
- BaseAgent architecture for consistency
- Unified configuration

Replaces:
- app/agents/vector_rag_agent.py
- app/agents/enhanced_vector_rag_agent.py
"""

import logging
from pathlib import Path
from typing import Any

from app.agents.shared.config import CHUNK_PREVIEW_LENGTH, DENSE_SCORE_THRESHOLD, get_vector_rag_config
from app.agents.shared.base import BaseAgent
from app.core.config import get_settings
from app.retrievers.hybrid_retriever import hybrid_search_with_diagnostics
from app.retrievers.parameter_tuning import apply_dynamic_parameters
from app.retrievers.query_expansion import expand_query
from app.services.agent_document_filter import get_sources_by_agent_class

logger = logging.getLogger(__name__)


__all__ = ["UnifiedVectorRAGAgent", "run_vector_rag"]


class UnifiedVectorRAGAgent(BaseAgent):
    """
    Unified Vector RAG Agent with all features integrated.

    Features:
    - Hybrid retrieval (dense + BM25)
    - Query expansion
    - Dynamic parameter tuning
    - Agent class filtering
    - Optional Self-RAG evaluation
    - Standardized error handling and result format
    """

    def __init__(self, config: dict[str, Any] | None = None, llm_client=None, dependencies: dict[str, Any] | None = None):
        """
        Initialize unified vector RAG agent.

        Args:
            config: Optional configuration override
            llm_client: Optional LLM client for Self-RAG evaluation
        """
        super().__init__(config)

        # Get vector RAG specific config
        self.vector_config = get_vector_rag_config()
        self._dependencies = dependencies or {}
        self.settings = self._dependencies.get("settings", get_settings())
        self._hybrid_search = self._dependencies.get("hybrid_search_with_diagnostics", hybrid_search_with_diagnostics)
        self._expand_query = self._dependencies.get("expand_query", expand_query)
        self._get_sources_by_agent_class = self._dependencies.get(
            "get_sources_by_agent_class", get_sources_by_agent_class
        )
        self.llm_client = llm_client

        # Initialize Self-RAG evaluator if enabled
        self.self_rag_evaluator = None
        if self.get_config_value("enable_evaluation", False) and llm_client:
            try:
                from app.services.self_rag_evaluator import SelfRAGEvaluator
                self.self_rag_evaluator = SelfRAGEvaluator(llm_client)
                logger.info("Self-RAG evaluation enabled")
            except ImportError:
                logger.warning("Self-RAG evaluator not available")

    def execute(
        self,
        query: str,
        allowed_sources: list[str] | None = None,
        retrieval_strategy: str | None = None,
        agent_class: str | None = None,
        enable_evaluation: bool | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Execute vector RAG retrieval.

        Args:
            query: User query
            allowed_sources: Optional list of allowed document sources
            retrieval_strategy: Retrieval strategy (hybrid/dense/bm25/rerank)
            agent_class: Agent class for automatic document filtering
            enable_evaluation: Whether to enable Self-RAG evaluation
            **kwargs: Additional parameters

        Returns:
            Dictionary with retrieval results
        """
        # Use config defaults if not specified
        if retrieval_strategy is None:
            retrieval_strategy = self.vector_config.retrieval_strategy

        if enable_evaluation is None:
            enable_evaluation = self.vector_config.enable_evaluation

        # Step 1: Apply dynamic parameter tuning
        dynamic_params = self._apply_dynamic_tuning(query)

        # Step 2: Apply query expansion if enabled
        search_query = self._apply_query_expansion(query)

        # Step 3: Apply agent class filtering
        filtered_sources = self._apply_agent_filtering(
            allowed_sources, agent_class
        )

        # Step 4: Execute retrieval
        results, diagnostics = self._execute_retrieval(
            search_query,
            filtered_sources,
            retrieval_strategy,
            dynamic_params
        )

        # Step 5: Process results
        citations = self._build_citations(results)
        context = self._build_context(results)
        effective_hits = self._count_effective_hits(results)

        # Step 6: Self-RAG evaluation (optional)
        evaluation_result = None
        if enable_evaluation and self.self_rag_evaluator:
            evaluation_result = self._evaluate_retrieval(query, citations)

        # Step 7: Build result
        return self._build_result(
            context=context,
            citations=citations,
            retrieved_count=len(citations),
            effective_hit_count=effective_hits,
            diagnostics=diagnostics,
            query=query,
            search_query=search_query,
            strategy=retrieval_strategy,
            evaluation=evaluation_result,
            dynamic_params=dynamic_params
        )

    def _apply_dynamic_tuning(self, query: str) -> dict[str, Any]:
        """Apply dynamic parameter tuning based on query complexity."""
        if not self.vector_config.dynamic_parameters:
            return {
                "complexity": "medium",
                "top_k": self.vector_config.top_k,
                "vector_weight": 0.7,
                "bm25_weight": 0.3
            }

        try:
            params = apply_dynamic_parameters(query)
            logger.debug(
                f"Dynamic tuning: complexity={params['complexity']}, "
                f"top_k={params['top_k']}"
            )
            return params
        except Exception as e:
            logger.warning(f"Dynamic tuning failed: {e}, using defaults")
            return {
                "complexity": "medium",
                "top_k": self.vector_config.top_k,
                "vector_weight": 0.7,
                "bm25_weight": 0.3
            }

    def _apply_query_expansion(self, query: str) -> str:
        """Apply query expansion if enabled."""
        if not bool(getattr(self.settings, "query_expansion_enabled", self.vector_config.enable_query_expansion)):
            return query

        try:
            expanded = self._expand_query(
                query,
                max_expansion_ratio=getattr(
                    self.settings,
                    "query_expansion_max_ratio",
                    3.0
                )
            )
            if expanded and expanded != query:
                logger.info(f"Query expanded: '{query}' -> '{expanded}'")
                return expanded
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")

        return query

    def _apply_agent_filtering(
        self,
        allowed_sources: list[str] | None,
        agent_class: str | None
    ) -> list[str] | None:
        """Apply agent class document filtering."""
        if not agent_class:
            return allowed_sources

        try:
            class_sources = self._get_sources_by_agent_class(agent_class)
            if allowed_sources is None:
                return class_sources
            elif class_sources is not None:
                allowed_set = set(class_sources)
                filtered = [s for s in allowed_sources if s in allowed_set]
                logger.debug(
                    f"Agent filter for {agent_class}: "
                    f"{len(allowed_sources)} -> {len(filtered)} sources"
                )
                return filtered
        except Exception as e:
            logger.warning(f"Agent filtering failed: {e}")

        return allowed_sources

    def _execute_retrieval(
        self,
        query: str,
        allowed_sources: list[str] | None,
        strategy: str | None,
        dynamic_params: dict[str, Any]
    ) -> tuple:
        """Execute hybrid retrieval with diagnostics."""
        try:
            results, diagnostics = self._hybrid_search(
                query,
                allowed_sources=allowed_sources,
                retrieval_strategy=strategy,
                dynamic_top_k=dynamic_params.get('top_k'),
                dynamic_vector_weight=dynamic_params.get('vector_weight'),
                dynamic_bm25_weight=dynamic_params.get('bm25_weight'),
            )
            return results, diagnostics
        except TypeError:
            # Backward-compatible fallback
            logger.warning("Using legacy retrieval signature")
            results, diagnostics = self._hybrid_search(
                query,
                allowed_sources=allowed_sources,
            )
            return results, diagnostics

    def _build_citations(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build legacy-compatible citation records from unified results."""
        citations = []
        for item in results[: self.settings.max_context_chunks]:
            metadata = item.get("metadata", {})
            source_path = str(metadata.get("source", "unknown"))
            source = Path(source_path).name if source_path else "unknown"
            retrieval_sources = item.get("retrieval_sources", [])
            if not isinstance(retrieval_sources, list):
                retrieval_sources = [str(retrieval_sources)]
            citations.append(
                {
                    "source": source,
                    "content": str(item.get("text", "") or "")[:CHUNK_PREVIEW_LENGTH],
                    "metadata": {
                        **metadata,
                        "dense_score": item.get("dense_score"),
                        "bm25_score": item.get("bm25_score"),
                        "hybrid_score": item.get("hybrid_score"),
                        "rerank_score": item.get("rerank_score"),
                        "rank_feature_score": item.get("rank_feature_score"),
                        "retrieval_sources": retrieval_sources,
                    },
                }
            )
        return citations

    def _build_context(self, results: list[dict[str, Any]]) -> str:
        """Keep the established vector context and source formatting."""
        blocks = []
        for item in results[: self.settings.max_context_chunks]:
            metadata = item.get("metadata", {})
            source_path = str(metadata.get("source", "unknown"))
            source = Path(source_path).name if source_path else "unknown"
            retrieval_sources = item.get("retrieval_sources", [])
            if not isinstance(retrieval_sources, list):
                retrieval_sources = [str(retrieval_sources)]
            blocks.append(
                f"[SOURCE: {source}]\n[RETRIEVAL: {','.join(retrieval_sources)}]\n"
                f"{str(item.get('text', '') or '')[:CHUNK_PREVIEW_LENGTH]}"
            )
        return "\n\n".join(blocks)

    def _count_effective_hits(self, results: list[dict[str, Any]]) -> int:
        """Count score-backed or non-empty evidence chunks."""
        effective_count = 0
        for item in results[: self.settings.max_context_chunks]:
            rerank_score = item.get("rerank_score")
            dense_score = item.get("dense_score")
            bm25_score = item.get("bm25_score")
            has_valid_score = (
                (isinstance(rerank_score, int | float) and rerank_score > 0)
                or (isinstance(dense_score, int | float) and dense_score >= DENSE_SCORE_THRESHOLD)
                or (isinstance(bm25_score, int | float) and bm25_score > 0)
            )
            if has_valid_score or str(item.get("text", "") or "").strip():
                effective_count += 1
        return effective_count

    def _evaluate_retrieval(
        self,
        query: str,
        citations: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Evaluate retrieval quality with Self-RAG."""
        if not self.self_rag_evaluator:
            return None

        try:
            # Convert citations to document format
            documents = [
                {"content": c["content"], "source": c["source"]}
                for c in citations
            ]

            # This would be async in real implementation
            # For now, return placeholder
            logger.info("Self-RAG evaluation would run here")
            return {
                "enabled": True,
                "evaluated_count": len(documents),
                "note": "Self-RAG evaluation placeholder"
            }
        except Exception as e:
            logger.warning(f"Self-RAG evaluation failed: {e}")
            return {"enabled": True, "error": str(e)}

    def _build_result(
        self,
        context: str,
        citations: list[dict[str, Any]],
        retrieved_count: int,
        effective_hit_count: int,
        diagnostics: dict[str, Any],
        query: str,
        search_query: str,
        strategy: str | None,
        evaluation: dict[str, Any] | None,
        dynamic_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Build final result dictionary."""
        # Add query expansion info
        if search_query != query:
            diagnostics["query_expansion"] = {
                "original": query,
                "expanded": search_query,
                "enabled": True,
            }
        else:
            diagnostics["query_expansion"] = {
                "enabled": bool(getattr(self.settings, "query_expansion_enabled", self.vector_config.enable_query_expansion)),
            }

        # Add dynamic parameters info
        diagnostics["dynamic_parameters"] = dynamic_params

        result = {
            "context": context,
            "citations": citations,
            "retrieved_count": retrieved_count,
            "effective_hit_count": effective_hit_count,
            "retrieval_diagnostics": diagnostics,
            "retrieval_strategy": strategy,
        }

        # Add evaluation results if available
        if evaluation:
            result["evaluation"] = evaluation

        return result


# Backward-compatible function interface
def run_vector_rag(
    question: str,
    allowed_sources: list[str] | None = None,
    retrieval_strategy: str | None = None,
    agent_class: str | None = None,
) -> dict[str, Any]:
    """
    Backward-compatible function interface for vector RAG.

    This maintains compatibility with existing code while using
    the new unified agent internally.

    Args:
        question: User query
        allowed_sources: Optional list of allowed sources
        retrieval_strategy: Retrieval strategy
        agent_class: Agent class for filtering

    Returns:
        Dictionary with retrieval results
    """
    agent = UnifiedVectorRAGAgent()
    result = agent.run(
        query=question,
        allowed_sources=allowed_sources,
        retrieval_strategy=retrieval_strategy,
        agent_class=agent_class
    )

    # Extract core result (remove BaseAgent wrapper fields for compatibility)
    return {
        "context": result.get("context", ""),
        "citations": result.get("citations", []),
        "retrieved_count": result.get("retrieved_count", 0),
        "effective_hit_count": result.get("effective_hit_count", 0),
        "retrieval_diagnostics": result.get("retrieval_diagnostics", {}),
    }
