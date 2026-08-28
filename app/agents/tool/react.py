"""
ReAct Agent - Reasoning and Acting agent with iterative tool use.

This agent implements the ReAct pattern (Reasoning + Acting):
1. Think: Analyze the current situation and decide next action
2. Act: Execute a tool (vector search, graph query, web search)
3. Observe: Review the results
4. Repeat: Continue until sufficient information is gathered

The agent reuses existing agents as tools without modifying them.
"""

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from app.agents.rag.graph import run_graph_rag
from app.agents.rag.vector import run_vector_rag
from app.agents.rag.web import run_web_research
from app.agents.synthesizer.generation import synthesize_answer
from app.core.models import get_chat_model, get_reasoning_model
from app.prompts import CANONICAL_REACT_SYSTEM_PROMPT as REACT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _empty_contexts() -> dict[str, str]:
    return {"vector": "", "graph": "", "web": ""}


def _empty_tool_results() -> dict[str, dict[str, Any]]:
    return {
        "vector": {
            "context": "",
            "citations": [],
            "retrieved_count": 0,
            "effective_hit_count": 0,
        },
        "graph": {
            "context": "",
            "entities": [],
            "neighbors": [],
            "paths": [],
        },
        "web": {
            "context": "",
            "citations": [],
            "used": False,
        },
    }


class ReActThought(BaseModel):
    """ReAct thought structure."""

    thought: str
    action: str
    action_input: str
    reasoning: str


class ReActObservation(BaseModel):
    """ReAct observation structure."""

    tool: str
    result: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReActStep(BaseModel):
    """Single ReAct iteration step."""

    iteration: int
    thought: ReActThought
    observation: ReActObservation | None = None


class ReActAgent:
    """ReAct agent that orchestrates multiple tools."""

    def __init__(
        self,
        max_iterations: int = 5,
        use_reasoning: bool = False,
    ):
        """
        Initialize ReAct agent.

        Args:
            max_iterations: Maximum number of think-act-observe cycles
            use_reasoning: Whether to use reasoning model for thinking
        """
        self.max_iterations = max_iterations
        self.use_reasoning = use_reasoning
        self.history: list[ReActStep] = []
        self.accumulated_context = _empty_contexts()
        self.tool_results = _empty_tool_results()
        self.agent_class: str | None = None

    @staticmethod
    def _append_context(existing: str, new: str) -> str:
        """Append non-empty context blocks without leading blank lines."""
        existing_text = str(existing or "").strip()
        new_text = str(new or "").strip()
        if not existing_text:
            return new_text
        if not new_text:
            return existing_text
        return f"{existing_text}\n\n{new_text}"

    def _merge_vector_result(self, result: dict[str, Any]) -> None:
        merged = self.tool_results["vector"]
        merged["context"] = self._append_context(merged.get("context", ""), result.get("context", ""))
        merged["citations"].extend(list(result.get("citations") or []))
        merged["retrieved_count"] += int(result.get("retrieved_count", 0) or 0)
        merged["effective_hit_count"] += int(result.get("effective_hit_count", 0) or 0)
        if "retrieval_diagnostics" in result:
            merged["retrieval_diagnostics"] = result.get("retrieval_diagnostics") or {}

    def _merge_graph_result(self, result: dict[str, Any]) -> None:
        merged = self.tool_results["graph"]
        merged["context"] = self._append_context(merged.get("context", ""), result.get("context", ""))
        merged["entities"].extend(list(result.get("entities") or []))
        merged["neighbors"].extend(list(result.get("neighbors") or []))
        merged["paths"].extend(list(result.get("paths") or []))
        merged["graph_signal_score"] = max(
            float(merged.get("graph_signal_score", 0.0) or 0.0),
            float(result.get("graph_signal_score", 0.0) or 0.0),
        )
        if result.get("error"):
            merged["error"] = result["error"]

    def _merge_web_result(self, result: dict[str, Any]) -> None:
        merged = self.tool_results["web"]
        merged["context"] = self._append_context(merged.get("context", ""), result.get("context", ""))
        merged["citations"].extend(list(result.get("citations") or []))
        merged["used"] = bool(merged.get("used")) or bool(result.get("used"))
        if result.get("error"):
            merged["error"] = result["error"]

    def run(
        self,
        question: str,
        memory_context: str = "",
        allowed_sources: list[str] | None = None,
        force_language: str = "",
        session_id: str = "",
        agent_class: str | None = None,
    ) -> dict[str, Any]:
        """
        Run ReAct cycle for the given question.

        Args:
            question: User question
            memory_context: Session memory context
            allowed_sources: Allowed document sources

        Returns:
            Dictionary with answer and metadata
        """
        logger.info(f"Starting ReAct cycle for question: {question[:100]}...")

        self.history = []
        self.accumulated_context = _empty_contexts()
        self.tool_results = _empty_tool_results()
        self.agent_class = agent_class
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"ReAct iteration {iteration}/{self.max_iterations}")

            # Think: Decide next action
            thought = self._think(question, memory_context)

            if not thought:
                logger.warning("Failed to generate valid thought, finishing")
                break

            # Create step record
            step = ReActStep(iteration=iteration, thought=thought)

            # Check if we should finish
            if thought.action == "finish":
                logger.info("ReAct decided to finish")
                self.history.append(step)
                break

            # Act: Execute the chosen tool
            observation = self._act(
                thought.action,
                thought.action_input,
                allowed_sources,
            )

            step.observation = observation
            self.history.append(step)

            logger.info(f"Action: {thought.action}, Result length: {len(observation.result)}")

        # Synthesize final answer
        final_answer = self._synthesize_final_answer(
            question=question,
            memory_context=memory_context,
            force_language=force_language,
            session_id=session_id,
        )

        return {
            "answer": final_answer["answer"],
            "detected_language": final_answer.get("detected_language", "zh"),
            "react_history": [step.model_dump() for step in self.history],
            "iterations_used": len(self.history),
            "contexts": dict(self.accumulated_context),
            "vector_result": self.tool_results["vector"],
            "graph_result": self.tool_results["graph"],
            "web_result": self.tool_results["web"],
        }

    def _think(self, question: str, memory_context: str) -> ReActThought | None:
        """
        Generate next thought and action.

        Args:
            question: Original question
            memory_context: Memory context

        Returns:
            ReActThought or None if thinking fails
        """
        # Build prompt with history
        history_text = self._format_history()

        prompt = f"""问题: {question}

记忆上下文: {memory_context or "无"}

已执行的步骤:
{history_text or "无"}

请分析当前状态，决定下一步行动。"""

        try:
            model = get_reasoning_model() if self.use_reasoning else get_chat_model()
            response = model.invoke([("system", REACT_SYSTEM_PROMPT), ("human", prompt)])

            content = response.content if hasattr(response, "content") else str(response)
            thought_data = self._extract_json(content)

            if not thought_data:
                logger.warning("Failed to extract JSON from thought")
                return None

            return ReActThought(
                thought=thought_data.get("thought", ""),
                action=thought_data.get("action", "finish"),
                action_input=thought_data.get("action_input", ""),
                reasoning=thought_data.get("reasoning", ""),
            )

        except Exception as e:
            logger.exception(f"Error generating thought: {e}")
            return None

    def _act(
        self,
        action: str,
        action_input: str,
        allowed_sources: list[str] | None,
    ) -> ReActObservation:
        """
        Execute the chosen action.

        Args:
            action: Tool name
            action_input: Input for the tool
            allowed_sources: Allowed sources for vector search

        Returns:
            ReActObservation with results
        """
        tool_map = {
            "vector_search": self._tool_vector_search,
            "graph_query": self._tool_graph_query,
            "web_search": self._tool_web_search,
        }

        if action not in tool_map:
            return ReActObservation(
                tool=action,
                result=f"Unknown tool: {action}",
                metadata={"error": "unknown_tool"},
            )

        try:
            result, metadata = tool_map[action](
                action_input,
                allowed_sources,
            )
            return ReActObservation(
                tool=action,
                result=result,
                metadata=metadata,
            )
        except Exception as e:
            logger.exception(f"Error executing {action}: {e}")
            return ReActObservation(
                tool=action,
                result=f"Tool execution failed: {str(e)}",
                metadata={"error": str(e)},
            )

    def _tool_vector_search(
        self,
        query: str,
        allowed_sources: list[str] | None,
    ) -> tuple[str, dict[str, Any]]:
        """Execute vector search tool (reuses vector_rag_agent)."""
        kwargs: dict[str, Any] = {
            "question": query,
            "allowed_sources": allowed_sources,
        }
        if self.agent_class:
            kwargs["agent_class"] = self.agent_class
        result = run_vector_rag(**kwargs)
        self._merge_vector_result(result)
        self.accumulated_context["vector"] = self.tool_results["vector"].get("context", "")

        summary = (
            f"Found {result.get('retrieved_count', 0)} vector hits, "
            f"with {result.get('effective_hit_count', 0)} effective hits."
        )

        if result.get("citations"):
            sources = [c.get("source", "unknown") for c in result["citations"][:3]]
            summary += f"\nTop sources: {', '.join(sources)}"

        return summary, {
            "retrieved_count": result.get("retrieved_count", 0),
            "effective_count": result.get("effective_hit_count", 0),
            "citations_count": len(result.get("citations", [])),
        }

    def _tool_graph_query(
        self,
        query: str,
        allowed_sources: list[str] | None,
    ) -> tuple[str, dict[str, Any]]:
        """Execute graph query tool (reuses graph_rag_agent)."""
        kwargs: dict[str, Any] = {"allowed_sources": allowed_sources}
        if self.agent_class:
            kwargs["agent_class"] = self.agent_class
        result = run_graph_rag(query, **kwargs)
        self._merge_graph_result(result)
        self.accumulated_context["graph"] = self.tool_results["graph"].get("context", "")

        entities = list(result.get("entities") or [])
        relationships = list(result.get("relationships") or [])
        neighbors = list(result.get("neighbors") or [])
        paths = list(result.get("paths") or [])
        relationship_count = len(relationships) if relationships else len(neighbors) + len(paths)

        summary = f"Found {len(entities)} entities and {relationship_count} graph relationships."

        if entities:
            entity_names = [self._entity_name(e) for e in entities[:5]]
            summary += f"\nEntities: {', '.join(entity_names)}"

        return summary, {
            "entities_count": len(entities),
            "relationships_count": relationship_count,
        }

    def _tool_web_search(
        self,
        query: str,
        allowed_sources: list[str] | None,
    ) -> tuple[str, dict[str, Any]]:
        """Execute web search tool (reuses web_research_agent)."""
        result = run_web_research(query)
        self._merge_web_result(result)
        self.accumulated_context["web"] = self.tool_results["web"].get("context", "")

        citations = list(result.get("citations") or [])
        summary = f"Found {len(citations)} web results."

        if citations:
            sources = [c.get("source", "unknown") for c in citations[:3]]
            summary += f"\nSources: {', '.join(sources)}"

        return summary, {
            "citations_count": len(citations),
            "used": result.get("used", False),
        }

    @staticmethod
    def _entity_name(entity: Any) -> str:
        if isinstance(entity, dict):
            return str(entity.get("name") or entity.get("entity") or "unknown")
        return str(entity or "unknown")

    def _format_history(self) -> str:
        """Format history for prompt."""
        if not self.history:
            return ""

        lines = []
        for step in self.history:
            lines.append(f"\n第{step.iteration}轮:")
            lines.append(f"  思考: {step.thought.thought}")
            lines.append(f"  行动: {step.thought.action}({step.thought.action_input})")
            lines.append(f"  推理: {step.thought.reasoning}")

            if step.observation:
                lines.append(f"  观察: {step.observation.result}")

        return "\n".join(lines)

    def _synthesize_final_answer(
        self,
        question: str,
        memory_context: str,
        force_language: str,
        session_id: str,
    ) -> dict[str, Any]:
        """
        Synthesize final answer using accumulated context.

        Args:
            question: Original question
            memory_context: Memory context

        Returns:
            Dictionary with answer and metadata
        """
        return synthesize_answer(
            question=question,
            skill_name="react_agent",
            memory_context=memory_context,
            vector_context=self.accumulated_context["vector"],
            graph_context=self.accumulated_context["graph"],
            web_context=self.accumulated_context["web"],
            use_reasoning=self.use_reasoning,
            force_language=force_language,
            session_id=session_id,
        )

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extract JSON from LLM response."""
        text = str(text or "").strip()

        # Try to find JSON in markdown code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON directly
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to extract JSON from response")
        return {}


ReactAgent = ReActAgent


__all__ = [
    "ReActThought",
    "ReActObservation",
    "ReActStep",
    "REACT_SYSTEM_PROMPT",
    "ReActAgent",
    "ReactAgent",
    "run_react_agent",
]


def run_react_agent(
    question: str,
    memory_context: str = "",
    allowed_sources: list[str] | None = None,
    use_reasoning: bool = False,
    max_iterations: int = 5,
    force_language: str = "",
    session_id: str = "",
    agent_class: str | None = None,
) -> dict[str, Any]:
    """
    Run ReAct agent (convenience function).

    Args:
        question: User question
        memory_context: Session memory context
        allowed_sources: Allowed document sources
        use_reasoning: Use reasoning model
        max_iterations: Maximum iterations

    Returns:
        Dictionary with answer and metadata
    """
    agent = ReActAgent(
        max_iterations=max_iterations,
        use_reasoning=use_reasoning,
    )

    return agent.run(
        question=question,
        memory_context=memory_context,
        allowed_sources=allowed_sources,
        force_language=force_language,
        session_id=session_id,
        agent_class=agent_class,
    )
