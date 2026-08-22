"""Concurrent typed retrieval adapter over the established local retrievers."""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import logging
import threading
from collections.abc import Awaitable, Callable

from app.agents.rag.evidence_builder import (
    bundle_from_bm25_records,
    bundle_from_legacy_payload,
    bundle_from_vector_matches,
)
from app.agents.rag.fusion import fuse_evidence
from app.domain.contracts import EvidenceBundle, RouteDecision, TaskPlan
from app.domain.events import ExecutionEvent
from app.orchestration.request import OrchestrationRequest

logger = logging.getLogger(__name__)

TypedRetriever = Callable[[OrchestrationRequest, RouteDecision, TaskPlan | None], Awaitable[EvidenceBundle]]
DegradationReporter = Callable[[ExecutionEvent], Awaitable[None]]

# Default timeout for individual retriever operations (seconds)
DEFAULT_RETRIEVER_TIMEOUT = 30.0

# Overall timeout multiplier for concurrent retrieval operations
# Multiplied by individual retriever timeout to allow for retries and parallel execution
OVERALL_TIMEOUT_MULTIPLIER = 2.0

# Error message length limit for event reporting (characters)
# Longer messages are truncated to prevent excessive log output
ERROR_MESSAGE_MAX_LENGTH = 1000

# Thread pool management: lazy initialization to avoid resource leak
_retriever_pool: concurrent.futures.ThreadPoolExecutor | None = None
_pool_lock = threading.Lock()
_MAX_WORKERS = 50


def _get_retriever_pool() -> concurrent.futures.ThreadPoolExecutor:
    """Get or create the shared retriever thread pool.

    Uses lazy initialization to avoid creating threads at module import time.
    Thread pool is automatically cleaned up at program exit via atexit.

    Thread-safe: protected by lock to prevent race conditions.
    """
    global _retriever_pool

    if _retriever_pool is not None:
        return _retriever_pool

    with _pool_lock:
        # Double-check pattern: another thread might have created it
        if _retriever_pool is not None:
            return _retriever_pool

        _retriever_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=_MAX_WORKERS, thread_name_prefix="retriever"
        )

        # Register cleanup at program exit
        atexit.register(_shutdown_retriever_pool)

        return _retriever_pool


def _shutdown_retriever_pool() -> None:
    """Shutdown the retriever thread pool gracefully.

    Called automatically at program exit via atexit.
    Can also be called manually for testing or explicit cleanup.
    """
    global _retriever_pool

    if _retriever_pool is None:
        return

    with _pool_lock:
        if _retriever_pool is not None:
            try:
                _retriever_pool.shutdown(wait=True, cancel_futures=False)
            except Exception as e:
                # Suppress exceptions during shutdown to prevent atexit errors
                logger.debug(f"Exception during retriever pool shutdown: {e}")
                pass
            finally:
                _retriever_pool = None


class RetrieverSoftFailure(RuntimeError):
    """A legacy retriever returned an explicit failure payload."""


class RetrievalFailureError(Exception):
    """All retrieval attempts failed according to degradation policy.

    Attributes:
        total_attempts: Number of retrieval attempts made
        failed_retrievers: Set of retriever names that failed
        successful_attempts: Number of attempts that succeeded
    """

    def __init__(self, total_attempts: int, failed_retrievers: set[str], successful_attempts: int = 0):
        self.total_attempts = total_attempts
        self.failed_retrievers = failed_retrievers
        self.successful_attempts = successful_attempts

        # Generate accurate message based on success/failure counts
        if successful_attempts == 0:
            message = (
                f"All {total_attempts} retrieval attempts failed. "
                f"Failed retrievers: {', '.join(sorted(failed_retrievers))}. "
                f"Cannot proceed without evidence."
            )
        else:
            message = (
                f"Degradation policy violation: {successful_attempts}/{total_attempts} successful attempts "
                f"is not acceptable. Failed retrievers: {', '.join(sorted(failed_retrievers))}."
            )
        super().__init__(message)


class RAGDegradationPolicy:
    """Policy for determining if retrieval degradation is acceptable.

    This policy determines when partial retrieval failures are acceptable
    versus when the entire RAG operation should fail.

    Note: This is distinct from OrchestrationDegradationPolicy in
    app/orchestration/error_handling.py, which handles orchestration-level degradation.
    """

    def is_acceptable(
        self,
        successful_attempts: int,
        total_attempts: int,
        failed_retriever_names: set[str],
    ) -> bool:
        """Determine if the retrieval result is acceptable.

        Args:
            successful_attempts: Number of successful retrieval attempts
            total_attempts: Total number of attempts made
            failed_retriever_names: Set of retriever names that failed

        Returns:
            True if the result is acceptable, False if it should fail
        """
        raise NotImplementedError


class RequireAtLeastOnePolicy(RAGDegradationPolicy):
    """Default policy: require at least 1 successful retriever."""

    def is_acceptable(
        self,
        successful_attempts: int,
        total_attempts: int,
        failed_retriever_names: set[str],
    ) -> bool:
        return successful_attempts > 0


class RequireMinimumCountPolicy(RAGDegradationPolicy):
    """Require a minimum number of successful retrievers."""

    def __init__(self, minimum_successful: int):
        if minimum_successful < 1:
            raise ValueError(f"minimum_successful must be >= 1, got {minimum_successful}")
        self.minimum_successful = minimum_successful

    def is_acceptable(
        self,
        successful_attempts: int,
        total_attempts: int,
        failed_retriever_names: set[str],
    ) -> bool:
        return successful_attempts >= self.minimum_successful


class RequireSpecificRetrieverPolicy(RAGDegradationPolicy):
    """Require specific retrievers to succeed."""

    def __init__(self, required_retrievers: set[str]):
        if not required_retrievers:
            raise ValueError("required_retrievers cannot be empty")
        # Validate retriever names (warn about unknown names)
        valid_names = {"vector", "bm25", "graph", "web"}
        invalid = required_retrievers - valid_names
        if invalid:
            import warnings

            warnings.warn(
                f"Unknown retriever names in required_retrievers: {invalid}. Valid names are: {valid_names}",
                UserWarning,
                stacklevel=2,
            )
        self.required_retrievers = required_retrievers

    def is_acceptable(
        self,
        successful_attempts: int,
        total_attempts: int,
        failed_retriever_names: set[str],
    ) -> bool:
        # Check if any required retriever failed
        return not (self.required_retrievers & failed_retriever_names)


class RAGAgentService:
    """Run enabled vector, graph, and web retrievers concurrently, then fuse their evidence.

    Concurrent execution: All enabled retrievers run in parallel using asyncio.gather.
    Timeout behavior: Each retriever has a default 30s timeout. The entire retrieve()
                     operation has an overall timeout to prevent indefinite blocking.
    Thread safety: set_degradation_reporter() is NOT thread-safe. Call it during
                  initialization, not during concurrent retrieve() calls.
    Degradation policy: Configurable via degradation_policy parameter (default: RequireAtLeastOnePolicy).
                       Raises RetrievalFailureError if policy is violated.
    Resource management: Uses a shared thread pool (max 50 workers) for synchronous retrievers.
    """

    def __init__(
        self,
        *,
        vector: TypedRetriever | None = None,
        bm25: TypedRetriever | None = None,
        graph: TypedRetriever | None = None,
        web: TypedRetriever | None = None,
        report_degradation: DegradationReporter | None = None,
        retriever_timeout: float = DEFAULT_RETRIEVER_TIMEOUT,
        degradation_policy: RAGDegradationPolicy | None = None,
    ) -> None:
        """Initialize RAG agent service with typed retrievers.

        Args:
            vector: Vector similarity retriever (defaults to _vector_retrieve)
            bm25: BM25 keyword retriever (defaults to _bm25_retrieve)
            graph: Knowledge graph retriever (defaults to _graph_retrieve)
            web: Web search retriever (defaults to _web_retrieve)
            report_degradation: Event reporter for degradation events (defaults to _discard_event)
            retriever_timeout: Timeout in seconds for individual retrievers (default: 30.0, must be > 0)
            degradation_policy: Policy for acceptable degradation (defaults to RequireAtLeastOnePolicy)

        Raises:
            ValueError: If retriever_timeout is not positive
        """
        if retriever_timeout <= 0:
            raise ValueError(f"retriever_timeout must be positive, got {retriever_timeout}")
        if retriever_timeout > 300:  # 5 minutes
            import warnings

            warnings.warn(
                f"retriever_timeout={retriever_timeout}s is very large (>5min). "
                f"Consider using a smaller timeout to prevent long waits.",
                UserWarning,
                stacklevel=2,
            )

        self._vector = _vector_retrieve if vector is None else vector
        self._bm25 = _bm25_retrieve if bm25 is None else bm25
        self._graph = _graph_retrieve if graph is None else graph
        self._web = _web_retrieve if web is None else web
        self._report_degradation = _discard_event if report_degradation is None else report_degradation
        self._retriever_timeout = retriever_timeout
        self._degradation_policy = RequireAtLeastOnePolicy() if degradation_policy is None else degradation_policy
        self._reporter_lock = threading.Lock()

    def set_degradation_reporter(self, reporter: DegradationReporter) -> None:
        """Bind the engine publisher after typed services are assembled.

        WARNING: This method should only be called during initialization.
        Thread-safe via lock, but concurrent calls during active retrieve()
        operations may cause inconsistent event reporting.
        """
        with self._reporter_lock:
            self._report_degradation = reporter

    async def retrieve(
        self,
        request: OrchestrationRequest,
        route: RouteDecision,
        plan: TaskPlan | None,
    ) -> EvidenceBundle:
        """Retrieve every permitted source for each retrieval-enabled planned task.

        Applies degradation policy to determine if partial failures are acceptable.
        All retrievers run concurrently with individual timeouts.

        Args:
            request: The orchestration request
            route: Routing decision with allowed capabilities
            plan: Optional task plan for multi-step retrieval

        Returns:
            Fused evidence bundle from all successful retrievers

        Raises:
            RetrievalFailureError: If all retrieval attempts fail (degradation policy violation)
            asyncio.TimeoutError: If overall retrieval exceeds timeout
        """
        # Early return: RAG not allowed
        if "rag" not in route.allowed_capabilities:
            return EvidenceBundle()

        # Early return: explicitly empty allowed sources
        if request.source_scope.allowed_sources is not None and not request.source_scope.allowed_sources:
            return EvidenceBundle()

        retrievers = self._enabled_retrievers(route)
        requests = _retrieval_requests(request, plan, len(retrievers))
        jobs = [
            (name, retriever, planned_request)
            for planned_request, max_retrievals in requests
            for name, retriever in retrievers[:max_retrievals]
        ]

        # Early return: no retrieval jobs to execute
        if not jobs:
            return EvidenceBundle()

        total_attempts = len(jobs)

        # Execute all retrievers concurrently with individual timeouts
        # Overall timeout uses multiplier to allow for retries and parallel execution
        overall_timeout = self._retriever_timeout * OVERALL_TIMEOUT_MULTIPLIER
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    *(
                        self._run_retriever_with_timeout(retriever, planned_request, route, plan, name)
                        for name, retriever, planned_request in jobs
                    ),
                    return_exceptions=True,
                ),
                timeout=overall_timeout,
            )
        except TimeoutError:
            # Overall timeout exceeded - report and raise
            await self._report_degradation(
                ExecutionEvent(
                    stage="rag", status="failed", message=f"Overall retrieval timeout exceeded ({overall_timeout}s)"
                )
            )
            raise

        bundles: list[EvidenceBundle] = []
        failed_retrievers: list[str] = []

        for (name, _, _), result in zip(jobs, results, strict=True):
            if isinstance(result, BaseException):
                failed_retrievers.append(name)
                # Truncate long error messages for event reporting
                # Full error is still available in exception traceback for debugging
                error_msg = str(result)
                if len(error_msg) > ERROR_MESSAGE_MAX_LENGTH:
                    error_msg = error_msg[:ERROR_MESSAGE_MAX_LENGTH] + "... (truncated)"
                await self._report_degradation(
                    ExecutionEvent(
                        stage="rag", status="skipped", message=f"{name}: {type(result).__name__}: {error_msg}"
                    )
                )
                continue

            # Defensive: validate result type
            if not isinstance(result, EvidenceBundle):
                failed_retrievers.append(name)
                await self._report_degradation(
                    ExecutionEvent(
                        stage="rag",
                        status="skipped",
                        message=f"{name}: returned invalid type {type(result).__name__}, expected EvidenceBundle",
                    )
                )
                continue

            bundles.append(result)

        successful_attempts = len(bundles)
        fused = fuse_evidence(bundles)
        evidence_count = len(fused.items)

        # Calculate unique failed retrievers once
        unique_failed = set(failed_retrievers)

        # Apply degradation policy
        if not self._degradation_policy.is_acceptable(successful_attempts, total_attempts, unique_failed):
            raise RetrievalFailureError(
                total_attempts=total_attempts, failed_retrievers=unique_failed, successful_attempts=successful_attempts
            )

        # Report degradation if no documents found
        if evidence_count == 0:
            await self._report_degradation(
                ExecutionEvent(
                    stage="rag",
                    status="completed",
                    message=(
                        f"DEGRADED: {successful_attempts}/{total_attempts} retrieval attempts succeeded "
                        f"but found no matching documents. Will proceed with fallback synthesis."
                    ),
                )
            )

        # Report degradation if some retrievers failed
        if failed_retrievers:
            await self._report_degradation(
                ExecutionEvent(
                    stage="rag",
                    status="completed",
                    message=(
                        f"DEGRADED: Partial retrieval success: {successful_attempts}/{total_attempts} attempts, "
                        f"{evidence_count} evidence items. Failed: {', '.join(sorted(unique_failed))}"
                    ),
                )
            )

        return fused

    async def _run_retriever_with_timeout(
        self,
        retriever: TypedRetriever,
        request: OrchestrationRequest,
        route: RouteDecision,
        plan: TaskPlan | None,
        name: str,
    ) -> EvidenceBundle:
        """Run a single retriever with timeout protection.

        Args:
            retriever: The retriever function to execute
            request: Orchestration request
            route: Route decision
            plan: Task plan
            name: Retriever name (for error reporting)

        Returns:
            Evidence bundle from the retriever

        Raises:
            asyncio.TimeoutError: If retriever exceeds individual timeout
            Exception: Any exception raised by the retriever
        """
        try:
            return await asyncio.wait_for(retriever(request, route, plan), timeout=self._retriever_timeout)
        except TimeoutError as e:
            # Re-raise as asyncio.TimeoutError with descriptive message
            raise TimeoutError(f"{name} retriever exceeded timeout ({self._retriever_timeout}s)") from e

    def _enabled_retrievers(self, route: RouteDecision) -> tuple[tuple[str, TypedRetriever], ...]:
        retrievers: list[tuple[str, TypedRetriever]] = [("vector", self._vector), ("bm25", self._bm25)]
        if route.intent == "hybrid":
            retrievers.append(("graph", self._graph))
        if "web" in route.allowed_capabilities:
            retrievers.append(("web", self._web))
        return tuple(retrievers)


def _retrieval_requests(
    request: OrchestrationRequest, plan: TaskPlan | None, available_retrievers: int
) -> tuple[tuple[OrchestrationRequest, int], ...]:
    """Build retrieval requests from plan tasks or use the original request.

    Args:
        request: Base orchestration request
        plan: Optional task plan with retrieval budgets
        available_retrievers: Number of available retrievers

    Returns:
        Tuple of (request, max_retrievers) pairs for each retrieval task.
        Always returns at least one request (the original) if plan has no valid tasks.
    """
    if plan is None:
        return ((request, available_retrievers),)

    result = []
    for task in plan.tasks:
        if not task.retrieval_required:
            continue
        if task.budget.max_retrievals <= 0:
            continue

        # Use task prompt if provided and non-empty
        task_question = request.question
        if task.prompt and task.prompt.strip():
            task_question = task.prompt

        task_request = request.model_copy(update={"question": task_question})
        max_retrievers = min(task.budget.max_retrievals, available_retrievers)
        result.append((task_request, max_retrievers))

    # Fallback: if plan has no valid retrieval tasks, use original request
    if not result:
        return ((request, available_retrievers),)

    return tuple(result)


async def _discard_event(event: ExecutionEvent) -> None:
    """Keep degradation optional until orchestration supplies a publisher."""
    del event


def _get_allowed_sources(request: OrchestrationRequest) -> list[str] | None:
    """Extract allowed sources from request, converting to list if present.

    Args:
        request: Orchestration request with source scope

    Returns:
        List of allowed sources, or None if unrestricted
    """
    if request.source_scope.allowed_sources:
        return list(request.source_scope.allowed_sources)
    return None


async def _bm25_retrieve(
    request: OrchestrationRequest,
    route: RouteDecision,
    plan: TaskPlan | None,
) -> EvidenceBundle:
    """BM25 keyword-based retrieval."""
    del route, plan
    from app.retrievers.bm25_retriever import bm25_search

    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(
        _get_retriever_pool(),
        bm25_search,
        request.question,  # query: str
        6,  # k: int (default number of results)
        _get_allowed_sources(request),  # allowed_sources: list[str] | None
        # use_chinese_tokenizer: bool uses default True
    )
    return bundle_from_bm25_records(records)


async def _vector_retrieve(
    request: OrchestrationRequest,
    route: RouteDecision,
    plan: TaskPlan | None,
) -> EvidenceBundle:
    """Vector similarity retrieval."""
    del route, plan
    from app.retrievers.vector_store import similarity_search

    loop = asyncio.get_event_loop()
    matches = await loop.run_in_executor(
        _get_retriever_pool(),
        similarity_search,
        request.question,  # query: str
        None,  # k: int | None (use default)
        _get_allowed_sources(request),  # allowed_sources: list[str] | None
        False,  # require_source_filter: bool (don't fail if no sources)
    )
    return bundle_from_vector_matches(matches)


async def _graph_retrieve(
    request: OrchestrationRequest,
    route: RouteDecision,
    plan: TaskPlan | None,
) -> EvidenceBundle:
    """Knowledge graph retrieval."""
    del route, plan
    from app.agents.rag.graph import run_graph_rag

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _get_retriever_pool(),
        run_graph_rag,
        request.question,
        _get_allowed_sources(request),
        request.source_scope.agent_class_hint,
    )
    return bundle_from_legacy_payload(result, "graph", fallback_document_id=f"graph:{request.question}")


async def _web_retrieve(
    request: OrchestrationRequest,
    route: RouteDecision,
    plan: TaskPlan | None,
) -> EvidenceBundle:
    """Web search retrieval."""
    del route, plan
    from app.agents.rag.web import run_web_research

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _get_retriever_pool(),
        run_web_research,
        request.question,
        request.actor.user_id if request.actor else None,
        request.session_id,
    )
    return bundle_from_legacy_payload(result, "web")
