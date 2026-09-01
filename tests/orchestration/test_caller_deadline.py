"""A caller's deadline has to reach the budget -- and may only ever narrow it.

`OrchestrationRequest.deadline_at` was accepted, forwarded through
`PipelineRequest`, and read by nobody: a caller saying "stop at T" was silently
ignored while the run spent the full `STAGE_TIMEOUT_TOTAL_MS`.

The same wiring publishes the budget to `app.services.runtime.request_context`,
which the LLM query rewriter and the synthesizer's self-review and
fact-verification exits check on their own. Nothing on the request path had ever
set it, so `remaining_seconds()` returned None -- and `_llm_rewrite` reads None
as "no time left", which made `QUERY_REWRITE_WITH_LLM` a switch that could not
turn anything on.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.orchestration.timeout_control import (
    MANDATORY_STAGES,
    ExecutionBudget,
    StageTimeoutError,
    TimeoutConfig,
    deadline_offset_ms,
)


def _config() -> TimeoutConfig:
    return TimeoutConfig()


class TestTheDeadlineNarrows:
    def test_a_nearer_deadline_wins(self) -> None:
        budget = ExecutionBudget(_config(), deadline_at=datetime.now(UTC) + timedelta(seconds=3))

        assert budget.remaining_ms() <= 3_000
        assert budget.config.total_timeout_ms > 3_000

    def test_a_further_deadline_does_not_extend_the_budget(self) -> None:
        """Otherwise a caller could pin a worker for an hour by asking nicely."""
        config = _config()
        budget = ExecutionBudget(config, deadline_at=datetime.now(UTC) + timedelta(hours=1))

        assert budget.remaining_ms() <= config.total_timeout_ms

    def test_no_deadline_leaves_the_budget_alone(self) -> None:
        config = _config()
        budget = ExecutionBudget(config)

        assert budget.deadline_offset_ms is None
        assert budget.remaining_ms() == pytest.approx(config.total_timeout_ms, abs=50)

    def test_a_deadline_already_past_spends_the_budget(self) -> None:
        budget = ExecutionBudget(_config(), deadline_at=datetime.now(UTC) - timedelta(seconds=5))

        assert budget.remaining_ms() == 0
        with pytest.raises(StageTimeoutError):
            budget.check_budget("knowledge")


class TestSecurityStagesStillRun:
    """Scope resolution and output DLP are not degradations that a caller may
    buy their way out of by setting an aggressive deadline."""

    @pytest.mark.parametrize("stage", sorted(MANDATORY_STAGES))
    def test_a_past_deadline_does_not_gate_a_mandatory_stage(self, stage: str) -> None:
        budget = ExecutionBudget(_config(), deadline_at=datetime.now(UTC) - timedelta(seconds=5))

        budget.check_budget(stage)  # must not raise
        assert budget.get_stage_timeout(stage) > 0

    def test_an_ordinary_stage_is_clamped_instead(self) -> None:
        budget = ExecutionBudget(_config(), deadline_at=datetime.now(UTC) - timedelta(seconds=5))

        assert budget.get_stage_timeout("knowledge") == 0


class TestOffsetConversion:
    def test_a_naive_datetime_is_read_as_utc(self) -> None:
        """Guessing the caller's local zone would shift a deadline by hours."""
        aware = deadline_offset_ms(datetime.now(UTC) + timedelta(seconds=10))
        naive = deadline_offset_ms(datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=10))

        assert abs(aware - naive) < 1_000

    def test_none_stays_none(self) -> None:
        assert deadline_offset_ms(None) is None


class TestTheRequestContextIsPublished:
    """The engine must hand the same budget to the helpers that check a deadline
    for themselves, not leave them looking at an unset ContextVar."""

    def test_a_run_sees_a_real_remaining_time(self) -> None:
        from app.services.runtime.request_context import remaining_seconds, request_context

        assert remaining_seconds() is None

        with request_context(timeout_ms=5_000, overload_mode=False, api_settings=None):
            seen = remaining_seconds()

        assert seen is not None and 0 < seen <= 5.0
        assert remaining_seconds() is None

    def test_the_llm_rewriter_declines_without_one(self) -> None:
        """Pins the reason the wiring mattered: no deadline reads as no time, so
        the rewriter returned None on every request."""
        from app.services.query.rule_rewrite import _llm_rewrite

        assert _llm_rewrite("what drove q3 revenue?") is None


def test_the_engine_passes_the_request_deadline_to_the_budget(monkeypatch) -> None:
    """The wiring under test is the engine reading `request.deadline_at`, not a
    budget constructed by hand in a test agreeing with itself.

    `_run_workflow` is stubbed out because the assertion is about what the engine
    builds *before* the graph runs; letting the graph run would reach real models.
    """
    import app.orchestration.engine as engine_module
    from app.domain.workflow import FinalAnswer
    from app.orchestration.capabilities import CoreCapabilities
    from app.orchestration.request import OrchestrationRequest, RequestActor

    seen: list[ExecutionBudget] = []

    async def _capture(self, request, reporter, budget):
        seen.append(budget)
        return FinalAnswer(text="stub")

    monkeypatch.setattr(engine_module.OrchestrationEngine, "_run_workflow", _capture)

    engine = engine_module.OrchestrationEngine(services=CoreCapabilities().orchestration_services())
    request = OrchestrationRequest(
        question="what drove q3 revenue?",
        actor=RequestActor(user_id="alice", tenant_id="alice", role="viewer"),
        deadline_at=datetime.now(UTC) + timedelta(milliseconds=1_500),
    )

    asyncio.run(engine._execute(request))

    assert seen, "the engine never constructed a budget"
    assert seen[0].deadline_offset_ms is not None
    assert seen[0].deadline_offset_ms <= 1_500
    assert seen[0].remaining_ms() <= 1_500
