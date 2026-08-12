"""Structured MCP read-tool response contracts."""

from typing import get_type_hints

from app.mcp import server
from app.mcp.contracts import MCPAgentDescriptor, MCPConversationMessage, MCPRagResponse


def test_mcp_server_exposes_pydantic_contracts_instead_of_untyped_dictionaries() -> None:
    """MCP response boundaries must remain schema-governed as RAG evolves."""
    hints = get_type_hints(server.run_rag_query)

    assert hints["return"] is MCPRagResponse
    assert get_type_hints(server.list_rag_agents)["return"] == tuple[MCPAgentDescriptor, ...]
    assert all(isinstance(agent, MCPAgentDescriptor) for agent in server.list_rag_agents())

def test_mcp_conversation_contract_converts_to_the_pipeline_contract() -> None:
    """MCP input models must cross the server adapter without an untyped mapping fallback."""
    messages = server._conversation_messages((MCPConversationMessage(role="user", content="hello"),))

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "hello"
