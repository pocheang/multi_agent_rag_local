"""
Web Research Agent Utilities

Additional helper functions for web research agent:
- Result validation
- Parallel search
- Cache management
- Metrics tracking
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.observability.log_safety import question_ref

logger = logging.getLogger(__name__)


def validate_url(url: str) -> bool:
    """
    Validate if a URL is safe to access.

    Args:
        url: URL to validate

    Returns:
        True if URL is valid and safe, False otherwise
    """
    if not url:
        return False

    # Basic validation
    if not url.startswith(("http://", "https://")):
        return False

    # Check for suspicious patterns
    suspicious_patterns = [
        "javascript:",
        "data:",
        "file://",
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
    ]

    url_lower = url.lower()
    for pattern in suspicious_patterns:
        if pattern in url_lower:
            logger.warning(f"Suspicious URL detected: {url}")
            return False

    return True


def run_parallel_web_research(questions: list[str], max_workers: int = 3, timeout_per_query: int = 30) -> list[dict]:
    """
    Execute multiple web searches in parallel.

    Args:
        questions: List of search queries
        max_workers: Maximum number of parallel workers (default: 3)
        timeout_per_query: Timeout per query in seconds (default: 30)

    Returns:
        List of search results, one dict per query

    Example:
        >>> queries = ["What is RAG?", "What is LangChain?"]
        >>> results = run_parallel_web_research(queries)
        >>> for i, result in enumerate(results):
        ...     print(f"Query {i+1}: {len(result['citations'])} results")
    """
    from app.agents.rag.web import run_web_research

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_question = {executor.submit(run_web_research, q): q for q in questions}

        for future in as_completed(future_to_question, timeout=timeout_per_query * len(questions)):
            question = future_to_question[future]
            try:
                result = future.result(timeout=timeout_per_query)
                results.append(result)
                logger.info("Parallel search completed for %s", question_ref(question))
            except Exception as e:
                logger.exception("Parallel search failed for %s: %s", question_ref(question), e)
                results.append(
                    {
                        "context": "",
                        "citations": [],
                        "used": False,
                        "error": f"parallel_search_error:{type(e).__name__}",
                    }
                )

    return results


def is_time_sensitive_query(question: str) -> bool:
    """
    Detect if a query is time-sensitive.

    Args:
        question: User query

    Returns:
        True if query likely requires latest information

    Example:
        >>> is_time_sensitive_query("What is the latest AI news?")
        True
        >>> is_time_sensitive_query("What is Python?")
        False
    """
    time_keywords = [
        "latest",
        "recent",
        "current",
        "today",
        "now",
        "this week",
        "this month",
        "this year",
        "2026",
        "new",
        "breaking",
        "update",
        "recently",
        "just released",
        "announcement",
        "最新",
        "今天",
        "当前",
        "最近",
        "本月",
        "本周",
        "今年",
    ]

    question_lower = question.lower()
    return any(keyword in question_lower for keyword in time_keywords)


class WebSearchMetrics:
    """Track web search performance metrics."""

    def __init__(self):
        self.total_searches = 0
        self.successful_searches = 0
        self.failed_searches = 0
        self.total_results = 0
        self.filtered_results = 0
        self.total_time = 0.0
        self.sanitized_queries = 0

    def record_search(self, result: dict):
        """Record metrics from a search result."""
        self.total_searches += 1

        if result.get("used"):
            self.successful_searches += 1
        else:
            self.failed_searches += 1

        metrics = result.get("metrics", {})
        if metrics:
            self.total_results += metrics.get("total_results", 0)
            self.filtered_results += metrics.get("filtered_results", 0)
            self.total_time += metrics.get("search_time", 0.0) + metrics.get("filter_time", 0.0)
            if metrics.get("sanitized"):
                self.sanitized_queries += 1

    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_searches == 0:
            return 0.0
        return (self.successful_searches / self.total_searches) * 100

    def get_average_time(self) -> float:
        """Get average search time in seconds."""
        if self.total_searches == 0:
            return 0.0
        return self.total_time / self.total_searches

    def get_filter_rate(self) -> float:
        """Get filter rate as percentage."""
        if self.total_results == 0:
            return 0.0
        return (self.filtered_results / self.total_results) * 100

    def get_summary(self) -> dict:
        """Get summary of all metrics."""
        return {
            "total_searches": self.total_searches,
            "successful_searches": self.successful_searches,
            "failed_searches": self.failed_searches,
            "success_rate": round(self.get_success_rate(), 2),
            "total_results": self.total_results,
            "filtered_results": self.filtered_results,
            "filter_rate": round(self.get_filter_rate(), 2),
            "average_time": round(self.get_average_time(), 2),
            "sanitized_queries": self.sanitized_queries,
        }

    def __str__(self) -> str:
        """String representation of metrics."""
        summary = self.get_summary()
        return (
            f"Web Search Metrics:\n"
            f"  Total: {summary['total_searches']} "
            f"(Success: {summary['successful_searches']}, "
            f"Failed: {summary['failed_searches']})\n"
            f"  Success Rate: {summary['success_rate']}%\n"
            f"  Results: {summary['total_results']} total, "
            f"{summary['filtered_results']} filtered ({summary['filter_rate']}%)\n"
            f"  Avg Time: {summary['average_time']}s\n"
            f"  Sanitized: {summary['sanitized_queries']} queries"
        )


# Global metrics instance
_global_metrics = WebSearchMetrics()


def get_metrics() -> WebSearchMetrics:
    """Get global metrics instance."""
    return _global_metrics


def reset_metrics():
    """Reset global metrics."""
    global _global_metrics
    _global_metrics = WebSearchMetrics()
