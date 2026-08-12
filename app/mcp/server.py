"""Expose QueryMind RAG profiles through the Model Context Protocol (MCP)."""

from __future__ import annotations

import os
from collections.abc import Sequence

from mcp.server.fastmcp import FastMCP

from app.mcp.contracts import (
    MCPAgentDescriptor,
    MCPCitation,
    MCPConversationMessage,
    MCPDegradationEvent,
    MCPRagResponse,
    MCPRoute,
)
from app.pipeline.contracts import ConversationMessage, PipelineRequest, PipelineResult, SourceScope
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline

AGENT_CATALOG: tuple[MCPAgentDescriptor, ...] = (
    MCPAgentDescriptor(name="router", purpose="Select the typed retrieval route."),
    MCPAgentDescriptor(name="planner", purpose="Build bounded multi-step retrieval plans."),
    MCPAgentDescriptor(name="retriever", purpose="Collect attributable evidence."),
    MCPAgentDescriptor(name="tool_runner", purpose="Run governed explicit tools."),
    MCPAgentDescriptor(name="finalizer", purpose="Ground, sanitize, validate, and score answers."),
)

mcp = FastMCP(
    "querymind_mcp",
    instructions=(
        "Use a profile-specific query tool to ask the local knowledge base. "
        "Every query is executed by the existing QueryMind RAGPipeline."
    ),
)


def _conversation_messages(
    conversation: Sequence[MCPConversationMessage] | None,
) -> tuple[ConversationMessage, ...]:
    """Convert MCP input into the immutable pipeline conversation contract."""
    if not conversation:
        return ()
    return tuple(ConversationMessage(role=message.role, content=message.content) for message in conversation)


def _source_scope(allowed_sources: Sequence[str] | None, agent_class_hint: str | None) -> SourceScope:
    normalized_sources = None
    if allowed_sources is not None:
        normalized_sources = frozenset(source.strip() for source in allowed_sources if source and source.strip())
    return SourceScope(
        allowed_sources=normalized_sources,
        agent_class_hint=agent_class_hint.strip() if agent_class_hint else None,
    )


def _serialize_result(result: PipelineResult) -> MCPRagResponse:
    """Return a stable, schema-governed MCP response without compatibility payloads."""
    return MCPRagResponse(
        answer=result.answer,
        route=MCPRoute.model_validate(result.route, from_attributes=True),
        citations=tuple(MCPCitation.model_validate(citation, from_attributes=True) for citation in result.citations),
        quality_report=result.quality_report,
        degradation_events=tuple(
            MCPDegradationEvent.model_validate(event, from_attributes=True) for event in result.degradation_events
        ),
    )


async def run_rag_query(
    *,
    question: str,
    profile: PipelineProfile,
    allowed_sources: Sequence[str] | None = None,
    agent_class_hint: str | None = None,
    retrieval_strategy: str | None = None,
    conversation: Sequence[MCPConversationMessage] | None = None,
    use_reasoning: bool = False,
    use_web_fallback: bool = False,
    enable_decomposition: bool = False,
    enable_self_rag: bool = False,
    force_language: str = "",
    pipeline: RAGPipeline | None = None,
) -> MCPRagResponse:
    """Execute a public RAG profile and return its normalized result for MCP."""
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be blank")

    request = PipelineRequest(
        question=normalized_question,
        profile=profile,
        conversation=_conversation_messages(conversation),
        source_scope=_source_scope(allowed_sources, agent_class_hint),
        retrieval_strategy=retrieval_strategy,
        use_reasoning=use_reasoning,
        use_web_fallback=use_web_fallback,
        enable_decomposition=enable_decomposition,
        enable_self_rag=enable_self_rag,
        force_language=force_language,
    )
    result = await (pipeline or RAGPipeline()).execute(request)
    return _serialize_result(result)


@mcp.tool(name="querymind_rag_list_agents")
def list_rag_agents() -> tuple[MCPAgentDescriptor, ...]:
    """List QueryMind's five stable, pipeline-facing capabilities."""
    return AGENT_CATALOG


@mcp.tool(name="querymind_rag_query_standard")
async def query_standard_rag(
    question: str,
    allowed_sources: list[str] | None = None,
    agent_class_hint: str | None = None,
    retrieval_strategy: str | None = None,
    conversation: tuple[MCPConversationMessage, ...] = (),
    use_reasoning: bool = False,
    use_web_fallback: bool = False,
    force_language: str = "",
) -> MCPRagResponse:
    """Query the standard RAG profile with optional source and reasoning controls."""
    return await run_rag_query(
        question=question,
        profile=PipelineProfile.STANDARD,
        allowed_sources=allowed_sources,
        agent_class_hint=agent_class_hint,
        retrieval_strategy=retrieval_strategy,
        conversation=conversation,
        use_reasoning=use_reasoning,
        use_web_fallback=use_web_fallback,
        force_language=force_language,
    )


@mcp.tool(name="querymind_rag_query_strict_quality")
async def query_strict_quality_rag(
    question: str,
    allowed_sources: list[str] | None = None,
    agent_class_hint: str | None = None,
    retrieval_strategy: str | None = None,
    conversation: tuple[MCPConversationMessage, ...] = (),
) -> MCPRagResponse:
    """Query the strict-quality profile with route, retrieval, and answer validation."""
    return await run_rag_query(
        question=question,
        profile=PipelineProfile.STRICT_QUALITY,
        allowed_sources=allowed_sources,
        agent_class_hint=agent_class_hint,
        retrieval_strategy=retrieval_strategy,
        conversation=conversation,
    )


@mcp.tool(name="querymind_rag_query_advanced")
async def query_advanced_rag(
    question: str,
    allowed_sources: list[str] | None = None,
    retrieval_strategy: str | None = None,
    enable_decomposition: bool = False,
    enable_self_rag: bool = False,
) -> MCPRagResponse:
    """Query the advanced profile; decomposition and Self-RAG are explicit opt-ins."""
    return await run_rag_query(
        question=question,
        profile=PipelineProfile.ADVANCED,
        allowed_sources=allowed_sources,
        retrieval_strategy=retrieval_strategy,
        enable_decomposition=enable_decomposition,
        enable_self_rag=enable_self_rag,
    )


def main() -> None:
    """Run Streamable HTTP in deployed mode and stdio only for local development."""
    transport = os.getenv("QUERYMIND_MCP_TRANSPORT", "streamable-http").strip().lower()
    if transport not in {"streamable-http", "stdio"}:
        raise ValueError(f"unsupported MCP transport: {transport}")
    if transport == "stdio" and os.getenv("QUERYMIND_MCP_LOCAL_DEV") != "1":
        raise RuntimeError("stdio transport is allowed only for local development")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
