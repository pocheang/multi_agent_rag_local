"""
Route Validator Agent - Validates router decisions with layered approach.

Now includes historical accuracy tracking for confidence recalibration.
"""

import asyncio
import logging
import re
import time
from typing import Any

from app.agents.router.accuracy import RouteAccuracyTracker
from app.agents.router.routing import LegacyRouteDecision
from app.agents.shared.config import (
    ROUTE_HIGH_CONFIDENCE_THRESHOLD,
    ROUTE_LOW_CONFIDENCE_THRESHOLD,
    ROUTE_MEDIUM_CONFIDENCE_THRESHOLD,
    ROUTE_VALIDATOR_TIMEOUT_MS,
    VALID_ROUTES,
    VALID_SKILLS,
)
from app.agents.shared.quality_models import RouteValidationResult
from app.core.models import get_chat_model

logger = logging.getLogger(__name__)

# Global accuracy tracker instance
_accuracy_tracker = RouteAccuracyTracker()
_accuracy_tracker.load()  # Load historical data on module import


def _extract_query_features(query: str) -> dict[str, Any]:
    """Extract features from query for rule-based validation"""
    query_lower = query.lower()

    features = {
        "has_relation_keywords": any(
            kw in query_lower for kw in ["关系", "依赖", "连接", "关联", "relationship", "dependency"]
        ),
        "has_comparison_keywords": any(
            kw in query_lower for kw in ["对比", "区别", "差异", "vs", "比较", "compare", "difference"]
        ),
        "has_graph_keywords": any(kw in query_lower for kw in ["路径", "拓扑", "网络", "path", "topology", "network"]),
        "has_pdf_keywords": any(
            kw in query_lower for kw in ["pdf", "文档", "文件", "提取", "document", "file", "extract"]
        ),
        "has_security_keywords": any(
            kw in query_lower for kw in ["安全", "漏洞", "攻击", "防护", "security", "vulnerability", "attack"]
        ),
        "question_words": [w for w in ["什么", "为什么", "如何", "怎么", "what", "why", "how"] if w in query_lower],
        "has_entities": len(re.findall(r"[一-鿿]{2,}|[A-Z][a-z]+", query)) > 1,
    }

    return features


def _rule_based_validation(query: str, route_decision: LegacyRouteDecision) -> dict[str, Any]:
    """Fast rule-based validation"""
    features = _extract_query_features(query)
    issues = []
    confidence = 0.8

    # Check route consistency
    if features["has_relation_keywords"] or features["has_graph_keywords"]:
        if route_decision.route not in ["graph", "hybrid"]:
            issues.append("query_has_relation_keywords_but_route_is_not_graph")
            confidence -= 0.3

    if features["has_comparison_keywords"]:
        if route_decision.skill != "compare_entities":
            issues.append("comparison_query_but_wrong_skill")
            confidence -= 0.2

    if features["has_pdf_keywords"]:
        if route_decision.skill != "pdf_text_reader":
            issues.append("pdf_query_but_wrong_skill")
            confidence -= 0.3

    # Check agent class consistency
    if features["has_security_keywords"]:
        if route_decision.agent_class != "cybersecurity":
            issues.append("security_query_but_wrong_agent_class")
            confidence -= 0.2

    # Validate route and skill are valid
    if route_decision.route not in VALID_ROUTES:
        issues.append(f"invalid_route_{route_decision.route}")
        confidence -= 0.5

    if route_decision.skill not in VALID_SKILLS:
        issues.append(f"invalid_skill_{route_decision.skill}")
        confidence -= 0.4

    confidence = max(0.0, min(1.0, confidence))

    return {
        "confidence": confidence,
        "reason": "rule_validation" if not issues else f"rule_validation_issues:{','.join(issues)}",
        "warnings": issues,
    }


async def _llm_validation(query: str, route_decision: LegacyRouteDecision) -> dict[str, Any]:
    """LLM-based validation for uncertain cases"""
    model = get_chat_model(temperature=0.0)

    prompt = f"""Validate this routing decision for quality assurance.

Query: {query}

Routing Decision:
- Route: {route_decision.route}
- Skill: {route_decision.skill}
- Agent Class: {route_decision.agent_class}
- Reason: {route_decision.reason}

Is this routing decision appropriate? If not, suggest an alternative.

Respond in this format:
VALID: yes/no
CONFIDENCE: 0.0-1.0
REASON: brief explanation
ALTERNATIVE_ROUTE: route (if VALID=no)
ALTERNATIVE_SKILL: skill (if VALID=no)
"""

    try:
        response = await asyncio.wait_for(model.ainvoke(prompt), timeout=ROUTE_VALIDATOR_TIMEOUT_MS / 1000.0)
        content = response.content if hasattr(response, "content") else str(response)

        is_valid = "yes" in content.lower().split("valid:")[1].split("\n")[0] if "valid:" in content.lower() else True

        confidence_match = re.search(r"confidence:\s*([\d.]+)", content.lower())
        confidence = float(confidence_match.group(1)) if confidence_match else 0.7

        reason_match = re.search(r"reason:\s*(.+?)(?:\n|$)", content, re.IGNORECASE)
        reason = reason_match.group(1).strip() if reason_match else "llm_validation"

        alternative = None
        if not is_valid:
            alt_route_match = re.search(r"alternative_route:\s*(\w+)", content, re.IGNORECASE)
            alt_skill_match = re.search(r"alternative_skill:\s*([\w_]+)", content, re.IGNORECASE)

            if alt_route_match or alt_skill_match:
                alternative = {
                    "route": alt_route_match.group(1) if alt_route_match else route_decision.route,
                    "skill": alt_skill_match.group(1) if alt_skill_match else route_decision.skill,
                    "reason": reason,
                }

        return {"is_valid": is_valid, "confidence": confidence, "reason": reason, "alternative": alternative}

    except TimeoutError:
        logger.warning(f"LLM validation timed out after {ROUTE_VALIDATOR_TIMEOUT_MS}ms")
        return {"is_valid": True, "confidence": 0.7, "reason": "llm_timeout", "alternative": None}

    except Exception as e:
        logger.exception(f"LLM validation failed: {e}")
        return {"is_valid": True, "confidence": 0.7, "reason": f"llm_error:{type(e).__name__}", "alternative": None}


async def validate_route_decision(
    query: str, route_decision: LegacyRouteDecision, use_cache: bool = True
) -> RouteValidationResult:
    """
    Validate routing decision with layered approach and historical accuracy tracking.

    Layer 1: High confidence fast pass (>=0.85) - ~5ms
    Layer 2: Rule-based validation (0.6-0.85) - ~30ms
    Layer 3: LLM validation (<0.6) - ~300ms

    Now includes confidence recalibration based on historical accuracy.

    Args:
        query: Original query text
        route_decision: Router's decision to validate
        use_cache: Whether to use cache

    Returns:
        RouteValidationResult with validation outcome
    """
    start_time = time.time()

    # Get router confidence if available
    router_confidence = getattr(route_decision, "confidence", 0.7)

    # Apply historical accuracy recalibration
    recalibrated_confidence = _accuracy_tracker.recalibrate_confidence(route_decision)

    # Use recalibrated confidence for threshold checks
    effective_confidence = recalibrated_confidence

    # Layer 1: High confidence fast pass
    if effective_confidence >= ROUTE_HIGH_CONFIDENCE_THRESHOLD:
        return RouteValidationResult(
            is_valid=True,
            confidence=recalibrated_confidence,
            validation_method="rule_fast",
            validation_reason="high_confidence_fast_pass_with_history",
            execution_time_ms=int((time.time() - start_time) * 1000),
            suggested_alternative=None,
            warnings=[],
        )

    # Layer 2: Rule-based validation
    rule_result = _rule_based_validation(query, route_decision)

    # Blend rule confidence with recalibrated confidence
    blended_confidence = (rule_result["confidence"] + recalibrated_confidence) / 2.0

    if blended_confidence >= ROUTE_MEDIUM_CONFIDENCE_THRESHOLD:
        return RouteValidationResult(
            is_valid=True,
            confidence=blended_confidence,
            validation_method="rule_feature",
            validation_reason=f"{rule_result['reason']}_with_history",
            execution_time_ms=int((time.time() - start_time) * 1000),
            suggested_alternative=None,
            warnings=rule_result.get("warnings", []),
        )

    # Layer 3: LLM validation (only for low confidence)
    if effective_confidence < ROUTE_LOW_CONFIDENCE_THRESHOLD:
        llm_result = await _llm_validation(query, route_decision)

        return RouteValidationResult(
            is_valid=llm_result["is_valid"],
            confidence=llm_result["confidence"],
            validation_method="llm",
            validation_reason=llm_result["reason"],
            execution_time_ms=int((time.time() - start_time) * 1000),
            suggested_alternative=llm_result.get("alternative"),
            warnings=[],
        )

    # Default: Medium confidence, pass with warning
    return RouteValidationResult(
        is_valid=True,
        confidence=blended_confidence if "blended_confidence" in locals() else 0.7,
        validation_method="rule_feature",
        validation_reason="medium_confidence_default",
        execution_time_ms=int((time.time() - start_time) * 1000),
        suggested_alternative=None,
        warnings=["medium_confidence"],
    )


def record_route_outcome(query: str, route_decision: LegacyRouteDecision, was_successful: bool, execution_time_ms: int):
    """
    Record the outcome of a routing decision for historical tracking.

    This should be called after executing a route to track whether it was successful.

    Args:
        query: Original query text
        route_decision: Router's decision that was executed
        was_successful: Whether the route produced good results
        execution_time_ms: Execution time
    """
    _accuracy_tracker.record_outcome(
        query=query, route_decision=route_decision, was_successful=was_successful, execution_time_ms=execution_time_ms
    )
