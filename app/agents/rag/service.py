"""Concurrent typed retrieval adapter over the established local retrievers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from contextvars import ContextVar

from app.domain.contracts import RouteDecision, TaskPlan
from app.domain.events import ExecutionEvent
from app.domain.knowledge import AccessScope, KnowledgeSource, KnowledgeStrategy
from app.domain.workflow import ContextBundle
from app.knowledge.adapters import KnowledgeAdapter, build_default_adapters
from app.knowledge.orchestrator import KnowledgeOrchestrator
from app.orchestration.request import OrchestrationRequest

logger = logging.getLogger(__name__)

DegradationReporter = Callable[[ExecutionEvent], Awaitable[None]]

# Per-request degradation reporter, installed by the orchestration engine for the
# current async task. A ContextVar (not instance state) so RAGAgentService stays
# stateless and safe to share across concurrent requests: each request's task sees
# only the reporter it installed, never another request's.
_current_degradation_reporter: ContextVar[DegradationReporter | None] = ContextVar(
    "rag_current_degradation_reporter", default=None
)


def _default_retriever_timeout() -> float:
    """Bound one source with the same setting KnowledgeOrchestrator uses.

    This used to be a hardcoded 30s while the whole knowledge stage was capped at
    10s, so the inner timeout could never fire: the stage ceiling killed the
    request first. Deriving it from `KNOWLEDGE_SOURCE_TIMEOUT_MS` keeps the inner
    bound below the outer one by construction -- see
    tests/orchestration/test_timeout_degradation.py.
    """
    from app.core.config import get_settings

    return max(0.1, float(get_settings().knowledge_source_timeout_ms) / 1000.0)


# The module-level ThreadPoolExecutor that used to live here belonged to the
# four `_*_retrieve` thunks, which ran blocking retrievers through
# `run_in_executor`. `app/knowledge/adapters.py` uses `asyncio.to_thread`
# instead, so the pool had no remaining user; keeping it would have kept 50
# idle worker slots and an atexit hook alive for nothing.


class RetrieverSoftFailure(RuntimeError):
    """A legacy retriever returned an explicit failure payload."""


NOT_ATTEMPTED: frozenset[str] = frozenset({"EmptyAccessScope", "AdapterNotConfigured"})
"""Reasons a source never ran, as opposed to ran and failed.

Both are reported as `skipped`, and both are outside the degradation policy's
question: it asks how much of the retrieval this run *attempted* came back, and
a source that was never attempted belongs in neither the numerator nor the
denominator. Counting them made "this user has no documents" and "this
deployment has no graph store" indistinguishable from "the vector store threw".
"""


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


class RAGDegradationPolicy(ABC):
    """Policy for determining if retrieval degradation is acceptable.

    This policy determines when partial retrieval failures are acceptable
    versus when the entire RAG operation should fail.

    Abstract for real: it used to raise NotImplementedError without inheriting
    ABC, so the base class was instantiable and a subclass could forget the
    method without anyone noticing until a request hit it.
    """

    @abstractmethod
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


def _policy_from_settings() -> RAGDegradationPolicy:
    """Select the configured degradation policy.

    `RequireMinimumCountPolicy` and `RequireSpecificRetrieverPolicy` were written
    and then never reachable: nothing constructed them and nothing could ask for
    them. These two settings are how a deployment says "one source is not enough"
    or "this answer is meaningless without the graph".
    """

    from app.core.config import get_settings

    settings = get_settings()
    required = {name.strip() for name in str(settings.retrieval_required_sources or "").split(",") if name.strip()}
    if required:
        return RequireSpecificRetrieverPolicy(required)
    minimum = int(settings.retrieval_min_successful_sources)
    return RequireMinimumCountPolicy(minimum) if minimum > 1 else RequireAtLeastOnePolicy()


class RAGAgentService:
    """Backward-compatible facade that delegates execution to KnowledgeOrchestrator."""

    def __init__(
        self,
        *,
        adapters: Mapping[KnowledgeSource, KnowledgeAdapter] | None = None,
        report_degradation: DegradationReporter | None = None,
        retriever_timeout: float | None = None,
        degradation_policy: RAGDegradationPolicy | None = None,
    ) -> None:
        """Initialize the retrieval executor.

        Args:
            adapters: Overrides merged over ``build_default_adapters()``. Source
                *selection* is the Knowledge Agent's job; this class only runs
                what it was handed.
            report_degradation: Event reporter for degradation events (defaults to _discard_event)
            retriever_timeout: Timeout in seconds for individual retrievers; defaults to
                KNOWLEDGE_SOURCE_TIMEOUT_MS so it stays under the knowledge stage ceiling
            degradation_policy: Policy for acceptable degradation; defaults to the one
                RETRIEVAL_MIN_SUCCESSFUL_SOURCES / RETRIEVAL_REQUIRED_SOURCES select

        Raises:
            ValueError: If retriever_timeout is not positive
        """
        if retriever_timeout is None:
            retriever_timeout = _default_retriever_timeout()
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

        self._adapters = {**build_default_adapters(), **dict(adapters or {})}
        # Fallback used only when no per-request reporter was installed via
        # set_degradation_reporter (e.g. direct construction in a test/script).
        # Fixed at construction time, never mutated -- see _current_degradation_reporter
        # for the actual per-request path, which is what the engine uses in production.
        self._default_report_degradation = _discard_event if report_degradation is None else report_degradation
        self._retriever_timeout = retriever_timeout
        self._degradation_policy = degradation_policy or _policy_from_settings()

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
        strategy: KnowledgeStrategy,
        scope: AccessScope,
    ) -> ContextBundle:
        """Execute the Knowledge Agent's strategy and enforce the degradation policy.

        This class used to build its own strategy here -- always vector+BM25,
        graph only for two routes, `rewrite=False` -- which silently overrode
        whatever the Knowledge Agent had just decided. That is why `memory`,
        `wiki` and `multimodal` were unreachable on the chat path however the
        Knowledge Agent chose them, why query rewriting never ran, and why a
        verifier retry re-ran the identical search: the retry query lives in the
        strategy, and the strategy was thrown away.

        Selection now belongs entirely to the Knowledge Agent. What stays here is
        execution: bounding each source, running them, and deciding whether the
        result is acceptable.
        """

        # `plan` is genuinely unused *here*, and that is now the right shape
        # rather than the bug it used to be. The plan's sub-queries reach
        # retrieval through `KnowledgeStrategy.sources[].queries`, seeded by
        # `KnowledgeAgentService._source_plan`; this method executes a strategy
        # and has no business re-deriving one. Reading the plan again here is how
        # the two would disagree about what was searched.
        del plan
        if "rag" not in route.allowed_capabilities:
            return ContextBundle()

        bounded = strategy.model_copy(
            update={
                "sources": tuple(
                    source.model_copy(
                        update={"timeout_ms": min(source.timeout_ms, int(self._retriever_timeout * 1000))}
                    )
                    for source in strategy.sources
                )
            }
        )
        reporter = _current_degradation_reporter.get() or self._default_report_degradation
        # `enable_context_tracking` is enforced here rather than at the API edge:
        # this is the one place that decides what retrieval is allowed to know
        # about the session, so the flag cannot be honoured on one path and
        # forgotten on another.
        conversation = request.conversation if request.enable_context_tracking else ()
        context = await KnowledgeOrchestrator(adapters=self._adapters).retrieve(bounded, scope, reporter, conversation)

        status = dict(context.diagnostics.get("source_status", {}))
        errors = dict(context.diagnostics.get("source_error_type", {}))
        # A source that was never attempted is not a source that failed. The two
        # look identical in `source_status` -- both read "skipped" -- and judging
        # by that alone meant a user who has uploaded nothing had every document
        # source counted as a failure, so their first question raised
        # RetrievalFailureError and surfaced as a 500. An empty document scope is
        # a routine state that must return quietly; see "User Data Isolation" in
        # CLAUDE.md, which the API layer had no way to satisfy before this.
        attempted = {name for name in status if str(errors.get(name, "")) not in NOT_ATTEMPTED}
        if not attempted:
            return context
        failed = {str(name) for name in attempted if status[name] != "completed"}
        successful = len(attempted) - len(failed)
        if not self._degradation_policy.is_acceptable(successful, len(attempted), failed):
            raise RetrievalFailureError(len(attempted), failed, successful)
        return context


# `_legacy_adapter`, `_compatibility_scope`, `_retrieval_requests` and the four
# `_*_retrieve` thunks lived here to let this facade build its own restricted
# source set. They were a second, narrower copy of `app/knowledge/adapters.py`
# -- vector/BM25/graph/web only, no owner-aware wiki, memory or multimodal -- and
# keeping both is what let the narrower one silently win. Selection is the
# Knowledge Agent's job now and execution runs `build_default_adapters()`, so
# there is one implementation of each source instead of two.


async def _discard_event(event: ExecutionEvent) -> None:
    """Keep degradation optional until orchestration supplies a publisher."""
    del event
