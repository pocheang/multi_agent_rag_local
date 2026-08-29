"""Concurrent typed retrieval adapter over the established local retrievers."""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import logging
import threading
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from app.agents.rag.evidence_builder import (
    bundle_from_bm25_records,
    bundle_from_legacy_payload,
    bundle_from_vector_matches,
)
from app.domain.contracts import EvidenceBundle, RouteDecision, TaskPlan
from app.domain.events import ExecutionEvent
from app.domain.knowledge import AccessScope, KnowledgeSource, KnowledgeSourcePlan, KnowledgeStrategy
from app.knowledge.adapters import CallableKnowledgeAdapter
from app.knowledge.orchestrator import KnowledgeOrchestrator
from app.orchestration.request import OrchestrationRequest
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS

logger = logging.getLogger(__name__)

TypedRetriever = Callable[[OrchestrationRequest, RouteDecision, TaskPlan | None], Awaitable[EvidenceBundle]]
DegradationReporter = Callable[[ExecutionEvent], Awaitable[None]]

# Per-request degradation reporter, installed by the orchestration engine for the
# current async task. A ContextVar (not instance state) so RAGAgentService stays
# stateless and safe to share across concurrent requests: each request's task sees
# only the reporter it installed, never another request's.
_current_degradation_reporter: ContextVar[DegradationReporter | None] = ContextVar(
    "rag_current_degradation_reporter", default=None
)

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
    """Backward-compatible facade that delegates execution to KnowledgeOrchestrator."""

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
        # Fallback used only when no per-request reporter was installed via
        # set_degradation_reporter (e.g. direct construction in a test/script).
        # Fixed at construction time, never mutated -- see _current_degradation_reporter
        # for the actual per-request path, which is what the engine uses in production.
        self._default_report_degradation = _discard_event if report_degradation is None else report_degradation
        self._retriever_timeout = retriever_timeout
        self._degradation_policy = RequireAtLeastOnePolicy() if degradation_policy is None else degradation_policy

    def set_degradation_reporter(self, reporter: DegradationReporter) -> None:
        """Install the degradation reporter for the current request.

        Stores the reporter in a ContextVar scoped to the current async task rather
        than on `self`, so this RAGAgentService instance stays stateless and safe to
        share across concurrent requests -- each request's task sees only the
        reporter it installed here, never one from a different request.
        """
        _current_degradation_reporter.set(reporter)

    async def retrieve(
        self,
        request: OrchestrationRequest,
        route: RouteDecision,
        plan: TaskPlan | None,
    ) -> EvidenceBundle:
        """Translate the legacy request contract and proxy it to the canonical service."""

        if "rag" not in route.allowed_capabilities:
            return EvidenceBundle()
        if request.source_scope.allowed_sources is not None and not request.source_scope.allowed_sources:
            return EvidenceBundle()

        enabled: list[tuple[KnowledgeSource, TypedRetriever]] = [
            ("vector", self._vector),
            ("bm25", self._bm25),
        ]
        if route.effective_route in {"graph", "hybrid"}:
            enabled.append(("graph", self._graph))
        if "web" in route.allowed_capabilities:
            enabled.append(("web", self._web))

        source_queries: dict[KnowledgeSource, list[str]] = {name: [] for name, _ in enabled}
        for planned_request, max_retrievals in _retrieval_requests(request, plan, len(enabled)):
            for name, _ in enabled[:max_retrievals]:
                source_queries[name].append(planned_request.question)
        selected = tuple((name, retriever) for name, retriever in enabled if source_queries[name])
        if not selected:
            return EvidenceBundle(route=route, plan=plan)

        adapters = {
            name: CallableKnowledgeAdapter(
                name,
                _legacy_adapter(name, retriever, request=request, route=route, task_plan=plan),
            )
            for name, retriever in selected
        }
        strategy = KnowledgeStrategy(
            sources=tuple(
                KnowledgeSourcePlan(
                    source=name,
                    queries=tuple(dict.fromkeys(source_queries[name])),
                    top_k=6,
                    timeout_ms=max(100, int(self._retriever_timeout * 1000)),
                    required=name in {"vector", "bm25"},
                )
                for name, _ in selected
            ),
            rewrite=False,
            rerank=len(selected) > 1,
            rationale="legacy RAG compatibility proxy",
        )
        reporter = _current_degradation_reporter.get() or self._default_report_degradation
        context = await KnowledgeOrchestrator(adapters=adapters).retrieve(
            strategy,
            _compatibility_scope(request),
            reporter,
        )
        status = dict(context.diagnostics.get("source_status", {}))
        failed = {str(name) for name, value in status.items() if value != "completed"}
        successful = len(status) - len(failed)
        if not self._degradation_policy.is_acceptable(successful, len(status), failed):
            raise RetrievalFailureError(len(status), failed, successful)
        return EvidenceBundle(
            route=route,
            plan=plan,
            items=context.evidence,
            diagnostics=context.diagnostics,
        )


def _legacy_adapter(
    source: KnowledgeSource,
    retriever: TypedRetriever,
    *,
    request: OrchestrationRequest,
    route: RouteDecision,
    task_plan: TaskPlan | None,
):
    """Adapt an injected legacy retriever without reimplementing orchestration."""

    async def retrieve(source_plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple:
        del scope
        bundles = await asyncio.gather(
            *(
                retriever(request.model_copy(update={"question": query}), route, task_plan)
                for query in source_plan.queries
            )
        )
        items = []
        for bundle in bundles:
            if not isinstance(bundle, EvidenceBundle):
                raise TypeError(f"{source} retriever must return EvidenceBundle")
            for item in bundle.items:
                updates = {"retriever": source}
                if source == "web":
                    updates["layer"] = "web"
                items.append(item.model_copy(update=updates))
        return tuple(items)

    return retrieve


def _compatibility_scope(request: OrchestrationRequest) -> AccessScope:
    """Build a fail-closed scope from the legacy request's already-authorized filters."""

    actor = request.actor
    user_id = str(actor.user_id if actor and actor.user_id else "legacy").strip()
    tenant_id = str(actor.tenant_id if actor and actor.tenant_id else user_id).strip()
    return AccessScope(
        tenant_id=tenant_id,
        user_id=user_id,
        role=str(actor.role if actor and actor.role else "viewer"),
        permissions=actor.permissions if actor else frozenset(),
        document_ids=request.source_scope.document_ids or frozenset(),
        allowed_sources=request.source_scope.allowed_sources or frozenset(),
        acl_tags=request.source_scope.acl_tags or frozenset(),
        allowed_fields=request.source_scope.allowed_fields or DEFAULT_CONTEXT_FIELDS,
    )


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
    from app.retrievers.stores.vector import similarity_search

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
