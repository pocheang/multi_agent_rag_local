"""
Agent integration validator and health check utility.

This module provides utilities to validate agent functionality and integration.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AgentValidator:
    """Validates agent functionality and integration."""

    @staticmethod
    def validate_router_agent() -> dict[str, Any]:
        """Validate Router Agent functionality."""
        try:
            from app.agents.router_agent import decide_route, VALID_ROUTES, VALID_SKILLS

            # Test basic routing
            test_queries = [
                ("什么是Docker？", "vector"),
                ("A和B的关系是什么？", "graph"),
                ("比较A和B的特点", "hybrid"),
            ]

            results = []
            for query, expected_route in test_queries:
                try:
                    decision = decide_route(query, use_llm_intent=False)
                    results.append({
                        "query": query,
                        "route": decision.route,
                        "expected": expected_route,
                        "match": decision.route in VALID_ROUTES,
                        "skill": decision.skill,
                        "confidence": decision.confidence,
                    })
                except Exception as e:
                    results.append({
                        "query": query,
                        "error": str(e),
                        "match": False,
                    })

            return {
                "status": "ok",
                "agent": "router",
                "valid_routes": VALID_ROUTES,
                "valid_skills": VALID_SKILLS,
                "test_results": results,
            }

        except Exception as e:
            logger.exception("Router agent validation failed")
            return {
                "status": "error",
                "agent": "router",
                "error": str(e),
            }

    @staticmethod
    def validate_vector_rag_agent() -> dict[str, Any]:
        """Validate Vector RAG Agent functionality."""
        try:
            from app.agents.vector_rag_agent import run_vector_rag

            # Test basic retrieval
            test_query = "测试查询"
            result = run_vector_rag(test_query, retrieval_strategy="hybrid")

            return {
                "status": "ok",
                "agent": "vector_rag",
                "test_query": test_query,
                "has_context": bool(result.get("context")),
                "retrieved_count": result.get("retrieved_count", 0),
                "effective_hits": result.get("effective_hit_count", 0),
                "has_diagnostics": "retrieval_diagnostics" in result,
            }

        except Exception as e:
            logger.exception("Vector RAG agent validation failed")
            return {
                "status": "error",
                "agent": "vector_rag",
                "error": str(e),
            }

    @staticmethod
    def validate_graph_rag_agent() -> dict[str, Any]:
        """Validate Graph RAG Agent functionality."""
        try:
            from app.agents.graph_rag_agent import run_graph_rag

            # Test basic graph query
            test_query = "测试实体"
            result = run_graph_rag(test_query)

            return {
                "status": "ok" if not result.get("error") else "fallback",
                "agent": "graph_rag",
                "test_query": test_query,
                "has_context": bool(result.get("context")),
                "entities_count": len(result.get("entities", [])),
                "neighbors_count": len(result.get("neighbors", [])),
                "paths_count": len(result.get("paths", [])),
                "graph_signal_score": result.get("graph_signal_score", 0.0),
                "fallback_used": result.get("fallback_used", False),
            }

        except Exception as e:
            logger.exception("Graph RAG agent validation failed")
            return {
                "status": "error",
                "agent": "graph_rag",
                "error": str(e),
            }

    @staticmethod
    def validate_react_agent() -> dict[str, Any]:
        """Validate ReAct Agent functionality."""
        try:
            from app.agents.react_agent import ReActAgent

            # Test agent initialization
            agent = ReActAgent(max_iterations=2, use_reasoning=False)

            return {
                "status": "ok",
                "agent": "react",
                "max_iterations": agent.max_iterations,
                "use_reasoning": agent.use_reasoning,
                "note": "Full execution test requires actual query - skipped for quick validation",
            }

        except Exception as e:
            logger.exception("ReAct agent validation failed")
            return {
                "status": "error",
                "agent": "react",
                "error": str(e),
            }

    @staticmethod
    def validate_synthesis_agent() -> dict[str, Any]:
        """Validate Synthesis Agent functionality."""
        try:
            from app.agents.synthesis_agent import synthesize_answer

            # Test basic synthesis
            test_result = synthesize_answer(
                question="测试问题",
                skill_name="answer_with_citations",
                vector_context="测试上下文",
                use_reasoning=False,
            )

            return {
                "status": "ok",
                "agent": "synthesis",
                "has_answer": bool(test_result.get("answer")),
                "detected_language": test_result.get("detected_language"),
                "skill_used": test_result.get("skill_used"),
            }

        except Exception as e:
            logger.exception("Synthesis agent validation failed")
            return {
                "status": "error",
                "agent": "synthesis",
                "error": str(e),
            }

    @staticmethod
    def validate_enhanced_router_agent() -> dict[str, Any]:
        """Validate Enhanced Router Agent functionality."""
        try:
            from app.agents.enhanced_router_agent import EnhancedRouterAgent
            from app.core.models import get_chat_model

            # Test initialization
            llm_client = get_chat_model()
            agent = EnhancedRouterAgent(llm_client, enable_query_decomposition=False)

            return {
                "status": "ok",
                "agent": "enhanced_router",
                "query_decomposition_enabled": agent.enable_query_decomposition,
                "has_decomposer": agent.query_decomposer is not None,
            }

        except Exception as e:
            logger.exception("Enhanced Router agent validation failed")
            return {
                "status": "error",
                "agent": "enhanced_router",
                "error": str(e),
            }

    @staticmethod
    def validate_workflow() -> dict[str, Any]:
        """Validate LangGraph Workflow."""
        try:
            from app.graph.workflow import build_workflow

            # Test workflow building
            workflow = build_workflow()

            return {
                "status": "ok",
                "component": "workflow",
                "workflow_built": workflow is not None,
                "note": "Full workflow execution test requires actual query",
            }

        except Exception as e:
            logger.exception("Workflow validation failed")
            return {
                "status": "error",
                "component": "workflow",
                "error": str(e),
            }

    @classmethod
    def validate_all(cls) -> dict[str, Any]:
        """Run all agent validations."""
        results = {
            "router": cls.validate_router_agent(),
            "vector_rag": cls.validate_vector_rag_agent(),
            "graph_rag": cls.validate_graph_rag_agent(),
            "react": cls.validate_react_agent(),
            "synthesis": cls.validate_synthesis_agent(),
            "enhanced_router": cls.validate_enhanced_router_agent(),
            "workflow": cls.validate_workflow(),
        }

        # Calculate overall status
        statuses = [r.get("status") for r in results.values()]
        error_count = statuses.count("error")
        fallback_count = statuses.count("fallback")
        ok_count = statuses.count("ok")

        overall_status = "healthy"
        if error_count > 0:
            overall_status = "degraded" if ok_count > error_count else "unhealthy"
        elif fallback_count > 0:
            overall_status = "partially_healthy"

        return {
            "overall_status": overall_status,
            "summary": {
                "total": len(results),
                "ok": ok_count,
                "fallback": fallback_count,
                "error": error_count,
            },
            "details": results,
        }


def validate_agent_integration() -> dict[str, Any]:
    """
    Validate all agent integrations.

    Returns:
        Validation results dictionary
    """
    return AgentValidator.validate_all()


if __name__ == "__main__":
    # Run validation when executed directly
    import json

    logging.basicConfig(level=logging.INFO)
    results = validate_agent_integration()
    print(json.dumps(results, indent=2, ensure_ascii=False))
