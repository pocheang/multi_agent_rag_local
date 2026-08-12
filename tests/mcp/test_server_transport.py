"""Tests safe MCP transport defaults."""

import pytest

from app.mcp import server


def test_mcp_server_defaults_to_streamable_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaulting back to stdio would make the deployed Gateway unreachable."""
    transports: list[str] = []
    monkeypatch.delenv("QUERYMIND_MCP_TRANSPORT", raising=False)
    monkeypatch.setattr(server.mcp, "run", lambda *, transport: transports.append(transport))

    server.main()

    assert transports == ["streamable-http"]


def test_mcp_server_exposes_only_querymind_read_tools() -> None:
    """Published RAG tools must be clearly namespaced and remain read-only."""
    tool_names = set(server.mcp._tool_manager._tools)

    assert server.mcp.name == "querymind_mcp"
    assert tool_names == {
        "querymind_rag_list_agents",
        "querymind_rag_query_advanced",
        "querymind_rag_query_standard",
        "querymind_rag_query_strict_quality",
    }

def test_mcp_server_rejects_stdio_without_explicit_local_development_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allowing stdio in deployed mode would silently bypass the HTTP gateway requirement."""
    monkeypatch.setenv("QUERYMIND_MCP_TRANSPORT", "stdio")
    monkeypatch.delenv("QUERYMIND_MCP_LOCAL_DEV", raising=False)

    with pytest.raises(RuntimeError, match="local development"):
        server.main()
