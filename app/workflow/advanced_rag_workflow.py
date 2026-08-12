"""
End-to-end workflow for advanced RAG processing.
"""

import asyncio
import logging
from typing import Any

from app.agents.rag.enhanced_vector import EnhancedVectorRAGAgent
from app.agents.rag.graph import run_graph_rag
from app.agents.rag.web import run_web_research
from app.agents.synthesizer.generation import synthesize_answer
from app.agents.tool.react import run_react_agent
from app.services.models.runtime import get_chat_model
from app.domain.advanced_rag import AdvancedRAGResult, SubQueryResult
from app.agents.router.compatibility import DecompositionRoutingAdapter, RoutingService

logger = logging.getLogger(__name__)
_NO_ANSWER = "I don't have enough information to answer this question."


class AdvancedRAGWorkflow:
    """Workflow for processing queries with advanced RAG techniques."""

    def __init__(
        self,
        enable_decomposition: bool = False,
        enable_self_rag: bool = False,
    ):
        """
        Initialize advanced RAG workflow.

        Args:
            enable_decomposition: Enable query decomposition
            enable_self_rag: Enable Self-RAG evaluation
        """
        self.enable_decomposition = enable_decomposition
        self.enable_self_rag = enable_self_rag

        self.llm_client = get_chat_model()
        # Preserve the legacy attribute name while using the canonical routing
        # compatibility owner.
        self.router_agent = DecompositionRoutingAdapter(
            self.llm_client,
            enable_query_decomposition=enable_decomposition,
            routing_service=RoutingService(),
        )
        self.vector_rag_agent = EnhancedVectorRAGAgent(
            self.llm_client,
            enable_self_rag=enable_self_rag,
        )

        logger.info(
            "Advanced RAG workflow initialized: decomposition=%s, self_rag=%s",
            enable_decomposition,
            enable_self_rag,
        )

    async def process_query(
        self,
        query: str,
        allowed_sources: list[str] | None = None,
        retrieval_strategy: str | None = None,
    ) -> AdvancedRAGResult:
        """
        Process query with advanced RAG techniques.

        Args:
            query: User query
            allowed_sources: Optional list of allowed sources
            retrieval_strategy: Optional retrieval strategy

        Returns:
            AdvancedRAGResult with complete processing results
        """
        metadata = {
            "decomposition_enabled": self.enable_decomposition,
            "self_rag_enabled": self.enable_self_rag,
        }

        routing_result = await self.router_agent.route_with_decomposition(query)
        decomposed_query = routing_result.get("decomposed_query")
        route_decisions = routing_result.get("route_decisions", [])

        metadata["route_decisions"] = [
            {
                "query": rd["query"],
                "route": rd["decision"].route,
                "skill": rd["decision"].skill,
                "agent_class": rd["decision"].agent_class,
            }
            for rd in route_decisions
        ]

        sub_query_results = []
        for route_decision in route_decisions:
            sub_query_results.append(
                await self._process_route_decision(
                    sub_query=route_decision["query"],
                    decision=route_decision["decision"],
                    allowed_sources=allowed_sources,
                    retrieval_strategy=retrieval_strategy,
                )
            )

        if len(sub_query_results) > 1:
            final_answer = await self._synthesize_answers(query, sub_query_results)
        else:
            final_answer = sub_query_results[0].answer if sub_query_results else "No answer generated."

        answer_quality = None
        if self.enable_self_rag:
            all_citations = []
            for sub_result in sub_query_results:
                all_citations.extend(
                    [
                        {
                            "source": doc["source"],
                            "content": doc["content"],
                            "metadata": doc.get("metadata", {}),
                        }
                        for doc in sub_result.documents
                    ]
                )

            quality_dict = await self.vector_rag_agent.evaluate_answer_quality(
                query,
                final_answer,
                all_citations,
            )
            if quality_dict:
                from app.domain.advanced_rag import AnswerQuality

                answer_quality = AnswerQuality(**quality_dict)

        return AdvancedRAGResult(
            query=query,
            decomposed_query=decomposed_query,
            sub_query_results=sub_query_results,
            final_answer=final_answer,
            answer_quality=answer_quality,
            metadata=metadata,
        )

    @staticmethod
    def _citation_documents(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "source": c.get("source", "unknown"),
                "content": c.get("content", ""),
                "metadata": c.get("metadata", {}),
            }
            for c in citations
        ]

    @staticmethod
    def _graph_documents(graph_result: dict[str, Any]) -> list[dict[str, Any]]:
        context = str(graph_result.get("context", "") or "").strip()
        if not context:
            return []
        return [
            {
                "source": "graph_context",
                "content": context,
                "metadata": {
                    "entities": list(graph_result.get("entities") or []),
                    "neighbors_count": len(graph_result.get("neighbors") or []),
                    "paths_count": len(graph_result.get("paths") or []),
                },
            }
        ]

    async def _synthesize_from_context(
        self,
        *,
        question: str,
        skill_name: str,
        vector_context: str = "",
        graph_context: str = "",
        web_context: str = "",
    ) -> str:
        if not any(str(block or "").strip() for block in (vector_context, graph_context, web_context)):
            return _NO_ANSWER
        result = await asyncio.to_thread(
            synthesize_answer,
            question=question,
            skill_name=skill_name,
            vector_context=vector_context,
            graph_context=graph_context,
            web_context=web_context,
        )
        if isinstance(result, dict):
            answer = str(result.get("answer", "") or "").strip()
        else:
            answer = str(result or "").strip()
        return answer or _NO_ANSWER

    async def _process_route_decision(
        self,
        *,
        sub_query: str,
        decision,
        allowed_sources: list[str] | None,
        retrieval_strategy: str | None,
    ) -> SubQueryResult:
        route = str(getattr(decision, "route", "vector") or "vector").strip().lower()
        skill = str(getattr(decision, "skill", "answer_with_citations") or "answer_with_citations")
        agent_class = str(getattr(decision, "agent_class", "general") or "general")

        if route == "graph":
            graph_result = await asyncio.to_thread(
                run_graph_rag,
                sub_query,
                allowed_sources=allowed_sources,
                agent_class=agent_class,
            )
            documents = self._graph_documents(graph_result)
            answer = await self._synthesize_from_context(
                question=sub_query,
                skill_name=skill,
                graph_context=str(graph_result.get("context", "") or ""),
            )
            return SubQueryResult(
                sub_query=sub_query,
                documents=documents,
                answer=answer,
                relevance_scores=None,
            )

        if route == "hybrid":
            retrieval_result = await self.vector_rag_agent.retrieve_with_evaluation(
                sub_query,
                allowed_sources=allowed_sources,
                retrieval_strategy=retrieval_strategy,
                agent_class=agent_class,
            )
            citations = retrieval_result.get("filtered_citations") or retrieval_result.get("citations") or []
            vector_context = str(retrieval_result.get("filtered_context") or retrieval_result.get("context") or "")
            retrieved_docs = [
                {
                    "content": doc.get("content", ""),
                    "metadata": doc.get("metadata", {}),
                }
                for doc in self._citation_documents(citations)
            ]
            graph_result = await asyncio.to_thread(
                run_graph_rag,
                sub_query,
                allowed_sources=allowed_sources,
                agent_class=agent_class,
                retrieved_docs=retrieved_docs or None,
            )
            documents = self._citation_documents(citations) + self._graph_documents(graph_result)
            answer = await self._synthesize_from_context(
                question=sub_query,
                skill_name=skill,
                vector_context=vector_context,
                graph_context=str(graph_result.get("context", "") or ""),
            )
            return SubQueryResult(
                sub_query=sub_query,
                documents=documents,
                answer=answer,
                relevance_scores=retrieval_result.get("relevance_scores"),
            )

        if route == "react":
            react_result = await asyncio.to_thread(
                run_react_agent,
                question=sub_query,
                allowed_sources=allowed_sources,
                retrieval_strategy=retrieval_strategy,
                agent_class=agent_class,
            )
            vector_docs = self._citation_documents(
                list((react_result.get("vector_result", {}) or {}).get("citations") or [])
            )
            web_docs = self._citation_documents(list((react_result.get("web_result", {}) or {}).get("citations") or []))
            graph_docs = self._graph_documents(react_result.get("graph_result") or {})
            return SubQueryResult(
                sub_query=sub_query,
                documents=vector_docs + web_docs + graph_docs,
                answer=str(react_result.get("answer", "") or _NO_ANSWER),
                relevance_scores=None,
            )

        if route == "web":
            web_result = await asyncio.to_thread(run_web_research, sub_query)
            citations = list(web_result.get("citations") or [])
            answer = await self._synthesize_from_context(
                question=sub_query,
                skill_name=skill,
                web_context=str(web_result.get("context", "") or ""),
            )
            return SubQueryResult(
                sub_query=sub_query,
                documents=self._citation_documents(citations),
                answer=answer,
                relevance_scores=None,
            )

        retrieval_result = await self.vector_rag_agent.retrieve_with_evaluation(
            sub_query,
            allowed_sources=allowed_sources,
            retrieval_strategy=retrieval_strategy,
            agent_class=agent_class,
        )
        citations = retrieval_result.get("filtered_citations") or retrieval_result.get("citations") or []
        vector_context = str(retrieval_result.get("filtered_context") or retrieval_result.get("context") or "")
        answer = await self._synthesize_from_context(
            question=sub_query,
            skill_name=skill,
            vector_context=vector_context,
        )
        return SubQueryResult(
            sub_query=sub_query,
            documents=self._citation_documents(citations),
            answer=answer,
            relevance_scores=retrieval_result.get("relevance_scores"),
        )

    async def _generate_answer(self, query: str, context: str) -> str:
        """
        Generate answer from context.

        Args:
            query: User query
            context: Retrieved context

        Returns:
            Generated answer
        """
        if not context or not context.strip():
            return _NO_ANSWER

        prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {query}

Answer:"""

        try:
            response = await self.llm_client.ainvoke(prompt)
            answer = response.content if hasattr(response, "content") else str(response)
            return answer.strip()
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return f"Error generating answer: {str(e)}"

    async def _synthesize_answers(
        self,
        query: str,
        sub_results: list[SubQueryResult],
    ) -> str:
        """
        Synthesize final answer from sub-query results.

        Args:
            query: Original query
            sub_results: Results from sub-queries

        Returns:
            Synthesized final answer
        """
        combined = "\n\n".join([f"Sub-question: {sr.sub_query}\nAnswer: {sr.answer}" for sr in sub_results])

        prompt = f"""Synthesize a comprehensive answer to the original question based on the following sub-answers.

Original Question: {query}

Sub-answers:
{combined}

Synthesized Answer:"""

        try:
            response = await self.llm_client.ainvoke(prompt)
            answer = response.content if hasattr(response, "content") else str(response)
            return answer.strip()
        except Exception as e:
            logger.error(f"Error synthesizing answer: {e}")
            return "\n\n".join([sr.answer for sr in sub_results])
