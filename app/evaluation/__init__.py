"""Evaluation module for comparing retrieval system performance."""

from app.evaluation.agents import agent_trace_summary, router_decision_score
from app.evaluation.data_loader import (
    filter_queries_by_category,
    filter_queries_by_difficulty,
    load_test_queries,
    save_test_queries,
)
from app.evaluation.metrics import (
    calculate_all_metrics,
    f1_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.evaluation.models import (
    EvaluationMetrics,
    EvaluationRun,
    QueryEvaluation,
    RetrievalResult,
    SystemComparison,
    TestQuery,
)
from app.evaluation.rag import answer_relevance, citation_coverage, faithfulness
from app.evaluation.retrieval import reranker_lift
from app.evaluation.service import EvaluationService

__all__ = [
    # Models
    "TestQuery",
    "RetrievalResult",
    "EvaluationMetrics",
    "QueryEvaluation",
    "SystemComparison",
    "EvaluationRun",
    # Metrics
    "precision_at_k",
    "recall_at_k",
    "f1_at_k",
    "reciprocal_rank",
    "mean_reciprocal_rank",
    "ndcg_at_k",
    "calculate_all_metrics",
    "reranker_lift",
    "faithfulness",
    "answer_relevance",
    "citation_coverage",
    "router_decision_score",
    "agent_trace_summary",
    # Service
    "EvaluationService",
    # Data loading
    "load_test_queries",
    "save_test_queries",
    "filter_queries_by_category",
    "filter_queries_by_difficulty",
]
