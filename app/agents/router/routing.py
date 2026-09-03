"""
Router Agent - Query routing and skill selection.

Optimizations:
- Uses centralized configuration
- Caching for router decisions
- Improved type hints and error handling
- Better logging and diagnostics
"""

import json
import logging
import re
import threading
from dataclasses import dataclass

from app.agents.router.calibration import ConfidenceCalibrator
from app.agents.router.examples import get_mixed_examples
from app.agents.shared.cache import cached_router_decision
from app.agents.shared.config import (
    AGENT_CLASS_GENERAL,
    ROUTE_VECTOR,
    ROUTE_WEB,
    ROUTER_LOW_CONFIDENCE_THRESHOLD,
    SKILL_DEFAULT,
    VALID_AGENT_CLASSES,
    VALID_ROUTES,
    VALID_SKILLS,
)
from app.core.config import get_settings
from app.domain.text import normalize_string
from app.prompts import build_router_prompt
from app.services.agent_classifier import classify_agent_class, pick_cyber_skill
from app.services.llm_intent_classifier import classify_intent_with_llm
from app.services.models.runtime import get_chat_model, get_reasoning_model
from app.services.query.intent import is_smalltalk_query

logger = logging.getLogger(__name__)


__all__ = [
    "LegacyRouteDecision",
    "ROUTER_PROMPT",
    "decide_route",
    "decide_route_simple",
    "record_routing_feedback",
    "get_calibration_stats",
]

# The calibrator is resolved on first use, never at import.
#
# `ENABLE_CALIBRATION` is a `Settings` field now, and Settings is read from the
# rendered runtime env after this module has already been imported. Binding the
# switch at import time is exactly what made it settable only as a real exported
# environment variable, and it would make a config-centre push unable to reach
# it. The lock matters because `decide_route` runs under `asyncio.to_thread`:
# two threads racing here would each build a calibrator, and both would flush
# accumulated outcomes to the same file.
_calibrator: ConfidenceCalibrator | None = None
_calibrator_lock = threading.Lock()


def _get_calibrator() -> ConfidenceCalibrator | None:
    """The calibrator, or None while `ENABLE_CALIBRATION` is off."""

    if not get_settings().enable_calibration:
        return None
    global _calibrator
    with _calibrator_lock:
        if _calibrator is None:
            _calibrator = ConfidenceCalibrator()
        return _calibrator


@dataclass
class LegacyRouteDecision:
    """Legacy router decision with route, skill, and agent class.

    NOTE: This is maintained for backward compatibility with code that expects
    these specific fields. New code should use app.domain.contracts.RouteDecision.
    """

    route: str
    reason: str
    skill: str
    agent_class: str
    confidence: float = 0.7  # Default confidence for backward compatibility
    raw_confidence: float = 0.7  # Pre-calibration value; the calibration loop keys on it


# Inject few-shot examples into prompt
ROUTER_PROMPT = build_router_prompt(get_mixed_examples(vector_count=2, graph_count=2, hybrid_count=1, react_count=1))


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response."""
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        logger.warning("No JSON found in router response, using fallback")
        return {"route": ROUTE_VECTOR, "reason": "fallback", "skill": SKILL_DEFAULT}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode error in router response: {e}")
        return {"route": ROUTE_VECTOR, "reason": "fallback_json_error", "skill": SKILL_DEFAULT}


def _normalize_agent_class_hint(agent_class_hint: str | None) -> str | None:
    """Normalize and validate agent class hint."""
    if not agent_class_hint:
        return None

    hint = normalize_string(agent_class_hint, lowercase=True)
    if hint in VALID_AGENT_CLASSES:
        return hint

    logger.debug(f"Invalid agent class hint: {agent_class_hint}")
    return None


def _append_reason(base_reason: str, *tags: str) -> str:
    """Join a base reason with optional diagnostic tags."""
    parts = [normalize_string(base_reason)]
    parts.extend(normalize_string(tag) for tag in tags if normalize_string(tag))
    return "|".join(part for part in parts if part)


def _try_fallback_with_reasoning(
    question: str, agent_class: str, skill: str, original_confidence: float
) -> tuple[str, str, float] | None:
    """
    Try fallback strategy using reasoning model.

    Args:
        question: User question
        agent_class: Agent class for context
        skill: Suggested skill
        original_confidence: Original low confidence score

    Returns:
        Tuple of (route, reason, confidence) if successful, None if fallback also fails
    """
    try:
        logger.info(
            f"Fallback triggered: original_confidence={original_confidence:.2f} "
            f"< threshold={ROUTER_LOW_CONFIDENCE_THRESHOLD}"
        )

        # Try reasoning model for better decision
        reasoning_model = get_reasoning_model()
        prompt = f"""{ROUTER_PROMPT}

Question: {question}
Agent class: {agent_class}
Suggested skill: {skill}"""
        response = reasoning_model.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        route_data = _extract_json(response_text)

        raw_route = normalize_string(route_data.get("route", ROUTE_VECTOR), lowercase=True)
        route = raw_route if raw_route in VALID_ROUTES else ROUTE_VECTOR

        reason = normalize_string(route_data.get("reason", "fallback_reasoning")) or "fallback_reasoning"
        reason = _append_reason(reason, "fallback_reasoning")

        # Extract confidence from reasoning model
        reasoning_confidence = route_data.get("confidence")
        if reasoning_confidence is not None and isinstance(reasoning_confidence, int | float):
            confidence = float(reasoning_confidence)
            confidence = max(0.0, min(1.0, confidence))
        else:
            confidence = 0.7

        logger.info(f"Fallback reasoning result: route={route}, confidence={confidence:.2f}")

        # Check if reasoning model improved confidence
        if confidence >= ROUTER_LOW_CONFIDENCE_THRESHOLD:
            return (route, reason, confidence)
        else:
            logger.warning(f"Fallback reasoning still low confidence: {confidence:.2f}")
            return None

    except Exception as e:
        logger.warning(f"Fallback reasoning model failed: {e}")
        return None


@cached_router_decision
def decide_route(
    question: str, use_reasoning: bool = False, agent_class_hint: str | None = None, use_llm_intent: bool = True
) -> LegacyRouteDecision:
    """
    Decide query route and skill.

    This function is cached - identical queries will return cached decisions.

    Args:
        question: User question
        use_reasoning: Whether to use reasoning model
        agent_class_hint: Force specific agent class
        use_llm_intent: Use LLM for intent classification (default True)

    Returns:
        LegacyRouteDecision: Route decision with route, skill, and agent class
    """
    forced = _normalize_agent_class_hint(agent_class_hint)
    if is_smalltalk_query(question):
        return _smalltalk_decision(forced)

    agent_class, intent_confidence, classification_method = _classify(question, forced, use_llm_intent)
    skill = _skill_for(agent_class, question)
    forced_reason = f"forced_agent_class={forced}" if forced else ""

    try:
        route, reason, skill, route_confidence = _llm_route(
            question, agent_class, skill, use_reasoning=use_reasoning, forced_reason=forced_reason
        )
        logger.info(
            f"Route decision: route={route}, skill={skill}, "
            f"agent_class={agent_class}, method={classification_method}, "
            f"intent_confidence={intent_confidence:.2f}, route_confidence={route_confidence:.2f}"
        )
    except Exception as e:
        logger.exception(f"Router LLM call failed: {e}")
        route = ROUTE_VECTOR
        reason = _append_reason(f"router_invoke_error:{type(e).__name__}", forced_reason)
        route_confidence = 0.5  # Low confidence for error case

    raw_confidence = route_confidence
    return LegacyRouteDecision(
        route=route,
        reason=reason,
        skill=skill,
        agent_class=agent_class,
        confidence=_calibrated(raw_confidence),
        raw_confidence=raw_confidence,
    )


def _smalltalk_decision(forced: str | None) -> LegacyRouteDecision:
    """Greetings need no retrieval and no model call to establish that."""

    raw_confidence = 0.95  # High confidence for smalltalk detection
    return LegacyRouteDecision(
        route=ROUTE_VECTOR,
        reason=_append_reason("smalltalk_local_only", f"forced_agent_class={forced}" if forced else ""),
        skill=SKILL_DEFAULT,
        agent_class=forced or AGENT_CLASS_GENERAL,
        confidence=_calibrated(raw_confidence),
        raw_confidence=raw_confidence,
    )


def _classify(question: str, forced: str | None, use_llm_intent: bool) -> tuple[str, float, str]:
    """Which agent class this question belongs to, and how that was decided.

    Three ways in, and the caller's hint outranks both classifiers.
    """

    if forced:
        return forced, 1.0, "forced"
    if not use_llm_intent:
        return classify_agent_class(question), 0.5, "rule_based"
    try:
        intent_result = classify_intent_with_llm(question)
        agent_class = intent_result["agent_class"]
        confidence = intent_result.get("confidence", 0.5)
        logger.info(f"LLM intent classification: {agent_class} (confidence={confidence:.2f})")
        return agent_class, confidence, f"llm(confidence={confidence:.2f})"
    except Exception as e:
        logger.warning(f"LLM intent classification failed, fallback to rule-based: {e}")
        return classify_agent_class(question), 0.5, "rule_fallback"


def _skill_for(agent_class: str, question: str) -> str:
    """The skill to suggest to the router, from the agent class or the wording.

    A proposal, not a decision: the model is shown this and may replace it with
    any skill in VALID_SKILLS.
    """

    if agent_class == "cybersecurity":
        return pick_cyber_skill(question)
    if agent_class == "pdf_text":
        return "pdf_text_reader"
    lowered = question.lower()
    if "compare" in lowered or "difference" in lowered:
        return "compare_entities"
    if "timeline" in lowered or "history" in lowered:
        return "timeline_builder"
    return SKILL_DEFAULT


def _llm_route(
    question: str, agent_class: str, skill: str, *, use_reasoning: bool, forced_reason: str
) -> tuple[str, str, str, float]:
    """Ask the model for a route, and trust none of what comes back unchecked."""

    model = get_reasoning_model() if use_reasoning else get_chat_model()
    prompt = f"""{ROUTER_PROMPT}

Question: {question}
Agent class: {agent_class}
Suggested skill: {skill}"""
    response = model.invoke(prompt)
    response_text = response.content if hasattr(response, "content") else str(response)
    route_data = _extract_json(response_text)

    route, reason = _validated_route(route_data)
    skill, reason = _validated_skill(route_data, skill, reason)

    # Web route downgrade (configurable)
    # Reason: In production, we prioritize local knowledge base first to reduce latency
    # and API costs. Web search is only used when explicitly enabled or local retrieval fails.
    if route == ROUTE_WEB and get_settings().enable_web_route_downgrade:
        route = ROUTE_VECTOR
        reason = _append_reason(reason, "web_downgraded_to_local_first")
        logger.debug("Web route downgraded to vector (ENABLE_WEB_ROUTE_DOWNGRADE=True)")

    if forced_reason:
        reason = _append_reason(reason, forced_reason)

    route_confidence = _stated_confidence(route_data)
    if route_confidence < ROUTER_LOW_CONFIDENCE_THRESHOLD:
        route, reason, route_confidence = _recover_low_confidence(
            question, agent_class, skill, route, reason, route_confidence, forced_reason
        )
    return route, reason, skill, route_confidence


def _validated_route(route_data: dict) -> tuple[str, str]:
    """A route outside VALID_ROUTES becomes vector, and the reason records what was asked for."""

    raw_route = normalize_string(route_data.get("route", ROUTE_VECTOR), lowercase=True)
    route = raw_route if raw_route in VALID_ROUTES else ROUTE_VECTOR
    reason = normalize_string(route_data.get("reason", "llm_decision")) or "llm_decision"
    if raw_route and raw_route not in VALID_ROUTES:
        reason = _append_reason(reason, f"invalid_route={raw_route}")
    return route, reason


def _validated_skill(route_data: dict, skill: str, reason: str) -> tuple[str, str]:
    """An unrecognised skill keeps the one already chosen rather than overriding it."""

    llm_skill = normalize_string(route_data.get("skill", skill), lowercase=True)
    if not llm_skill or llm_skill == "...":
        return skill, reason
    if llm_skill in VALID_SKILLS:
        return llm_skill, reason
    return skill, _append_reason(reason, f"invalid_skill={llm_skill}")


def _stated_confidence(route_data: dict) -> float:
    """The model's own confidence, clamped -- or 0.7 when it did not offer one."""

    value = route_data.get("confidence")
    if value is not None and isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return 0.7  # Default if not provided


def _recover_low_confidence(
    question: str,
    agent_class: str,
    skill: str,
    route: str,
    reason: str,
    route_confidence: float,
    forced_reason: str,
) -> tuple[str, str, float]:
    """Re-ask with the reasoning model, and fall back to vector if that fails too.

    The confidence is floored at 0.5 rather than raised to it: a safe route
    chosen because nothing better was available should still read as uncertain.
    """

    logger.info(f"Low confidence detected: {route_confidence:.2f} < {ROUTER_LOW_CONFIDENCE_THRESHOLD}")
    fallback_result = _try_fallback_with_reasoning(question, agent_class, skill, route_confidence)
    if fallback_result is not None:
        route, reason, route_confidence = fallback_result
    else:
        logger.warning(f"Fallback to safe route: original_route={route}, original_confidence={route_confidence:.2f}")
        route = ROUTE_VECTOR
        reason = _append_reason(reason, "fallback_safe_route")
        route_confidence = max(0.5, route_confidence)
    if forced_reason:
        reason = _append_reason(reason, forced_reason)
    return route, reason, route_confidence


def _calibrated(raw_confidence: float) -> float:
    """What the caller is told. `raw_confidence` is what the calibrator is later trained on."""

    calibrator = _get_calibrator()
    if calibrator is None:
        return raw_confidence
    calibrated = calibrator.calibrate(raw_confidence)
    logger.debug(f"Calibrated confidence: {raw_confidence:.2f} -> {calibrated:.2f}")
    return calibrated


def decide_route_simple(question: str) -> str:
    """
    Simple route decision without full skill selection.

    Args:
        question: User question

    Returns:
        Route name ("vector", "graph", "hybrid")
    """
    decision = decide_route(question, use_llm_intent=False)
    return decision.route


def record_routing_feedback(raw_confidence: float, was_correct: bool) -> None:
    """
    Record feedback about a routing decision for calibration.

    This function should be called after verifying whether a routing
    decision was correct (e.g., based on answer quality metrics or
    explicit user feedback).

    Args:
        raw_confidence: The raw confidence score that was used
        was_correct: Whether the routing decision was correct

    Example:
        decision = decide_route(question)
        # ... execute query and evaluate result ...
        if result_quality > threshold:
            record_routing_feedback(decision.confidence, was_correct=True)
    """
    calibrator = _get_calibrator()
    if calibrator is not None:
        calibrator.record_feedback(raw_confidence, was_correct)
        logger.info(f"Recorded routing feedback: confidence={raw_confidence:.2f}, correct={was_correct}")


def get_calibration_stats() -> dict[str, dict]:
    """
    Get calibration statistics for monitoring.

    Returns:
        Dictionary mapping bucket names to calibration stats
    """
    calibrator = _get_calibrator()
    if calibrator is not None:
        return calibrator.get_stats()
    return {}
