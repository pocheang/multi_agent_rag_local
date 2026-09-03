"""What decide_route decides, pinned before it was split up.

It was one 130-line function: smalltalk, intent classification with two
fallbacks, keyword skill selection, an LLM call, validation of everything that
call returned, a configurable web downgrade, a low-confidence recovery path with
its own fallback, and calibration. The tests it had were about its cache.

The route is an instruction the rest of the pipeline follows -- it decides which
retrievers run and which answer shape the synthesizer is given -- so what this
function does with a malformed or unconfident answer from the model is worth
stating.
"""

from __future__ import annotations

import json

import pytest

from app.agents.router import routing
from app.agents.shared.cache import clear_router_decision_cache


class _Reply:
    def __init__(self, content: str) -> None:
        self.content = content


class _Model:
    def __init__(self, payload) -> None:
        self._payload = payload
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> _Reply:
        self.prompts.append(prompt)
        if isinstance(self._payload, Exception):
            raise self._payload
        return _Reply(json.dumps(self._payload) if not isinstance(self._payload, str) else self._payload)


@pytest.fixture(autouse=True)
def _router_wiring(monkeypatch: pytest.MonkeyPatch):
    """No cache between tests, no calibrator, and no real model or classifier."""

    clear_router_decision_cache()
    monkeypatch.setattr(routing, "_get_calibrator", lambda: None)
    monkeypatch.setattr(
        routing, "classify_intent_with_llm", lambda question: {"agent_class": "general", "confidence": 0.9}
    )
    monkeypatch.setattr(routing, "get_settings", lambda: type("S", (), {"enable_web_route_downgrade": False})())
    yield
    clear_router_decision_cache()


def _answer(monkeypatch: pytest.MonkeyPatch, payload) -> _Model:
    model = _Model(payload)
    monkeypatch.setattr(routing, "get_chat_model", lambda: model)
    monkeypatch.setattr(routing, "get_reasoning_model", lambda: model)
    return model


def test_smalltalk_never_reaches_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    model = _answer(monkeypatch, {"route": "graph"})

    decision = routing.decide_route("hello")

    assert decision.route == routing.ROUTE_VECTOR
    assert decision.skill == routing.SKILL_DEFAULT
    assert decision.confidence == pytest.approx(0.95)
    assert model.prompts == []


def test_the_model_decides_the_route_and_may_change_the_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, {"route": "graph", "reason": "entities", "skill": "timeline_builder", "confidence": 0.9})

    decision = routing.decide_route("how do the services depend on each other")

    assert decision.route == "graph"
    assert decision.skill == "timeline_builder"
    assert decision.reason == "entities"
    assert decision.confidence == pytest.approx(0.9)


def test_a_route_the_model_invented_falls_back_to_vector_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, {"route": "telepathy", "reason": "guessing", "confidence": 0.9})

    decision = routing.decide_route("what does the report say about costs")

    assert decision.route == routing.ROUTE_VECTOR
    assert "invalid_route=telepathy" in decision.reason


def test_a_skill_the_model_invented_keeps_the_one_already_chosen(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, {"route": "vector", "reason": "ok", "skill": "astrology", "confidence": 0.9})

    decision = routing.decide_route("compare the two vendors on price")

    assert decision.skill == "compare_entities"  # from the question, not from the model
    assert "invalid_skill=astrology" in decision.reason


@pytest.mark.parametrize(
    ("question", "expected_skill"),
    [
        ("compare the two vendors on price", "compare_entities"),
        ("what is the difference between them", "compare_entities"),
        ("give me the timeline of the incident", "timeline_builder"),
        ("what is the history of this project", "timeline_builder"),
        ("what does the document say about revenue", "answer_with_citations"),
    ],
)
def test_the_question_picks_a_skill_before_the_model_is_asked(
    monkeypatch: pytest.MonkeyPatch, question: str, expected_skill: str
) -> None:
    _answer(monkeypatch, {"route": "vector", "reason": "ok", "confidence": 0.9})

    assert routing.decide_route(question).skill == expected_skill


def test_a_forced_agent_class_wins_and_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, {"route": "vector", "reason": "ok", "confidence": 0.9})

    decision = routing.decide_route("what does the report say", agent_class_hint="cybersecurity")

    assert decision.agent_class == "cybersecurity"
    assert "forced_agent_class=cybersecurity" in decision.reason


def test_the_web_route_survives_when_the_downgrade_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, {"route": "web", "reason": "needs fresh data", "confidence": 0.9})

    assert routing.decide_route("what happened in the news today about this").route == "web"


def test_the_web_route_is_rewritten_when_the_downgrade_is_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """A third answer to "who authorised the web", and an invisible one."""

    _answer(monkeypatch, {"route": "web", "reason": "needs fresh data", "confidence": 0.9})
    monkeypatch.setattr(routing, "get_settings", lambda: type("S", (), {"enable_web_route_downgrade": True})())

    decision = routing.decide_route("what happened in the news today about this")

    assert decision.route == routing.ROUTE_VECTOR
    assert "web_downgraded_to_local_first" in decision.reason


@pytest.mark.parametrize(
    ("stated", "expected"),
    # Only values that clear the low-confidence threshold: below it the recovery
    # path takes over and the clamp is no longer what is being read.
    [(1.7, 1.0), (None, 0.7), ("high", 0.7)],
)
def test_the_models_confidence_is_clamped_or_defaulted(
    monkeypatch: pytest.MonkeyPatch, stated, expected: float
) -> None:
    payload = {"route": "vector", "reason": "ok"}
    if stated is not None:
        payload["confidence"] = stated
    _answer(monkeypatch, payload)

    decision = routing.decide_route(f"what does the report say about item {stated}")

    assert decision.raw_confidence == pytest.approx(expected)


def test_low_confidence_takes_the_reasoning_model_when_it_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, {"route": "vector", "reason": "unsure", "confidence": 0.1})
    monkeypatch.setattr(routing, "_try_fallback_with_reasoning", lambda *args: ("graph", "reasoned_again", 0.85))

    decision = routing.decide_route("something the router is unsure about")

    assert (decision.route, decision.reason) == ("graph", "reasoned_again")
    assert decision.raw_confidence == pytest.approx(0.85)


def test_low_confidence_falls_back_to_the_safe_route_and_keeps_saying_it_is_unsure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _answer(monkeypatch, {"route": "graph", "reason": "unsure", "confidence": 0.1})
    monkeypatch.setattr(routing, "_try_fallback_with_reasoning", lambda *args: None)

    decision = routing.decide_route("something else the router is unsure about")

    assert decision.route == routing.ROUTE_VECTOR
    assert "fallback_safe_route" in decision.reason
    # Floored at 0.5 rather than raised to it: the uncertainty is the message.
    assert decision.raw_confidence == pytest.approx(0.5)


def test_a_model_that_raises_still_returns_a_usable_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, RuntimeError("provider timeout"))

    decision = routing.decide_route("compare the two vendors on price and support")

    assert decision.route == routing.ROUTE_VECTOR
    assert "router_invoke_error:RuntimeError" in decision.reason
    assert decision.raw_confidence == pytest.approx(0.5)
    # The skill chosen before the call survives it.
    assert decision.skill == "compare_entities"


def test_an_intent_classifier_that_raises_falls_back_to_the_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, {"route": "vector", "reason": "ok", "confidence": 0.9})

    def refuse(question):
        raise RuntimeError("classifier down")

    monkeypatch.setattr(routing, "classify_intent_with_llm", refuse)
    monkeypatch.setattr(routing, "classify_agent_class", lambda question: "pdf_text")

    decision = routing.decide_route("what does page four of the manual say")

    assert decision.agent_class == "pdf_text"
    assert decision.skill == "pdf_text_reader"


def test_calibration_replaces_the_reported_confidence_but_not_the_raw_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """raw_confidence exists to feed the calibrator without training it on itself."""

    _answer(monkeypatch, {"route": "vector", "reason": "ok", "confidence": 0.8})
    monkeypatch.setattr(
        routing, "_get_calibrator", lambda: type("C", (), {"calibrate": staticmethod(lambda v: 0.42)})()
    )

    decision = routing.decide_route("what does the summary say about margins")

    assert decision.confidence == pytest.approx(0.42)
    assert decision.raw_confidence == pytest.approx(0.8)


def test_a_negative_confidence_is_clamped_to_zero_before_the_recovery_sees_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The clamp runs first, so the recovery path is never handed a nonsense number."""

    _answer(monkeypatch, {"route": "vector", "reason": "ok", "confidence": -0.4})
    seen: list[float] = []

    def record(question, agent_class, skill, confidence):
        seen.append(confidence)
        return None

    monkeypatch.setattr(routing, "_try_fallback_with_reasoning", record)

    routing.decide_route("a question the model is very unsure about")

    assert seen == [0.0]
