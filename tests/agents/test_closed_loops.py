"""Three loops that were built with one end missing.

Each was reachable, documented, and switchable -- and each did nothing when
switched on, because the half that feeds it was never connected:

* clarification advanced a round only when the *session store* recorded an
  answer, so a caller that asked again without answering got the same question
  back forever and the round cap could not be reached;
* fact verification rebuilt its source documents by regexing a context format
  retired months earlier, so it verified every answer against an empty list;
* router calibration had no caller for `record_routing_feedback` anywhere, so
  `ENABLE_CALIBRATION` switched on a calibrator that never learns.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from app.agents.clarification.rules import max_rounds_for
from app.agents.clarification.service import ClarificationAgentService
from app.domain.contracts import ClarificationContext, EvidenceBundle, EvidenceItem, RouteDecision
from app.domain.workflow import ContextBundle, VerificationDecision
from app.orchestration.request import OrchestrationRequest

# --- clarification -----------------------------------------------------------

_DESIGN = "帮我设计一个 RAG 系统"


async def _ask_repeatedly(times: int) -> list[tuple[str, int]]:
    """Simulate a caller that never answers, only re-asks."""
    service = ClarificationAgentService()
    context = ClarificationContext()
    seen: list[tuple[str, int]] = []
    for _ in range(times):
        result = await service.clarify(OrchestrationRequest(question=_DESIGN), context=context)
        context = result.context
        seen.append((result.action, context.clarification_round))
        if result.action == "continue":
            break
    return seen


@pytest.mark.asyncio
async def test_asking_advances_the_round_without_waiting_for_an_answer():
    seen = await _ask_repeatedly(2)

    assert [round_ for _action, round_ in seen] == [1, 2]


@pytest.mark.asyncio
async def test_a_caller_that_never_answers_still_terminates():
    seen = await _ask_repeatedly(10)

    assert seen[-1][0] == "continue"
    assert len(seen) <= max_rounds_for("rag_design") + 1


@pytest.mark.asyncio
async def test_each_round_asks_about_a_different_field():
    service = ClarificationAgentService()
    context = ClarificationContext()
    fields: list[str] = []
    for _ in range(max_rounds_for("rag_design")):
        result = await service.clarify(OrchestrationRequest(question=_DESIGN), context=context)
        context = result.context
        if result.question:
            fields.append(result.question.field_name)

    assert len(fields) == len(set(fields))


def test_the_round_cap_matches_the_questions_that_exist():
    """The cap was a hand-written 7 against four fields, so it could never fire
    and the UI promised three rounds that do not exist."""
    from app.agents.clarification.rules import _QUESTIONS_ZH

    for intent, questions in _QUESTIONS_ZH.items():
        assert max_rounds_for(intent) <= len(questions), intent
    assert max_rounds_for("rag_design") == 4
    assert max_rounds_for("complete") == 0


# --- fact verification -------------------------------------------------------


@pytest.mark.asyncio
async def test_fact_verification_receives_the_evidence_the_answer_was_built_from():
    """It used to regex `[doc_id:page]` out of the rendered context. That form is
    gone, so the parse produced nothing and verification passed vacuously."""
    from app.agents.synthesizer.service import SynthesizerAgentService

    seen: dict[str, object] = {}

    def _generate(*_args, **kwargs):
        seen.update(kwargs)
        return {"answer": "An answer [E1]."}

    item = EvidenceItem(
        content="Revenue grew 12 percent.",
        source="q4.pdf",
        document_id="q4.pdf",
        version=1,
        page=7,
        retriever="vector",
    )
    service = SynthesizerAgentService(generate=_generate)

    await service.synthesize_candidate(
        OrchestrationRequest(question="How did revenue do?"),
        ContextBundle(evidence=(item,), rendered_context="[E1] document=q4.pdf\nRevenue grew 12 percent."),
        (),
    )

    documents = seen["source_documents"]
    assert documents == [{"doc_id": "q4.pdf", "page": 7, "content": "Revenue grew 12 percent."}]


@pytest.mark.asyncio
async def test_verification_without_source_documents_is_skipped_not_passed():
    """Verifying against nothing and reporting perfect groundedness is worse than
    not verifying."""
    from app.agents.synthesizer import generation

    result = await _run_in_thread(
        generation.synthesize_answer,
        "q",
        "answer_with_citations",
        vector_context="[E1] document=a.pdf\nsome text",
        enable_fact_verification=True,
        source_documents=None,
    )

    assert "verification" not in result


async def _run_in_thread(function, *args, **kwargs):
    import asyncio

    return await asyncio.to_thread(lambda: function(*args, **kwargs))


# --- router calibration ------------------------------------------------------


@pytest.fixture
def calibration_path(monkeypatch):
    # Deliberately not pytest's tmp_path: its basetemp root needs directory
    # permissions that are not available on every Windows checkout.
    root = Path(tempfile.mkdtemp(prefix="querymind-calibration-"))
    from app.core.config import get_settings

    monkeypatch.setenv("ROUTER_CALIBRATION_PATH", str(root / "router_calibration.json"))
    get_settings.cache_clear()
    try:
        yield root / "router_calibration.json"
    finally:
        get_settings.cache_clear()
        shutil.rmtree(root, ignore_errors=True)


def _route(raw: float | None) -> RouteDecision:
    return RouteDecision(
        route="vector",
        confidence=0.8,
        raw_confidence=raw,
        requires_plan=False,
        reason="test",
        allowed_capabilities=frozenset({"rag"}),
    )


def _evidence(count: int) -> EvidenceBundle:
    return EvidenceBundle(
        items=tuple(
            EvidenceItem(
                content=f"chunk {index}",
                source="a.pdf",
                document_id="a.pdf",
                version=1,
                retriever="vector",
            )
            for index in range(count)
        )
    )


@pytest.mark.parametrize(
    ("evidence_count", "status", "expected"),
    [
        (0, "degraded", False),  # the route found nothing: attributable
        (3, "approved", True),  # the route found the right things: attributable
        (3, "degraded", None),  # evidence was there; the failure is not routing's
        (3, "rejected", None),
    ],
)
def test_only_outcomes_attributable_to_routing_are_recorded(monkeypatch, evidence_count, status, expected):
    from app.orchestration.langgraph import nodes

    recorded: list[tuple[float, bool]] = []
    monkeypatch.setattr(
        "app.agents.router.routing.record_routing_feedback",
        lambda raw_confidence, was_correct: recorded.append((raw_confidence, was_correct)),
    )

    nodes._record_routing_outcome(_route(0.85), _evidence(evidence_count), VerificationDecision(status=status))

    if expected is None:
        assert recorded == []
    else:
        assert recorded == [(0.85, expected)]


def test_a_route_with_no_raw_confidence_records_nothing(monkeypatch):
    """Feeding the calibrated value back would train the calibrator on its own
    output, so a decision that never carried the raw one is skipped."""
    from app.orchestration.langgraph import nodes

    recorded: list[object] = []
    monkeypatch.setattr(
        "app.agents.router.routing.record_routing_feedback",
        lambda **_: recorded.append(1),
    )

    nodes._record_routing_outcome(_route(None), _evidence(3), VerificationDecision(status="approved"))

    assert recorded == []


def test_the_router_carries_the_pre_calibration_confidence():
    from app.agents.router.service import _to_domain_route

    assert _to_domain_route("vector", 0.72, "reason", 0.91).raw_confidence == 0.91


def test_accumulated_outcomes_do_not_dirty_the_tracked_config(calibration_path):
    """The calibrator wrote config/router_calibration.json on every request."""
    from app.agents.router.calibration import CALIBRATION_CONFIG_PATH, ConfidenceCalibrator

    before = CALIBRATION_CONFIG_PATH.read_text(encoding="utf-8")
    calibrator = ConfidenceCalibrator()
    for _ in range(25):
        calibrator.record_feedback(0.85, was_correct=True)
    calibrator.flush()

    assert calibration_path.exists()
    assert CALIBRATION_CONFIG_PATH.read_text(encoding="utf-8") == before


def test_a_fresh_deployment_seeds_from_the_shipped_distribution(calibration_path):
    from app.agents.router.calibration import ConfidenceCalibrator

    assert not calibration_path.exists()
    calibrator = ConfidenceCalibrator()

    assert calibrator.get_stats(), "seeded distribution should not be empty"


def test_feedback_is_buffered_rather_than_written_per_request(calibration_path):
    from app.agents.router.calibration import ConfidenceCalibrator

    calibrator = ConfidenceCalibrator()
    calibrator.record_feedback(0.85, was_correct=True)

    assert not calibration_path.exists(), "one record must not trigger a disk write"

    calibrator.flush()
    assert calibration_path.exists()
    assert json.loads(calibration_path.read_text(encoding="utf-8"))["buckets"]
