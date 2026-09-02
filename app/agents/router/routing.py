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
        raw_confidence = 0.95  # High confidence for smalltalk detection
        calibrator = _get_calibrator()
        calibrated_confidence = calibrator.calibrate(raw_confidence) if calibrator else raw_confidence

        return LegacyRouteDecision(
            route=ROUTE_VECTOR,
            reason=_append_reason(
                "smalltalk_local_only",
                f"forced_agent_class={forced}" if forced else "",
            ),
            skill=SKILL_DEFAULT,
            agent_class=forced or AGENT_CLASS_GENERAL,
            confidence=calibrated_confidence,
            raw_confidence=raw_confidence,
        )

    # Select intent classification method
    if forced:
        agent_class = forced
        classification_method = "forced"
        confidence = 1.0
    elif use_llm_intent:
        try:
            intent_result = classify_intent_with_llm(question)
            agent_class = intent_result["agent_class"]
            confidence = intent_result.get("confidence", 0.5)
            classification_method = f"llm(confidence={confidence:.2f})"
            logger.info(f"LLM intent classification: {agent_class} (confidence={confidence:.2f})")
        except Exception as e:
            logger.warning(f"LLM intent classification failed, fallback to rule-based: {e}")
            agent_class = classify_agent_class(question)
            confidence = 0.5
            classification_method = "rule_fallback"
    else:
        agent_class = classify_agent_class(question)
        confidence = 0.5
        classification_method = "rule_based"

    # Determine skill based on agent class and question
    if agent_class == "cybersecurity":
        skill = pick_cyber_skill(question)
    elif agent_class == "pdf_text":
        skill = "pdf_text_reader"
    elif "compare" in question.lower() or "difference" in question.lower():
        skill = "compare_entities"
    elif "timeline" in question.lower() or "history" in question.lower():
        skill = "timeline_builder"
    else:
        skill = SKILL_DEFAULT

    forced_reason = f"forced_agent_class={forced}" if forced else ""

    # Get route decision from LLM
    try:
        model = get_reasoning_model() if use_reasoning else get_chat_model()
        prompt = f"""{ROUTER_PROMPT}

Question: {question}
Agent class: {agent_class}
Suggested skill: {skill}"""
        response = model.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        route_data = _extract_json(response_text)

        raw_route = normalize_string(route_data.get("route", ROUTE_VECTOR), lowercase=True)
        route = raw_route if raw_route in VALID_ROUTES else ROUTE_VECTOR

        reason = normalize_string(route_data.get("reason", "llm_decision")) or "llm_decision"
        if raw_route and raw_route not in VALID_ROUTES:
            reason = _append_reason(reason, f"invalid_route={raw_route}")

        llm_skill = normalize_string(route_data.get("skill", skill), lowercase=True)
        if llm_skill and llm_skill != "...":
            if llm_skill in VALID_SKILLS:
                skill = llm_skill
            else:
                reason = _append_reason(reason, f"invalid_skill={llm_skill}")
                # Keep the pre-determined skill (don't override with invalid value)

        # Web route downgrade (configurable)
        # Reason: In production, we prioritize local knowledge base first to reduce latency
        # and API costs. Web search is only used when explicitly enabled or local retrieval fails.
        if route == ROUTE_WEB and get_settings().enable_web_route_downgrade:
            route = ROUTE_VECTOR
            reason = _append_reason(reason, "web_downgraded_to_local_first")
            logger.debug("Web route downgraded to vector (ENABLE_WEB_ROUTE_DOWNGRADE=True)")

        if forced_reason:
            reason = _append_reason(reason, forced_reason)

        # Extract LLM confidence if provided (for route decision confidence)
        llm_confidence = route_data.get("confidence")
        if llm_confidence is not None and isinstance(llm_confidence, int | float):
            route_confidence = float(llm_confidence)
            # Clamp to valid range
            route_confidence = max(0.0, min(1.0, route_confidence))
        else:
            route_confidence = 0.7  # Default if not provided

        # Check if confidence is too low and trigger fallback
        if route_confidence < ROUTER_LOW_CONFIDENCE_THRESHOLD:
            logger.info(f"Low confidence detected: {route_confidence:.2f} < {ROUTER_LOW_CONFIDENCE_THRESHOLD}")

            # Try fallback with reasoning model
            fallback_result = _try_fallback_with_reasoning(question, agent_class, skill, route_confidence)

            if fallback_result is not None:
                # Fallback succeeded with reasoning model
                route, reason, route_confidence = fallback_result
                if forced_reason:
                    reason = _append_reason(reason, forced_reason)
            else:
                # Fallback to safe route (vector)
                logger.warning(
                    f"Fallback to safe route: original_route={route}, original_confidence={route_confidence:.2f}"
                )
                route = ROUTE_VECTOR
                reason = _append_reason(reason, "fallback_safe_route")
                if forced_reason:
                    reason = _append_reason(reason, forced_reason)
                # Keep low confidence to indicate uncertainty
                route_confidence = max(0.5, route_confidence)

        logger.info(
            f"Route decision: route={route}, skill={skill}, "
            f"agent_class={agent_class}, method={classification_method}, "
            f"intent_confidence={confidence:.2f}, route_confidence={route_confidence:.2f}"
        )

    except Exception as e:
        logger.exception(f"Router LLM call failed: {e}")
        route = ROUTE_VECTOR
        reason = _append_reason(f"router_invoke_error:{type(e).__name__}", forced_reason)
        route_confidence = 0.5  # Low confidence for error case

    # Apply confidence calibration
    raw_confidence = route_confidence
    calibrator = _get_calibrator()
    if calibrator is not None:
        calibrated_confidence = calibrator.calibrate(raw_confidence)
        logger.debug(f"Calibrated confidence: {raw_confidence:.2f} -> {calibrated_confidence:.2f}")
    else:
        calibrated_confidence = raw_confidence

    return LegacyRouteDecision(
        route=route,
        reason=reason,
        skill=skill,
        agent_class=agent_class,
        confidence=calibrated_confidence,
        raw_confidence=raw_confidence,
    )


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
