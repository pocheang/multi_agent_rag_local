"""
RetrievalLogger Service

Tracks retrieval performance, agent usage, and document popularity for the RAG system.
Provides statistics aggregation and export functionality.
"""

import csv
import io
import json
import threading
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Optional

from pydantic import BaseModel, Field


def utcnow():
    """Get current UTC timestamp."""
    return datetime.now(UTC)


class RetrievalLog(BaseModel):
    """
    Represents a single retrieval event with metrics and metadata.
    """

    log_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=utcnow)
    question: str
    agent_class: str  # cybersecurity, artificial_intelligence, general
    route: str  # vector, graph, web, hybrid

    # Retrieval metrics
    filtered_docs_count: int  # Documents after agent filter
    retrieved_count: int  # Actually retrieved documents
    effective_hit_count: int  # Relevant hits (score > threshold)
    top_scores: list[float]  # Top 3 relevance scores

    # Performance metrics
    retrieval_time_ms: float  # Retrieval time in milliseconds
    total_time_ms: float  # Total time in milliseconds

    # Document info
    retrieved_sources: list[str]  # Retrieved document filenames

    # Result status
    has_result: bool  # Whether results were found
    error: str | None = None  # Error message if failed


class AnalyticsOverview(BaseModel):
    """
    High-level analytics overview of all retrieval operations.
    """

    total_queries: int
    success_rate: float  # 0-100
    avg_retrieval_time_ms: float
    avg_total_time_ms: float
    avg_retrieved_count: float
    avg_effective_hit_count: float

    agent_distribution: dict[str, int]  # {"cybersecurity": 50, ...}
    route_distribution: dict[str, int]  # {"vector": 60, ...}

    time_range_start: datetime | None = None
    time_range_end: datetime | None = None


class AgentStats(BaseModel):
    """
    Performance statistics for a specific agent.
    """

    agent_class: str
    query_count: int
    success_rate: float  # 0-100
    avg_retrieval_time_ms: float
    avg_total_time_ms: float
    avg_retrieved_count: float
    avg_effective_hit_count: float
    avg_top_score: float


class DocumentStats(BaseModel):
    """
    Usage statistics for a specific document.
    """

    source: str  # Document name
    retrieval_count: int  # Times retrieved
    avg_score: float  # Average relevance score
    agent_usage: dict[str, int]  # Usage by agent


class RetrievalLogger:
    """
    Singleton service for logging and analyzing retrieval operations.

    Thread-safe implementation using deque for efficient log storage
    with automatic size limiting (maxlen=1000).
    """

    _instance: Optional["RetrievalLogger"] = None
    _lock = threading.Lock()

    def __init__(self):
        """Initialize the logger with thread-safe storage."""
        self._logs: deque[RetrievalLog] = deque(maxlen=1000)
        self._logs_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "RetrievalLogger":
        """
        Get the singleton instance of RetrievalLogger.

        Returns:
            RetrievalLogger: The singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def log_retrieval(self, log: RetrievalLog) -> None:
        """
        Log a retrieval event.

        Args:
            log: RetrievalLog instance containing event data
        """
        with self._logs_lock:
            self._logs.append(log)

    def get_overview(self) -> AnalyticsOverview:
        """
        Get high-level analytics overview.

        Returns:
            AnalyticsOverview: Aggregated statistics across all logs
        """
        with self._logs_lock:
            logs = list(self._logs)

        if not logs:
            return AnalyticsOverview(
                total_queries=0,
                success_rate=0.0,
                avg_retrieval_time_ms=0.0,
                avg_total_time_ms=0.0,
                avg_retrieved_count=0.0,
                avg_effective_hit_count=0.0,
                agent_distribution={},
                route_distribution={},
                time_range_start=None,
                time_range_end=None,
            )

        total_queries = len(logs)
        successful_queries = sum(1 for log in logs if log.has_result)
        success_rate = (successful_queries / total_queries) * 100

        avg_retrieval_time_ms = sum(log.retrieval_time_ms for log in logs) / total_queries
        avg_total_time_ms = sum(log.total_time_ms for log in logs) / total_queries
        avg_retrieved_count = sum(log.retrieved_count for log in logs) / total_queries
        avg_effective_hit_count = sum(log.effective_hit_count for log in logs) / total_queries

        # Agent distribution
        agent_distribution: dict[str, int] = defaultdict(int)
        for log in logs:
            agent_distribution[log.agent_class] += 1

        # Route distribution
        route_distribution: dict[str, int] = defaultdict(int)
        for log in logs:
            route_distribution[log.route] += 1

        # Time range
        timestamps = [log.timestamp for log in logs]
        time_range_start = min(timestamps)
        time_range_end = max(timestamps)

        return AnalyticsOverview(
            total_queries=total_queries,
            success_rate=success_rate,
            avg_retrieval_time_ms=avg_retrieval_time_ms,
            avg_total_time_ms=avg_total_time_ms,
            avg_retrieved_count=avg_retrieved_count,
            avg_effective_hit_count=avg_effective_hit_count,
            agent_distribution=dict(agent_distribution),
            route_distribution=dict(route_distribution),
            time_range_start=time_range_start,
            time_range_end=time_range_end,
        )

    def get_agent_stats(self) -> list[AgentStats]:
        """
        Get performance statistics for each agent.

        Returns:
            list[AgentStats]: List of agent statistics, sorted by query_count descending
        """
        with self._logs_lock:
            logs = list(self._logs)

        if not logs:
            return []

        # Group logs by agent
        agent_logs: dict[str, list[RetrievalLog]] = defaultdict(list)
        for log in logs:
            agent_logs[log.agent_class].append(log)

        # Calculate stats for each agent
        stats_list = []
        for agent_class, agent_log_list in agent_logs.items():
            query_count = len(agent_log_list)
            successful = sum(1 for log in agent_log_list if log.has_result)
            success_rate = (successful / query_count) * 100

            avg_retrieval_time_ms = sum(log.retrieval_time_ms for log in agent_log_list) / query_count
            avg_total_time_ms = sum(log.total_time_ms for log in agent_log_list) / query_count
            avg_retrieved_count = sum(log.retrieved_count for log in agent_log_list) / query_count
            avg_effective_hit_count = sum(log.effective_hit_count for log in agent_log_list) / query_count

            # Calculate average top score (first score in top_scores)
            top_scores = [log.top_scores[0] for log in agent_log_list if log.top_scores]
            avg_top_score = sum(top_scores) / len(top_scores) if top_scores else 0.0

            stats_list.append(
                AgentStats(
                    agent_class=agent_class,
                    query_count=query_count,
                    success_rate=success_rate,
                    avg_retrieval_time_ms=avg_retrieval_time_ms,
                    avg_total_time_ms=avg_total_time_ms,
                    avg_retrieved_count=avg_retrieved_count,
                    avg_effective_hit_count=avg_effective_hit_count,
                    avg_top_score=avg_top_score,
                )
            )

        # Sort by query_count descending
        stats_list.sort(key=lambda x: x.query_count, reverse=True)
        return stats_list

    def get_document_stats(self, limit: int = 20) -> list[DocumentStats]:
        """
        Get usage statistics for documents.

        Args:
            limit: Maximum number of documents to return (default: 20)

        Returns:
            list[DocumentStats]: List of document statistics, sorted by retrieval_count descending
        """
        with self._logs_lock:
            logs = list(self._logs)

        if not logs:
            return []

        # Track document statistics
        doc_retrieval_count: dict[str, int] = defaultdict(int)
        doc_scores: dict[str, list[float]] = defaultdict(list)
        doc_agent_usage: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for log in logs:
            for idx, source in enumerate(log.retrieved_sources):
                doc_retrieval_count[source] += 1
                doc_agent_usage[source][log.agent_class] += 1

                # Get the corresponding score for this document
                if idx < len(log.top_scores):
                    doc_scores[source].append(log.top_scores[idx])

        # Build stats list
        stats_list = []
        for source, retrieval_count in doc_retrieval_count.items():
            scores = doc_scores[source]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            stats_list.append(
                DocumentStats(
                    source=source,
                    retrieval_count=retrieval_count,
                    avg_score=avg_score,
                    agent_usage=dict(doc_agent_usage[source]),
                )
            )

        # Sort by retrieval_count descending and apply limit
        stats_list.sort(key=lambda x: x.retrieval_count, reverse=True)
        return stats_list[:limit]

    def export_logs(self, format: str = "json") -> str:
        """
        Export logs in the specified format.

        Args:
            format: Export format, either "json" or "csv"

        Returns:
            str: Exported data as a string

        Raises:
            ValueError: If format is not supported
        """
        with self._logs_lock:
            logs = list(self._logs)

        if format == "json":
            return self._export_json(logs)
        elif format == "csv":
            return self._export_csv(logs)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'json' or 'csv'.")

    def _export_json(self, logs: list[RetrievalLog]) -> str:
        """
        Export logs as JSON.

        Args:
            logs: List of RetrievalLog instances

        Returns:
            str: JSON string
        """
        data = [log.model_dump(mode="json") for log in logs]
        return json.dumps(data, indent=2, default=str)

    def _export_csv(self, logs: list[RetrievalLog]) -> str:
        """
        Export logs as CSV.

        Args:
            logs: List of RetrievalLog instances

        Returns:
            str: CSV string
        """
        output = io.StringIO()

        if not logs:
            # Return header only
            fieldnames = [
                "log_id",
                "timestamp",
                "question",
                "agent_class",
                "route",
                "filtered_docs_count",
                "retrieved_count",
                "effective_hit_count",
                "top_scores",
                "retrieval_time_ms",
                "total_time_ms",
                "retrieved_sources",
                "has_result",
                "error",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            return output.getvalue()

        # Convert logs to dictionaries
        rows = []
        for log in logs:
            row = log.model_dump(mode="json")
            # Convert lists to JSON strings for CSV compatibility
            row["top_scores"] = json.dumps(row["top_scores"])
            row["retrieved_sources"] = json.dumps(row["retrieved_sources"])
            rows.append(row)

        # Write CSV
        fieldnames = rows[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

        return output.getvalue()
