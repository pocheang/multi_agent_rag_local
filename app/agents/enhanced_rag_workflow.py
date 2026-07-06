"""
Enhanced RAG Workflow - Integration of all quality assurance agents.

This is the production-ready orchestration layer that combines:
- Task 2: Route Validator (validate routing decisions)
- Task 3: Retrieval Quality (async parallel evaluation)
- Task 4: Answer Validator (4-level validation cascade)
- Task 5: Quality Orchestrator (score fusion & reporting)
- Task 6: Context Tracker (multi-turn context awareness)

Performance targets:
- Average added latency: <250ms
- Fast path (high quality): <150ms
- Route retry: max 1 attempt
- Answer retry: max 1 attempt
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional

from app.agents.router_agent import decide_route, RouteDecision
from app.agents.route_validator_agent import validate_route_decision
from app.agents.retrieval_quality_agent import evaluate_retrieval_quality
from app.agents.answer_validator_agent import validate_answer
from app.agents.quality_orchestrator_agent import orchestrate_quality
from app.agents.context_tracker_agent import (
    get_context_aware_routing_hints,
    resolve_query_with_context,
    update_conversation_context,
)
from app.agents.vector_rag_agent import run_vector_rag
from app.agents.graph_rag_agent import run_graph_rag
from app.agents.web_research_agent import run_web_research
from app.agents.quality_models import (
    QualityReport,
    RouteValidationResult,
    RetrievalQualityResult,
    RetrievalQualityMetrics,
    AnswerValidationResult,
    AnswerValidationDetails,
)
from app.agents.degradation_strategies import (
    apply_fallback_strategy,
    get_circuit_breaker,
    record_component_success,
)
from app.core.models import get_chat_model, get_reasoning_model
from app.services.agent_execution_tracker import get_tracker

logger = logging.getLogger(__name__)


def _extract_entities(text: str) -> List[str]:
    """
    Simple entity extraction from text.

    Extracts capitalized words and common named entities.

    Args:
        text: Text to extract entities from

    Returns:
        List of extracted entity strings
    """
    import re

    # Extract capitalized words (potential entities)
    entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)

    # Extract Chinese entity-like patterns (2-4 characters)
    chinese_entities = re.findall(r'[一-鿿]{2,4}', text)

    # Combine and deduplicate
    all_entities = list(set(entities + chinese_entities))

    # Limit to top 10 entities
    return all_entities[:10]


class EnhancedRAGWorkflow:
    """
    Production RAG workflow with integrated quality assurance.

    Quality checkpoints:
    1. Route validation with retry (Task 2)
    2. Retrieval quality assessment (Task 3)
    3. Answer validation with regeneration (Task 4)
    4. Quality score fusion (Task 5)
    5. Context tracking for multi-turn (Task 6)
    """

    def __init__(
        self,
        max_route_retries: int = 2,
        max_answer_retries: int = 2,
        enable_context_tracking: bool = True,
        quality_threshold: float = 0.6,
    ):
        """
        Initialize Enhanced RAG Workflow.

        Args:
            max_route_retries: Maximum retrieval retry attempts (default 2, means up to 3 total attempts: initial + 2 retries)
            max_answer_retries: Maximum answer regeneration retry attempts (default 2, means up to 3 total attempts: initial + 2 retries)
            enable_context_tracking: Enable multi-turn context tracking (default True)
            quality_threshold: Minimum quality score to accept retrieval results without retry (default 0.6)
        """
        self.max_route_retries = max_route_retries
        self.max_answer_retries = max_answer_retries
        self.enable_context_tracking = enable_context_tracking
        self.quality_threshold = quality_threshold
        logger.info(
            f"EnhancedRAGWorkflow initialized: "
            f"route_retries={max_route_retries}, "
            f"answer_retries={max_answer_retries}, "
            f"context_tracking={enable_context_tracking}, "
            f"quality_threshold={quality_threshold}"
        )

    async def execute_query(
        self,
        query: str,
        user_id: str,
        session_id: str,
        allowed_sources: Optional[List[str]] = None,
        retrieval_strategy: Optional[str] = None,
        agent_class_hint: Optional[str] = None,
        timeout_ms: int = 10000,  # P1-11: Total timeout protection (10 seconds default)
    ) -> Dict[str, Any]:
        """
        Execute complete quality-enhanced RAG pipeline with timeout protection.

        Args:
            query: User query text
            user_id: User identifier
            session_id: Conversation session identifier
            allowed_sources: Optional document source filter
            retrieval_strategy: Optional retrieval strategy
            agent_class_hint: Optional agent class hint
            timeout_ms: Maximum execution time in milliseconds (default 10000)

        Returns:
            Dictionary with:
            - answer: Final answer text
            - citations: List of citations
            - quality_report: Comprehensive quality assessment
            - route_used: Route that was used
            - execution_metadata: Performance metrics
        """
        try:
            # Execute with timeout protection (P1-11)
            result = await asyncio.wait_for(
                self._execute_query_internal(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    allowed_sources=allowed_sources,
                    retrieval_strategy=retrieval_strategy,
                    agent_class_hint=agent_class_hint,
                ),
                timeout=timeout_ms / 1000.0
            )
            return result

        except asyncio.TimeoutError:
            logger.error(f"Query timed out after {timeout_ms}ms: {query[:100]}...")
            return self._create_timeout_response(query, timeout_ms)

    async def _execute_query_internal(
        self,
        query: str,
        user_id: str,
        session_id: str,
        allowed_sources: Optional[List[str]] = None,
        retrieval_strategy: Optional[str] = None,
        agent_class_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Internal execution method without timeout wrapper.

        This is separated to allow timeout protection at the top level.
        """
        start_time = time.time()
        execution_metadata = {
            "route_retry": 0,
            "answer_retry": 0,
            "retry_count": 0,
            "degradation_applied": False,
            "circuit_breaker_triggered": False,
            "validation_degraded": False,
            "degradation_events": [],
        }

        # Initialize execution tracker
        tracker = get_tracker()
        execution_id = tracker.start_execution(query=query, user_id=user_id)

        try:
            # Step 1: Get context hints from conversation history (Task 6)
            context_hints = None
            resolved_query = query
            if self.enable_context_tracking:
                context_hints = get_context_aware_routing_hints(session_id, query)
                logger.debug(f"Context hints: {context_hints}")
                if context_hints and context_hints.resolve_references:
                    resolved_query = resolve_query_with_context(query, context_hints)
                    if resolved_query != query:
                        logger.info("Resolved follow-up query with conversation context")

            # Step 2: Route decision with validation and retry (Task 2)
            route_step_id = tracker.record_agent_step(
                execution_id=execution_id,
                agent_name="router",
                input_data={"query": resolved_query, "agent_class_hint": agent_class_hint}
            )

            route_decision, route_validation = await self._route_with_validation(
                query=resolved_query,
                agent_class_hint=agent_class_hint,
                context_hints=context_hints,
                execution_metadata=execution_metadata,
            )

            tracker.complete_agent_step(
                execution_id=execution_id,
                step_id=route_step_id,
                output_data={
                    "route": route_decision.route,
                    "confidence": route_decision.confidence,
                    "skill": route_decision.skill
                },
                metadata={"validation_passed": route_validation.is_valid}
            )

            # Step 3: Execute retrieval based on validated route with intelligent retry
            retrieval_result = None
            retrieval_quality = None
            retrieval_retry_count = 0
            current_top_k = 5
            current_route = route_decision.route

            retrieval_step_id = tracker.record_agent_step(
                execution_id=execution_id,
                agent_name=f"{current_route}_retrieval",
                input_data={"query": resolved_query, "route": current_route}
            )

            while retrieval_retry_count <= self.max_route_retries:
                try:
                    retrieval_result = await self._execute_retrieval(
                        query=resolved_query,
                        route_decision=route_decision if retrieval_retry_count == 0 else RouteDecision(
                            route=current_route,
                            skill=route_decision.skill,
                            agent_class=route_decision.agent_class,
                            reason=f"retry_{retrieval_retry_count}_route_{current_route}",
                            confidence=route_decision.confidence,
                        ),
                        allowed_sources=allowed_sources,
                        retrieval_strategy=retrieval_strategy,
                        execution_metadata=execution_metadata,
                        retry_attempt=retrieval_retry_count,
                        top_k=current_top_k,
                    )

                    tracker.complete_agent_step(
                        execution_id=execution_id,
                        step_id=retrieval_step_id,
                        output_data={
                            "chunks_count": len(retrieval_result.get("chunks", [])),
                            "route": current_route
                        }
                    )

                    # Step 4: Assess retrieval quality
                    try:
                        retrieval_quality = await evaluate_retrieval_quality(
                            query=resolved_query,
                            chunks=retrieval_result["chunks"],
                            metadata=retrieval_result["metadata"],
                        )
                        record_component_success("retrieval_quality")
                    except Exception as e:
                        logger.warning(f"Retrieval quality evaluation failed: {e}", exc_info=True)
                        fallback_info = apply_fallback_strategy("quality_validation", e)
                        execution_metadata["validation_degraded"] = True
                        execution_metadata["degradation_events"].append({
                            "component": "retrieval_quality",
                            "error": str(e),
                            "action": "use_default_score",
                        })

                        # Use default quality result
                        retrieval_quality = RetrievalQualityResult(
                            overall_quality=0.5,
                            metrics=RetrievalQualityMetrics(
                                coverage_score=0.5,
                                relevance_score=0.5,
                                diversity_score=0.5,
                                completeness_score=0.5,
                            ),
                            execution_time_ms=0,
                        )

                    # Check if quality is acceptable or if we've exhausted retries
                    quality_score = getattr(retrieval_quality, 'overall_quality', 1.0) if retrieval_quality else 1.0
                    if quality_score >= self.quality_threshold or retrieval_retry_count >= self.max_route_retries:
                        # Quality is acceptable or max retries reached
                        break

                    # Quality is low, apply retry strategy
                    retrieval_retry_count += 1
                    execution_metadata["retry_count"] += 1

                    # Exponential backoff: 100ms for first retry, 500ms for second
                    backoff_ms = 100 if retrieval_retry_count == 1 else 500
                    logger.info(
                        f"Retrieval quality low ({quality_score:.3f}), "
                        f"retrying with variation (attempt {retrieval_retry_count}/{self.max_route_retries}), "
                        f"backoff={backoff_ms}ms"
                    )
                    await asyncio.sleep(backoff_ms / 1000.0)

                    # Apply retry variation based on attempt number
                    if retrieval_retry_count == 1:
                        # First retry: increase top-k from 5 to 10
                        current_top_k = 10
                        logger.info("Retry variation 1: increasing top-k from 5 to 10")
                    elif retrieval_retry_count == 2:
                        # Second retry: try alternative route
                        if current_route == "vector":
                            current_route = "hybrid"
                            logger.info("Retry variation 2: switching from vector to hybrid route")
                        elif current_route == "graph":
                            current_route = "hybrid"
                            logger.info("Retry variation 2: switching from graph to hybrid route")
                        else:
                            # Already hybrid, try increasing top-k further
                            current_top_k = 15
                            logger.info("Retry variation 2: increasing top-k to 15 (already using hybrid)")

                except Exception as e:
                    logger.error(f"Retrieval failed on attempt {retrieval_retry_count}: {e}", exc_info=True)

                    # If this is not the last retry, try again with variation
                    if retrieval_retry_count < self.max_route_retries:
                        retrieval_retry_count += 1
                        execution_metadata["retry_count"] += 1

                        # Exponential backoff
                        backoff_ms = 100 if retrieval_retry_count == 1 else 500
                        await asyncio.sleep(backoff_ms / 1000.0)

                        # Apply fallback route
                        component = "vector_rag" if current_route == "vector" else "graph_rag"
                        fallback_info = apply_fallback_strategy(component, e, {"query": query, "route": current_route})

                        execution_metadata["degradation_applied"] = True
                        execution_metadata["degradation_events"].append({
                            "component": component,
                            "error": str(e),
                            "fallback": fallback_info["fallback_route"],
                            "retry_attempt": retrieval_retry_count,
                        })

                        # Switch to fallback route
                        if fallback_info["fallback_route"] and fallback_info["fallback_route"] != current_route:
                            current_route = fallback_info["fallback_route"]
                            logger.info(f"Switching to fallback route: {current_route}")
                        continue
                    else:
                        # Last retry failed, raise the error
                        raise

            # Ensure we have retrieval result and quality
            if retrieval_result is None:
                raise Exception("Retrieval failed after all retry attempts")
            if retrieval_quality is None:
                # Should not happen, but provide default
                retrieval_quality = RetrievalQualityResult(
                    overall_quality=0.5,
                    metrics=RetrievalQualityMetrics(
                        coverage_score=0.5,
                        relevance_score=0.5,
                        diversity_score=0.5,
                        completeness_score=0.5,
                    ),
                    execution_time_ms=0,
                )

            # Step 5: Generate answer with validation and retry (Task 4)
            answer, citations, answer_validation = await self._generate_answer_with_validation(
                query=query,
                context=retrieval_result["context"],
                citations=retrieval_result["citations"],
                route=route_decision.route,
                execution_metadata=execution_metadata,
            )

            # Step 6: Orchestrate quality scores (Task 5)
            total_time_ms = int((time.time() - start_time) * 1000)
            execution_metadata["total_time_ms"] = total_time_ms

            quality_report = orchestrate_quality(
                route_validation=route_validation,
                retrieval_quality=retrieval_quality,
                answer_validation=answer_validation,
                execution_metadata=execution_metadata,
            )

            # Step 7: Update conversation context (Task 6)
            if self.enable_context_tracking:
                entities = _extract_entities(query + " " + answer)
                await update_conversation_context(
                    session_id=session_id,
                    user_id=user_id,
                    query=query,
                    response=answer,
                    route=route_decision.route,
                    entities=entities,
                )

            logger.info(
                f"Enhanced RAG completed: "
                f"route={route_decision.route}, "
                f"quality={quality_report.quality_level}, "
                f"confidence={quality_report.overall_confidence:.3f}, "
                f"time={total_time_ms}ms, "
                f"retries={execution_metadata['retry_count']}"
            )

            # Mark execution as complete
            tracker.complete_execution(execution_id, final_result={
                "route": route_decision.route,
                "quality_level": quality_report.quality_level,
                "confidence": quality_report.overall_confidence,
            })

            return {
                "answer": answer,
                "citations": citations,
                "quality_report": quality_report,
                "route_used": route_decision.route,
                "route_reason": route_decision.reason,
                "skill_used": route_decision.skill,
                "agent_class": route_decision.agent_class,
                "execution_metadata": {
                    "total_time_ms": total_time_ms,
                    "validation_overhead_ms": quality_report.execution_stats.validation_overhead_ms,
                    "route_retry": execution_metadata["route_retry"],
                    "answer_retry": execution_metadata["answer_retry"],
                    "retry_count": execution_metadata["retry_count"],
                    "context_tracking_enabled": self.enable_context_tracking,
                    "degradation_applied": execution_metadata["degradation_applied"],
                    "circuit_breaker_triggered": execution_metadata["circuit_breaker_triggered"],
                    "validation_degraded": execution_metadata["validation_degraded"],
                    "degradation_events": execution_metadata["degradation_events"],
                },
            }

        except Exception as e:
            # Mark execution as failed
            tracker.fail_execution(execution_id, str(e))
            logger.exception(f"Enhanced RAG workflow failed: {e}")
            raise

    async def _route_with_validation(
        self,
        query: str,
        agent_class_hint: Optional[str],
        context_hints: Optional[Any],
        execution_metadata: Dict[str, Any],
    ) -> tuple[RouteDecision, RouteValidationResult]:
        """
        Route decision with validation and optional retry.
        Includes graceful degradation for router failures.

        Returns:
            Tuple of (RouteDecision, RouteValidationResult)
        """
        # Apply context hints if available
        if context_hints and context_hints.previous_route and context_hints.followup:
            logger.debug(f"Using previous route hint: {context_hints.previous_route}")
            # Context-aware routing could prefer previous route for follow-ups
            # For now, we let the router decide but log the hint

        # Initial routing decision with degradation handling
        try:
            # Check circuit breaker for router
            router_cb = get_circuit_breaker("router")
            if router_cb.is_open():
                logger.warning("Router circuit breaker is OPEN, using fallback route")
                execution_metadata["circuit_breaker_triggered"] = True
                execution_metadata["degradation_applied"] = True
                execution_metadata["degradation_events"].append({
                    "component": "router",
                    "reason": "circuit_breaker_open",
                    "fallback": "vector",
                })
                route_decision = RouteDecision(
                    route="vector",
                    skill="answer_with_citations",
                    agent_class=agent_class_hint or "general",
                    reason="circuit_breaker_open_fallback_to_vector",
                    confidence=0.5,
                )
            else:
                route_decision = decide_route(
                    question=query,
                    use_reasoning=False,
                    agent_class_hint=agent_class_hint,
                    use_llm_intent=True,
                )
                record_component_success("router")

        except Exception as e:
            logger.error(f"Router failed: {e}", exc_info=True)
            fallback_info = apply_fallback_strategy("router", e, {"query": query})
            execution_metadata["degradation_applied"] = True
            execution_metadata["degradation_events"].append({
                "component": "router",
                "error": str(e),
                "fallback": fallback_info["fallback_route"],
            })

            # Use fallback route decision
            route_decision = RouteDecision(
                route=fallback_info["fallback_route"] or "vector",
                skill="answer_with_citations",
                agent_class=agent_class_hint or "general",
                reason=fallback_info["reason"],
                confidence=0.5,
            )

        # Validate route decision (Task 2) with degradation handling
        try:
            route_validation = await validate_route_decision(query, route_decision)
            record_component_success("route_validation")

        except Exception as e:
            logger.warning(f"Route validation failed: {e}", exc_info=True)
            fallback_info = apply_fallback_strategy("route_validation", e)
            execution_metadata["validation_degraded"] = True
            execution_metadata["degradation_events"].append({
                "component": "route_validation",
                "error": str(e),
                "action": "skip_validation",
            })

            # Create minimal validation result
            route_validation = RouteValidationResult(
                is_valid=True,
                confidence=0.5,
                validation_method="rule_fast",
                execution_time_ms=0,
                validation_reason="validation_failed_degraded",
                suggested_alternative=None,
            )

        # Retry logic: if validation fails and suggests alternative
        if (
            not route_validation.is_valid
            and route_validation.suggested_alternative
            and execution_metadata["route_retry"] < self.max_route_retries
        ):
            logger.warning(
                f"Route validation failed: {route_validation.validation_reason}. "
                f"Retrying with alternative: {route_validation.suggested_alternative}"
            )
            execution_metadata["route_retry"] += 1
            execution_metadata["retry_count"] += 1

            # Apply suggested alternative
            alt = route_validation.suggested_alternative
            route_decision = RouteDecision(
                route=alt["route"],
                skill=alt["skill"],
                agent_class=route_decision.agent_class,
                reason=f"retry_from_validation:{alt['reason']}",
                confidence=0.75,
            )

            # Re-validate the alternative
            try:
                route_validation = await validate_route_decision(query, route_decision)
                record_component_success("route_validation")
            except Exception as e:
                logger.warning(f"Route validation retry failed: {e}")
                # Use minimal validation on retry failure
                route_validation = RouteValidationResult(
                    is_valid=True,
                    confidence=0.5,
                    validation_method="rule_fast",
                    execution_time_ms=0,
                    validation_reason="retry_validation_failed_degraded",
                    suggested_alternative=None,
                )

        logger.info(
            f"Route validation: valid={route_validation.is_valid}, "
            f"confidence={route_validation.confidence:.3f}, "
            f"method={route_validation.validation_method}, "
            f"time={route_validation.execution_time_ms}ms"
        )

        return route_decision, route_validation

    async def _execute_retrieval(
        self,
        query: str,
        route_decision: RouteDecision,
        allowed_sources: Optional[List[str]],
        retrieval_strategy: Optional[str],
        execution_metadata: Dict[str, Any],
        retry_attempt: int = 0,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Execute retrieval based on route decision with exception isolation.
        Includes graceful degradation for retrieval failures.

        Returns:
            Dictionary with context, citations, chunks, and metadata
        """
        route = route_decision.route

        try:
            if route == "graph":
                # Check circuit breaker for graph RAG
                graph_cb = get_circuit_breaker("graph_rag")
                if graph_cb.is_open():
                    logger.warning("Graph RAG circuit breaker is OPEN, falling back to vector")
                    execution_metadata["circuit_breaker_triggered"] = True
                    raise Exception("Circuit breaker open for graph_rag")

                # Graph RAG retrieval
                graph_result = run_graph_rag(
                    question=query,
                    allowed_sources=allowed_sources,
                )
                record_component_success("graph_rag")
                return {
                    "context": graph_result.get("context", ""),
                    "citations": graph_result.get("citations", []),
                    "chunks": self._extract_chunks_from_graph(graph_result),
                    "metadata": {"route": "graph"},
                }

            elif route == "hybrid":
                # Check circuit breakers
                vector_cb = get_circuit_breaker("vector_rag")
                graph_cb = get_circuit_breaker("graph_rag")

                vector_result = None
                graph_result = None

                # Try vector RAG
                if not vector_cb.is_open():
                    try:
                        vector_result = run_vector_rag(
                            question=query,
                            allowed_sources=allowed_sources,
                            retrieval_strategy=retrieval_strategy,
                            agent_class=route_decision.agent_class,
                            top_k=top_k,
                        )
                        record_component_success("vector_rag")
                    except Exception as e:
                        logger.warning(f"Vector RAG failed in hybrid mode: {e}")
                        apply_fallback_strategy("vector_rag", e)
                else:
                    logger.warning("Vector RAG circuit breaker is OPEN, skipping in hybrid")

                # Try graph RAG
                if not graph_cb.is_open():
                    try:
                        graph_result = run_graph_rag(
                            question=query,
                            allowed_sources=allowed_sources,
                        )
                        record_component_success("graph_rag")
                    except Exception as e:
                        logger.warning(f"Graph RAG failed in hybrid mode: {e}")
                        apply_fallback_strategy("graph_rag", e)
                else:
                    logger.warning("Graph RAG circuit breaker is OPEN, skipping in hybrid")

                # Merge results or use what we have
                if vector_result and graph_result:
                    combined_context = f"{vector_result.get('context', '')}\n\n{graph_result.get('context', '')}"
                    combined_citations = vector_result.get("citations", []) + graph_result.get("citations", [])
                    return {
                        "context": combined_context,
                        "citations": combined_citations,
                        "chunks": self._extract_chunks_from_vector(vector_result),
                        "metadata": {"route": "hybrid"},
                    }
                elif vector_result:
                    logger.info("Hybrid mode degraded to vector only")
                    return {
                        "context": vector_result.get("context", ""),
                        "citations": vector_result.get("citations", []),
                        "chunks": self._extract_chunks_from_vector(vector_result),
                        "metadata": {"route": "hybrid_degraded_vector_only"},
                    }
                elif graph_result:
                    logger.info("Hybrid mode degraded to graph only")
                    return {
                        "context": graph_result.get("context", ""),
                        "citations": graph_result.get("citations", []),
                        "chunks": self._extract_chunks_from_graph(graph_result),
                        "metadata": {"route": "hybrid_degraded_graph_only"},
                    }
                else:
                    raise Exception("Both vector and graph failed in hybrid mode")

            else:
                # Check circuit breaker for vector RAG
                vector_cb = get_circuit_breaker("vector_rag")
                if vector_cb.is_open():
                    logger.warning("Vector RAG circuit breaker is OPEN, falling back to graph")
                    execution_metadata["circuit_breaker_triggered"] = True
                    raise Exception("Circuit breaker open for vector_rag")

                # Default: vector RAG
                vector_result = run_vector_rag(
                    question=query,
                    allowed_sources=allowed_sources,
                    retrieval_strategy=retrieval_strategy,
                    agent_class=route_decision.agent_class,
                    top_k=top_k,
                )
                record_component_success("vector_rag")
                return {
                    "context": vector_result.get("context", ""),
                    "citations": vector_result.get("citations", []),
                    "chunks": self._extract_chunks_from_vector(vector_result),
                    "metadata": {
                        "route": "vector",
                        "retrieved_count": vector_result.get("retrieved_count", 0),
                    },
                }

        except Exception as e:
            logger.error(f"Retrieval failed for route={route}: {e}", exc_info=True)

            # Apply fallback strategy
            component = "vector_rag" if route == "vector" else "graph_rag"
            fallback_info = apply_fallback_strategy(component, e, {"query": query, "route": route})

            # Track degradation
            execution_metadata["degradation_applied"] = True
            execution_metadata["degradation_events"].append({
                "component": component,
                "error": str(e),
                "fallback": fallback_info["fallback_route"],
            })

            # Try fallback route
            fallback_route = fallback_info["fallback_route"]
            fallback_alternatives = fallback_info.get("fallback_alternatives", [])

            if fallback_route and fallback_route != route:
                logger.info(f"Attempting fallback from {route} to {fallback_route}")

                try:
                    if fallback_route == "graph":
                        graph_cb = get_circuit_breaker("graph_rag")
                        if not graph_cb.is_open():
                            graph_result = run_graph_rag(
                                question=query,
                                allowed_sources=allowed_sources,
                            )
                            record_component_success("graph_rag")
                            return {
                                "context": graph_result.get("context", ""),
                                "citations": graph_result.get("citations", []),
                                "chunks": self._extract_chunks_from_graph(graph_result),
                                "metadata": {"route": f"fallback_{fallback_route}", "original_route": route},
                            }
                    elif fallback_route == "web":
                        logger.info("Attempting web search fallback")
                        web_result = run_web_research(question=query)
                        record_component_success("web_research")
                        return {
                            "context": web_result.get("context", ""),
                            "citations": web_result.get("citations", []),
                            "chunks": [],
                            "metadata": {"route": "fallback_web", "original_route": route},
                        }
                    else:  # fallback to vector
                        vector_cb = get_circuit_breaker("vector_rag")
                        if not vector_cb.is_open():
                            vector_result = run_vector_rag(
                                question=query,
                                allowed_sources=allowed_sources,
                                retrieval_strategy=retrieval_strategy,
                                agent_class=route_decision.agent_class,
                                top_k=top_k,
                            )
                            record_component_success("vector_rag")
                            return {
                                "context": vector_result.get("context", ""),
                                "citations": vector_result.get("citations", []),
                                "chunks": self._extract_chunks_from_vector(vector_result),
                                "metadata": {"route": f"fallback_{fallback_route}", "original_route": route},
                            }

                except Exception as fallback_error:
                    logger.error(f"Fallback retrieval also failed: {fallback_error}", exc_info=True)

                    # Try fallback alternatives (e.g., web search if graph failed)
                    for alt_route in fallback_alternatives:
                        if alt_route == route or alt_route == fallback_route:
                            continue

                        logger.info(f"Attempting alternative fallback: {alt_route}")
                        try:
                            if alt_route == "web":
                                web_result = run_web_research(question=query)
                                record_component_success("web_research")
                                return {
                                    "context": web_result.get("context", ""),
                                    "citations": web_result.get("citations", []),
                                    "chunks": [],
                                    "metadata": {"route": f"fallback_{alt_route}", "original_route": route},
                                }
                            elif alt_route == "graph":
                                graph_cb = get_circuit_breaker("graph_rag")
                                if not graph_cb.is_open():
                                    graph_result = run_graph_rag(
                                        question=query,
                                        allowed_sources=allowed_sources,
                                    )
                                    record_component_success("graph_rag")
                                    return {
                                        "context": graph_result.get("context", ""),
                                        "citations": graph_result.get("citations", []),
                                        "chunks": self._extract_chunks_from_graph(graph_result),
                                        "metadata": {"route": f"fallback_{alt_route}", "original_route": route},
                                    }
                            elif alt_route == "vector":
                                vector_cb = get_circuit_breaker("vector_rag")
                                if not vector_cb.is_open():
                                    vector_result = run_vector_rag(
                                        question=query,
                                        allowed_sources=allowed_sources,
                                        retrieval_strategy=retrieval_strategy,
                                        agent_class=route_decision.agent_class,
                                        top_k=top_k,
                                    )
                                    record_component_success("vector_rag")
                                    return {
                                        "context": vector_result.get("context", ""),
                                        "citations": vector_result.get("citations", []),
                                        "chunks": self._extract_chunks_from_vector(vector_result),
                                        "metadata": {"route": f"fallback_{alt_route}", "original_route": route},
                                    }
                        except Exception as alt_error:
                            logger.error(f"Alternative fallback {alt_route} also failed: {alt_error}", exc_info=True)
                            continue

            # Last resort: return empty context
            logger.error("All retrieval attempts failed, returning empty context")
            return {
                "context": "",
                "citations": [],
                "chunks": [],
                "metadata": {"route": "failed", "error": str(e)},
            }

    async def _generate_answer_with_validation(
        self,
        query: str,
        context: str,
        citations: List[Dict],
        route: str,
        execution_metadata: Dict[str, Any],
    ) -> tuple[str, List[Dict], AnswerValidationResult]:
        """
        Generate answer with validation and optional regeneration with intelligent retry.
        Includes graceful degradation for validation failures.

        Returns:
            Tuple of (answer, citations, AnswerValidationResult)
        """
        answer = None
        answer_validation = None
        answer_retry_count = 0
        use_reasoning_model = False

        while answer_retry_count <= self.max_answer_retries:
            # Generate answer
            answer = await self._generate_answer(
                query,
                context,
                route,
                use_reasoning=use_reasoning_model,
                regeneration_prompt=(
                    "Previous answer had quality issues. "
                    "Please ensure: (1) all claims are supported by context, "
                    "(2) citations are complete, (3) no speculation."
                ) if answer_retry_count > 0 else None,
            )

            # Validate answer (Task 4) with degradation handling
            try:
                answer_validation = await validate_answer(
                    query=query,
                    answer=answer,
                    source_docs=citations,
                    citations=citations,
                )
                record_component_success("answer_validation")

            except Exception as e:
                logger.warning(f"Answer validation failed: {e}", exc_info=True)
                fallback_info = apply_fallback_strategy("answer_validation", e)
                execution_metadata["validation_degraded"] = True
                execution_metadata["degradation_events"].append({
                    "component": "answer_validation",
                    "error": str(e),
                    "action": "skip_validation",
                })

                # Create minimal validation result
                answer_validation = AnswerValidationResult(
                    is_valid=True,
                    overall_score=0.7,
                    validation_details=AnswerValidationDetails(
                        factual_consistency=0.7,
                        hallucination_risk=0.3,
                        citation_completeness=0.7,
                        answer_quality=0.7,
                        safety_score=1.0,
                    ),
                    action="approve",
                    validation_method="fast_path",
                    execution_time_ms=0,
                    issues=[],
                )

            # Check if answer is acceptable or if we've exhausted retries
            if answer_validation.action != "regenerate" or answer_retry_count >= self.max_answer_retries:
                break

            # Answer needs regeneration, apply retry strategy
            answer_retry_count += 1
            execution_metadata["answer_retry"] += 1
            execution_metadata["retry_count"] += 1

            # Exponential backoff: 100ms for first retry, 500ms for second
            backoff_ms = 100 if answer_retry_count == 1 else 500
            logger.warning(
                f"Answer validation suggests regeneration: "
                f"score={answer_validation.overall_score:.3f}, "
                f"issues={len(answer_validation.issues)}, "
                f"retry {answer_retry_count}/{self.max_answer_retries}, "
                f"backoff={backoff_ms}ms"
            )
            await asyncio.sleep(backoff_ms / 1000.0)

            # Apply retry variation: use reasoning model on third attempt (answer_retry_count == 2)
            if answer_retry_count >= 2:
                use_reasoning_model = True
                logger.info("Retry variation: switching to reasoning model for answer generation")

        logger.info(
            f"Answer validation: score={answer_validation.overall_score:.3f}, "
            f"action={answer_validation.action}, "
            f"method={answer_validation.validation_method}, "
            f"time={answer_validation.execution_time_ms}ms, "
            f"retries={answer_retry_count}"
        )

        return answer, citations, answer_validation

    async def _generate_answer(
        self,
        query: str,
        context: str,
        route: str,
        use_reasoning: bool = False,
        regeneration_prompt: Optional[str] = None,
    ) -> str:
        """
        Generate answer using LLM.

        Args:
            query: User query
            context: Retrieved context
            route: Route used
            use_reasoning: Whether to use reasoning model instead of chat model
            regeneration_prompt: Optional quality improvement instructions

        Returns:
            Generated answer text
        """
        # Select model based on retry strategy
        if use_reasoning:
            model = get_reasoning_model()
            logger.info("Using reasoning model for answer generation")
        else:
            model = get_chat_model()

        prompt = f"""You are a helpful RAG assistant. Answer the question based on the provided context.

Context:
{context}

Question: {query}

Instructions:
- Base your answer strictly on the context provided
- Cite sources when making factual claims
- If the context doesn't contain enough information, say so
- Be concise and direct
"""

        if regeneration_prompt:
            prompt += f"\n\nQuality Requirements:\n{regeneration_prompt}"

        response = await model.ainvoke(prompt)
        answer = response.content if hasattr(response, "content") else str(response)

        return answer.strip()

    def _extract_chunks_from_vector(self, vector_result: Dict[str, Any]) -> List[Dict]:
        """Extract chunks from vector RAG result for quality assessment."""
        chunks = []
        citations = vector_result.get("citations", [])

        for citation in citations:
            chunks.append({
                "content": citation.get("content", ""),
                "source": citation.get("source", ""),
                "score": citation.get("metadata", {}).get("hybrid_score", 0.5),
            })

        return chunks

    def _extract_chunks_from_graph(self, graph_result: Dict[str, Any]) -> List[Dict]:
        """Extract chunks from graph RAG result for quality assessment."""
        # Graph RAG returns entities and relations
        # Convert to chunk format for quality assessment
        chunks = []
        entities = graph_result.get("entities", [])

        for entity in entities[:10]:  # Limit to top 10
            # Handle both dict and string entities
            if isinstance(entity, dict):
                content = str(entity.get("description", entity.get("name", "")))
            else:
                content = str(entity)

            chunks.append({
                "content": content,
                "source": "graph",
                "score": 0.8,  # Graph results have implicit high relevance
            })

        return chunks


    def _create_timeout_response(self, query: str, timeout_ms: int) -> Dict[str, Any]:
        """
        Create a response when query times out (P1-11).

        Args:
            query: Original query
            timeout_ms: Timeout value that was exceeded

        Returns:
            Error response with timeout information
        """
        from app.agents.quality_models import (
            QualityReport,
            QualityBreakdown,
            ExecutionStats,
        )

        quality_report = QualityReport(
            overall_confidence=0.0,
            quality_level="very_low",
            quality_label="超时",
            user_prompt=f"⚠️ 查询超时（{timeout_ms}ms），请简化问题或稍后重试",
            breakdown=QualityBreakdown(
                route_decision={"score": 0.0, "status": "⏱ 超时"},
                retrieval={"score": 0.0, "status": "⏱ 超时"},
                answer_factuality={"score": 0.0, "status": "⏱ 超时"},
                citations={"score": 0.0, "status": "⏱ 超时"},
            ),
            issues=[{
                "severity": "critical",
                "component": "workflow",
                "message": f"Query execution exceeded {timeout_ms}ms timeout"
            }],
            suggestions=["简化查询", "分解为多个小问题", "稍后重试"],
            execution_stats=ExecutionStats(
                total_time_ms=timeout_ms,
                validation_overhead_ms=0,
                retry_count=0,
                route_retry=0,
                answer_retry=0,
            ),
        )

        return {
            "answer": f"抱歉，查询处理超时（{timeout_ms}ms）。请尝试：\n1. 简化您的问题\n2. 分解为多个小问题\n3. 稍后重试",
            "citations": [],
            "quality_report": quality_report,
            "route_used": "timeout",
            "route_reason": f"timeout_after_{timeout_ms}ms",
            "skill_used": "none",
            "agent_class": "error",
            "execution_metadata": {
                "total_time_ms": timeout_ms,
                "validation_overhead_ms": 0,
                "route_retry": 0,
                "answer_retry": 0,
                "context_tracking_enabled": self.enable_context_tracking,
                "timeout": True,
            },
        }


