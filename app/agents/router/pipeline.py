"""
Refactored router architecture with clear separation of concerns.

This module replaces the monolithic decide_route() function with a
clean pipeline of single-responsibility components.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from app.agents.router.calibration import ConfidenceCalibrator
from app.agents.router.config import ENABLE_CALIBRATION
from app.agents.shared.config import (
    AGENT_CLASS_GENERAL,
    ROUTE_VECTOR,
    ROUTER_LOW_CONFIDENCE_THRESHOLD,
    SKILL_DEFAULT,
)
from app.core.models import get_chat_model, get_reasoning_model
from app.services.query_intent import is_smalltalk_query

logger = logging.getLogger(__name__)


# ============================================================================
# Domain Models
# ============================================================================


@dataclass
class Intent:
    """Classified user intent with metadata."""

    type: str  # e.g., "general", "cybersecurity", "pdf_text"
    confidence: float
    method: str  # e.g., "llm", "rule_based", "forced"


@dataclass
class Skill:
    """Selected skill for handling the query."""

    name: str
    source: str  # e.g., "agent_class", "query_pattern", "default"


@dataclass
class RouteCandidate:
    """Candidate route with reasoning."""

    route: str
    confidence: float
    reason: str
    skill: Skill
    agent_class: str


@dataclass
class FinalRoute:
    """Final routing decision after calibration."""

    route: str
    reason: str
    skill: str
    agent_class: str
    confidence: float


# ============================================================================
# Component Interfaces
# ============================================================================


class IntentClassifierProtocol(Protocol):
    """Interface for intent classification components."""

    def classify(
        self,
        question: str,
        use_llm: bool = True,
        forced_hint: str | None = None,
    ) -> Intent:
        """Classify the user's intent."""
        ...


class SkillSelectorProtocol(Protocol):
    """Interface for skill selection components."""

    def select(self, question: str, intent: Intent) -> Skill:
        """Select appropriate skill based on question and intent."""
        ...


class RouteDeciderProtocol(Protocol):
    """Interface for route decision components."""

    def decide(
        self,
        question: str,
        intent: Intent,
        skill: Skill,
        use_reasoning: bool = False,
    ) -> RouteCandidate:
        """Decide the routing strategy."""
        ...


class ConfidenceCalibratorProtocol(Protocol):
    """Interface for confidence calibration."""

    def calibrate(self, confidence: float) -> float:
        """Calibrate raw confidence score."""
        ...


class FallbackHandlerProtocol(Protocol):
    """Interface for fallback handling."""

    def handle(
        self,
        question: str,
        candidate: RouteCandidate,
        threshold: float,
    ) -> RouteCandidate:
        """Handle low-confidence scenarios."""
        ...


# ============================================================================
# Intent Classifier
# ============================================================================


class IntentClassifier:
    """Classify user intent using multiple strategies."""

    def classify(
        self,
        question: str,
        use_llm: bool = True,
        forced_hint: str | None = None,
    ) -> Intent:
        """
        Classify user intent.

        Priority:
        1. Forced hint (if provided)
        2. Smalltalk detection
        3. LLM classification (if enabled)
        4. Rule-based classification (fallback)
        """

        # 1. Handle forced hint
        if forced_hint:
            return self._validate_hint(forced_hint)

        # 2. Detect smalltalk
        if is_smalltalk_query(question):
            return Intent(
                type="smalltalk",
                confidence=0.95,
                method="rule_based_smalltalk",
            )

        # 3. Try LLM classification
        if use_llm:
            return self._classify_with_llm(question)

        # 4. Fallback to rule-based
        return self._classify_with_rules(question)

    def _validate_hint(self, hint: str) -> Intent:
        """Validate and normalize forced hint."""
        from app.agents.shared.config import VALID_AGENT_CLASSES
        from app.domain.text import normalize_string

        normalized = normalize_string(hint, lowercase=True)
        if normalized in VALID_AGENT_CLASSES:
            return Intent(
                type=normalized,
                confidence=1.0,
                method="forced",
            )

        logger.warning(f"Invalid agent class hint: {hint}, using default")
        return Intent(
            type=AGENT_CLASS_GENERAL,
            confidence=0.5,
            method="forced_invalid",
        )

    def _classify_with_llm(self, question: str) -> Intent:
        """Classify using LLM."""
        try:
            from app.services.llm_intent_classifier import classify_intent_with_llm

            result = classify_intent_with_llm(question)
            return Intent(
                type=result["agent_class"],
                confidence=result.get("confidence", 0.5),
                method="llm",
            )
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}, falling back to rules")
            return self._classify_with_rules(question)

    def _classify_with_rules(self, question: str) -> Intent:
        """Classify using rule-based heuristics."""
        from app.services.agent_classifier import classify_agent_class

        agent_class = classify_agent_class(question)
        return Intent(
            type=agent_class,
            confidence=0.5,
            method="rule_based",
        )


# ============================================================================
# Skill Selector
# ============================================================================


class SkillSelector:
    """Select appropriate skill based on intent and query patterns."""

    def select(self, question: str, intent: Intent) -> Skill:
        """
        Select skill based on intent type and query patterns.

        Priority:
        1. Intent-specific skills (cybersecurity, pdf_text)
        2. Query pattern skills (compare, timeline)
        3. Default skill
        """

        # 1. Intent-specific skills
        if intent.type == "cybersecurity":
            from app.services.agent_classifier import pick_cyber_skill

            cyber_skill = pick_cyber_skill(question)
            return Skill(name=cyber_skill, source="agent_class_cybersecurity")

        if intent.type == "pdf_text":
            return Skill(name="pdf_text_reader", source="agent_class_pdf")

        # 2. Query pattern detection
        question_lower = question.lower()

        if "compare" in question_lower or "difference" in question_lower:
            return Skill(name="compare_entities", source="query_pattern_compare")

        if "timeline" in question_lower or "history" in question_lower:
            return Skill(name="timeline_builder", source="query_pattern_timeline")

        # 3. Default skill
        return Skill(name=SKILL_DEFAULT, source="default")


# ============================================================================
# Route Decider
# ============================================================================


class RouteDecider:
    """Decide routing strategy using LLM."""

    def __init__(self, router_prompt: str):
        self.router_prompt = router_prompt

    def decide(
        self,
        question: str,
        intent: Intent,
        skill: Skill,
        use_reasoning: bool = False,
    ) -> RouteCandidate:
        """
        Decide route using LLM.

        Returns:
            RouteCandidate with route, confidence, and reasoning
        """

        try:
            model = get_reasoning_model() if use_reasoning else get_chat_model()

            prompt = f"""{self.router_prompt}

Question: {question}
Agent class: {intent.type}
Suggested skill: {skill.name}"""

            response = model.invoke(prompt)
            response_text = response.content if hasattr(response, "content") else str(response)

            route_data = self._extract_json(response_text)

            # Extract and validate route
            route = self._normalize_route(route_data.get("route", ROUTE_VECTOR))

            # Extract reason
            reason = route_data.get("reason", "llm_decision") or "llm_decision"

            # Extract confidence
            llm_confidence = route_data.get("confidence")
            if llm_confidence is not None and isinstance(llm_confidence, (int, float)):
                confidence = float(llm_confidence)
                confidence = max(0.0, min(1.0, confidence))
            else:
                confidence = 0.7

            # Check for skill override from LLM
            llm_skill_name = route_data.get("skill", "")
            if llm_skill_name and llm_skill_name != "...":
                from app.agents.shared.config import VALID_SKILLS
                from app.domain.text import normalize_string

                normalized_skill = normalize_string(llm_skill_name, lowercase=True)
                if normalized_skill in VALID_SKILLS:
                    skill = Skill(name=normalized_skill, source="llm_override")

            return RouteCandidate(
                route=route,
                confidence=confidence,
                reason=reason,
                skill=skill,
                agent_class=intent.type,
            )

        except Exception as e:
            logger.exception(f"Route decision failed: {e}")
            return RouteCandidate(
                route=ROUTE_VECTOR,
                confidence=0.5,
                reason=f"router_error:{type(e).__name__}",
                skill=skill,
                agent_class=intent.type,
            )

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response."""
        import json
        import re

        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            logger.warning("No JSON found in router response")
            return {"route": ROUTE_VECTOR, "reason": "fallback"}

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}")
            return {"route": ROUTE_VECTOR, "reason": "fallback_json_error"}

    def _normalize_route(self, route: str) -> str:
        """Normalize and validate route."""
        from app.agents.shared.config import VALID_ROUTES
        from app.domain.text import normalize_string

        normalized = normalize_string(route, lowercase=True)
        if normalized in VALID_ROUTES:
            return normalized

        logger.warning(f"Invalid route: {route}, using vector")
        return ROUTE_VECTOR


# ============================================================================
# Fallback Handler
# ============================================================================


class FallbackHandler:
    """Handle low-confidence routing with reasoning model fallback."""

    def handle(
        self,
        question: str,
        candidate: RouteCandidate,
        threshold: float = ROUTER_LOW_CONFIDENCE_THRESHOLD,
    ) -> RouteCandidate:
        """
        Handle low-confidence scenario.

        If confidence < threshold, try reasoning model for better decision.
        If still low, fall back to safe route (vector).
        """

        if candidate.confidence >= threshold:
            return candidate

        logger.info(f"Low confidence: {candidate.confidence:.2f} < {threshold:.2f}, trying reasoning model")

        # Try reasoning model
        try:
            reasoning_candidate = self._try_reasoning_model(question, candidate)

            if reasoning_candidate.confidence >= threshold:
                # Reasoning model improved confidence
                return reasoning_candidate

            logger.warning(f"Reasoning model still low confidence: {reasoning_candidate.confidence:.2f}")
        except Exception as e:
            logger.warning(f"Reasoning model fallback failed: {e}")

        # Fall back to safe route
        return RouteCandidate(
            route=ROUTE_VECTOR,
            confidence=max(0.5, candidate.confidence),
            reason=f"{candidate.reason}|fallback_safe_route",
            skill=candidate.skill,
            agent_class=candidate.agent_class,
        )

    def _try_reasoning_model(
        self,
        question: str,
        candidate: RouteCandidate,
    ) -> RouteCandidate:
        """Try using reasoning model for better decision."""
        from app.agents.router.examples import get_mixed_examples
        from app.prompts import build_router_prompt

        router_prompt = build_router_prompt(
            get_mixed_examples(vector_count=2, graph_count=2, hybrid_count=1, react_count=1)
        )

        model = get_reasoning_model()

        prompt = f"""{router_prompt}

Question: {question}
Agent class: {candidate.agent_class}
Suggested skill: {candidate.skill.name}"""

        response = model.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        # Reuse RouteDecider's extraction logic
        decider = RouteDecider(router_prompt)
        route_data = decider._extract_json(response_text)

        route = decider._normalize_route(route_data.get("route", ROUTE_VECTOR))
        confidence = route_data.get("confidence", 0.7)
        if isinstance(confidence, (int, float)):
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        else:
            confidence = 0.7

        return RouteCandidate(
            route=route,
            confidence=confidence,
            reason=f"{route_data.get('reason', 'fallback_reasoning')}|reasoning_model",
            skill=candidate.skill,
            agent_class=candidate.agent_class,
        )


# ============================================================================
# Main Pipeline
# ============================================================================


class RoutingPipeline:
    """
    Clean routing pipeline with single-responsibility components.

    Flow:
        question → IntentClassifier → SkillSelector → RouteDecider
                → ConfidenceCalibrator → FallbackHandler → FinalRoute
    """

    def __init__(
        self,
        *,
        intent_classifier: IntentClassifierProtocol | None = None,
        skill_selector: SkillSelectorProtocol | None = None,
        route_decider: RouteDeciderProtocol | None = None,
        confidence_calibrator: ConfidenceCalibratorProtocol | None = None,
        fallback_handler: FallbackHandlerProtocol | None = None,
        router_prompt: str | None = None,
    ):
        from app.agents.router.examples import get_mixed_examples
        from app.prompts import build_router_prompt

        prompt = router_prompt or build_router_prompt(
            get_mixed_examples(vector_count=2, graph_count=2, hybrid_count=1, react_count=1)
        )

        self.intent_classifier = intent_classifier or IntentClassifier()
        self.skill_selector = skill_selector or SkillSelector()
        self.route_decider = route_decider or RouteDecider(prompt)
        self.confidence_calibrator = confidence_calibrator or (ConfidenceCalibrator() if ENABLE_CALIBRATION else None)
        self.fallback_handler = fallback_handler or FallbackHandler()

    def decide(
        self,
        question: str,
        use_reasoning: bool = False,
        use_llm_intent: bool = True,
        agent_class_hint: str | None = None,
    ) -> FinalRoute:
        """
        Execute routing pipeline.

        Args:
            question: User question
            use_reasoning: Use reasoning model for route decision
            use_llm_intent: Use LLM for intent classification
            agent_class_hint: Force specific agent class

        Returns:
            FinalRoute with route, skill, confidence, and reasoning
        """

        # Step 1: Classify intent
        intent = self.intent_classifier.classify(
            question,
            use_llm=use_llm_intent,
            forced_hint=agent_class_hint,
        )

        logger.info(f"Intent: {intent.type} (confidence={intent.confidence:.2f}, method={intent.method})")

        # Step 2: Select skill
        skill = self.skill_selector.select(question, intent)

        logger.info(f"Skill: {skill.name} (source={skill.source})")

        # Step 3: Decide route
        candidate = self.route_decider.decide(
            question,
            intent,
            skill,
            use_reasoning=use_reasoning,
        )

        logger.info(
            f"Route candidate: {candidate.route} (confidence={candidate.confidence:.2f}, reason={candidate.reason})"
        )

        # Step 4: Calibrate confidence
        raw_confidence = candidate.confidence
        if self.confidence_calibrator:
            calibrated_confidence = self.confidence_calibrator.calibrate(raw_confidence)
            logger.debug(f"Confidence calibration: {raw_confidence:.2f} → {calibrated_confidence:.2f}")
            candidate = RouteCandidate(
                route=candidate.route,
                confidence=calibrated_confidence,
                reason=candidate.reason,
                skill=candidate.skill,
                agent_class=candidate.agent_class,
            )

        # Step 5: Handle low confidence
        final_candidate = self.fallback_handler.handle(question, candidate)

        if final_candidate != candidate:
            logger.info(
                f"Fallback applied: {candidate.route} → {final_candidate.route} "
                f"(confidence: {candidate.confidence:.2f} → {final_candidate.confidence:.2f})"
            )

        # Step 6: Build final route
        return FinalRoute(
            route=final_candidate.route,
            reason=final_candidate.reason,
            skill=final_candidate.skill.name,
            agent_class=final_candidate.agent_class,
            confidence=final_candidate.confidence,
        )
