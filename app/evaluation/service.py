"""Evaluation service for running and comparing retrieval systems."""

import statistics
from datetime import datetime
from typing import Protocol

from app.evaluation.metrics import calculate_all_metrics
from app.evaluation.models import (
    EvaluationMetrics,
    EvaluationRun,
    QueryEvaluation,
    RetrievalResult,
    SystemComparison,
    TestQuery,
)


class RetrievalSystem(Protocol):
    """Protocol for retrieval systems that can be evaluated."""

    def retrieve(self, query: str, query_id: str = "") -> RetrievalResult:
        """Retrieve documents for a query."""
        ...

    def batch_retrieve(self, queries: list[tuple[str, str]]) -> list[RetrievalResult]:
        """Retrieve documents for multiple queries."""
        ...


class EvaluationService:
    """Service for evaluating and comparing retrieval systems."""

    def __init__(self, k: int = 5):
        """Initialize evaluation service.

        Args:
            k: Number of top results to consider for metrics
        """
        self.k = k

    def evaluate_query(self, test_query: TestQuery, retrieval_result: RetrievalResult) -> QueryEvaluation:
        """Evaluate a single query result.

        Args:
            test_query: Test query with ground truth
            retrieval_result: Retrieval result to evaluate

        Returns:
            QueryEvaluation with all metrics
        """
        relevant_docs = set(test_query.expected_docs)
        retrieved_docs = retrieval_result.retrieved_docs

        metrics = calculate_all_metrics(retrieved_docs, relevant_docs, self.k)

        return QueryEvaluation(
            query_id=test_query.id,
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1=metrics["f1"],
            reciprocal_rank=metrics["reciprocal_rank"],
            ndcg=metrics["ndcg"],
            latency_ms=retrieval_result.latency_ms,
            retrieved_docs=retrieved_docs,
            relevant_docs=list(relevant_docs),
        )

    def evaluate_system(
        self, system: RetrievalSystem, test_queries: list[TestQuery], system_name: str = "unknown"
    ) -> EvaluationRun:
        """Evaluate a retrieval system on a set of test queries.

        Args:
            system: Retrieval system to evaluate
            test_queries: List of test queries with ground truth
            system_name: Name identifier for the system

        Returns:
            EvaluationRun with aggregated metrics and per-query results
        """
        # Prepare queries for batch retrieval
        query_tuples = [(q.query, q.id) for q in test_queries]

        # Retrieve documents
        retrieval_results = system.batch_retrieve(query_tuples)

        # Evaluate each query
        query_evaluations = []
        # strict=True: a short result list used to truncate the query set
        # silently, and truncation makes the score *better* -- the queries that
        # get dropped are the ones the retriever failed to answer. A retriever
        # that returns the wrong number of results is broken, not lenient.
        for test_query, retrieval_result in zip(test_queries, retrieval_results, strict=True):
            query_eval = self.evaluate_query(test_query, retrieval_result)
            query_evaluations.append(query_eval)

        # Aggregate metrics
        aggregated_metrics = self._aggregate_metrics(query_evaluations)

        # Create evaluation run
        run_id = f"{system_name}_{datetime.now().isoformat()}"

        return EvaluationRun(
            run_id=run_id,
            system_name=system_name,
            timestamp=datetime.now().isoformat(),
            metrics=aggregated_metrics,
            query_results=query_evaluations,
            config={"k": self.k, "num_queries": len(test_queries)},
        )

    def compare_systems(
        self, systems: dict[str, RetrievalSystem], test_queries: list[TestQuery]
    ) -> list[SystemComparison]:
        """Compare multiple retrieval systems.

        Args:
            systems: Dictionary mapping system names to retrieval systems
            test_queries: List of test queries with ground truth

        Returns:
            List of SystemComparison objects, sorted by F1 score
        """
        comparisons = []

        for system_name, system in systems.items():
            eval_run = self.evaluate_system(system, test_queries, system_name)

            comparison = SystemComparison(
                system_name=system_name,
                metrics=eval_run.metrics,
                query_results=eval_run.query_results,
            )
            comparisons.append(comparison)

        # Sort by F1 score (descending)
        comparisons.sort(key=lambda x: x.metrics.f1_at_5, reverse=True)

        return comparisons

    def _aggregate_metrics(self, query_evaluations: list[QueryEvaluation]) -> EvaluationMetrics:
        """Aggregate metrics across multiple queries.

        Args:
            query_evaluations: List of per-query evaluations

        Returns:
            Aggregated EvaluationMetrics
        """
        if not query_evaluations:
            return EvaluationMetrics(
                precision_at_5=0.0,
                recall_at_5=0.0,
                f1_at_5=0.0,
                mrr=0.0,
                ndcg_at_5=0.0,
                avg_latency_ms=0.0,
                total_queries=0,
            )

        return EvaluationMetrics(
            precision_at_5=statistics.mean(q.precision for q in query_evaluations),
            recall_at_5=statistics.mean(q.recall for q in query_evaluations),
            f1_at_5=statistics.mean(q.f1 for q in query_evaluations),
            mrr=statistics.mean(q.reciprocal_rank for q in query_evaluations),
            ndcg_at_5=statistics.mean(q.ndcg for q in query_evaluations),
            avg_latency_ms=statistics.mean(q.latency_ms for q in query_evaluations),
            total_queries=len(query_evaluations),
        )

    def print_comparison(self, comparisons: list[SystemComparison]) -> None:
        """Print a formatted comparison table.

        Args:
            comparisons: List of system comparisons
        """
        import logging

        logger = logging.getLogger(__name__)

        logger.info("\n" + "=" * 80)
        logger.info("RETRIEVAL SYSTEM COMPARISON")
        logger.info("=" * 80)
        logger.info(f"{'System':<20} {'P@5':>8} {'R@5':>8} {'F1@5':>8} {'MRR':>8} {'NDCG@5':>8} {'Latency(ms)':>12}")
        logger.info("-" * 80)

        for comp in comparisons:
            m = comp.metrics
            logger.info(
                f"{comp.system_name:<20} "
                f"{m.precision_at_5:>8.3f} "
                f"{m.recall_at_5:>8.3f} "
                f"{m.f1_at_5:>8.3f} "
                f"{m.mrr:>8.3f} "
                f"{m.ndcg_at_5:>8.3f} "
                f"{m.avg_latency_ms:>12.1f}"
            )

        logger.info("=" * 80 + "\n")
