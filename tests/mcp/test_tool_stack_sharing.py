"""The pipeline and the API must reach the *same* governed tool stack.

`build_app_services()` used to construct its own `ApprovalStore`, `ToolRegistry`
and `MCPGateway`, and the RAG pipeline had none at all
(`CoreCapabilities.typed_tools` defaulted to `ToolAgentService()` with no
dependencies, so every tool call returned "tool system not initialized").

Wiring the two independently would not have been enough: `ToolRegistry` mints an
approval token into *its* `ApprovalStore`, and `POST
/api/v1/connectors/approvals/{token}` redeems it from whichever store the
FastAPI dependency hands out. Two stores means a token that can never be
redeemed, so sharing is a correctness requirement, not a performance one.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.mcp.contracts import ToolArgument, ToolCall
from app.mcp.runtime import DISABLE_CONNECTOR_TOOL_ID, get_tool_stack, reset_tool_stack
from app.orchestration.request import RequestActor

_ACTOR = RequestActor(user_id="u1", tenant_id="t1", role="viewer")


@pytest.fixture(autouse=True)
def _isolated_stack(monkeypatch):
    monkeypatch.setenv("API_SETTINGS_ENCRYPTION_KEY", "test-key-for-connector-credentials")
    # Connectors and credentials are persisted now, so building the stack writes
    # real rows -- point the app database at a temp file rather than the
    # developer's data/app.db. Deliberately not pytest's tmp_path: its basetemp
    # root needs directory permissions that are not available on every Windows
    # checkout (see tests/api/test_advanced_rag_roundtrip.py).
    root = Path(tempfile.mkdtemp(prefix="querymind-connectors-"))
    monkeypatch.setenv("APP_DB_PATH", str(root / "app.db"))
    get_settings.cache_clear()
    reset_tool_stack()
    try:
        yield
    finally:
        reset_tool_stack()
        get_settings.cache_clear()
        shutil.rmtree(root, ignore_errors=True)


def _call() -> ToolCall:
    return ToolCall(
        tool_id=DISABLE_CONNECTOR_TOOL_ID,
        arguments=(ToolArgument(name="connector_id", value="slack"),),
        execution_id="exec-1",
    )


def test_the_stack_is_built_once_per_process():
    assert get_tool_stack() is get_tool_stack()


def test_the_api_container_resolves_the_same_stack_it_does_not_build_one():
    from app.api.deps.runtime import build_app_services

    stack = get_tool_stack()
    services = build_app_services()

    assert services.approvals is stack.approvals
    assert services.tool_registry is stack.registry
    assert services.gateway is stack.gateway
    assert services.connectors is stack.connectors


@pytest.mark.asyncio
async def test_a_token_minted_by_a_tool_call_is_redeemable_through_the_api_store():
    """The whole point of sharing: the approval endpoint must find the token the
    registry minted, so `POST /connectors/approvals/{token}` can complete."""
    from app.api.deps.runtime import build_app_services

    stack = get_tool_stack()
    result = await stack.gateway.invoke(_call(), _ACTOR)

    assert result.status == "approval_required"
    assert result.approval_token

    # The store the FastAPI dependency hands out must know this token.
    api_store = build_app_services().approvals
    api_store.approve(result.approval_token, _ACTOR)  # raises if the token is unknown


@pytest.mark.asyncio
async def test_the_pipeline_tool_agent_reaches_the_same_gateway():
    """`ToolAgentService()` with no injected dependencies is what
    `CoreCapabilities` builds by default; it must not be inert."""
    from app.agents.tool.selector import ToolSelection
    from app.agents.tool.service import ToolAgentService
    from app.orchestration.request import OrchestrationRequest

    class _PicksDisable:
        async def select(self, question, conversation, catalog, *, observations=(), execution_id):
            del question, conversation, catalog, observations
            return ToolSelection(call=_call(), reason="test")

    results = await ToolAgentService(selector=_PicksDisable()).invoke_requested(
        OrchestrationRequest(question="disable connector slack", actor=_ACTOR),
        execution_id="exec-2",
    )

    # It reached the real registry: a `write` tool always demands approval first.
    assert len(results) == 1
    assert results[0].status == "approval_required"
    assert results[0].approval_token


@pytest.mark.asyncio
async def test_a_declined_selection_reports_a_reason_instead_of_silence():
    """Returning an empty tuple is what made a mis-routed request a silent
    no-op: an ordinary answer with no hint the action did not happen."""
    from app.agents.tool.selector import ToolSelection
    from app.agents.tool.service import SELECTOR_TOOL_ID, ToolAgentService
    from app.orchestration.request import OrchestrationRequest

    class _Declines:
        async def select(self, question, conversation, catalog, *, observations=(), execution_id):
            del question, conversation, catalog, observations, execution_id
            return ToolSelection(call=None, reason="no tool matches an enable request")

    results = await ToolAgentService(selector=_Declines()).invoke_requested(
        OrchestrationRequest(question="enable integration slack", actor=_ACTOR),
        execution_id="exec-3",
    )

    assert len(results) == 1
    assert results[0].tool_id == SELECTOR_TOOL_ID
    assert results[0].status == "skipped"
    assert "no tool matches an enable request" in results[0].summary


def test_constructing_the_tool_agent_does_not_build_the_stack():
    """CoreCapabilities constructs this by default_factory. Building eagerly
    would demand API_SETTINGS_ENCRYPTION_KEY of every test and script that
    touches capabilities."""
    from app.agents.tool.service import ToolAgentService

    reset_tool_stack()
    ToolAgentService()

    import app.mcp.runtime as runtime

    assert runtime._stack is None


def test_default_capabilities_still_share_the_compiled_engine():
    """A naive `RAGPipeline(tool_agent=…)` would set `_uses_default_capabilities`
    False and rebuild the LangGraph workflow per request (~20ms of synchronous
    CPU on the event loop). Resolving the stack inside the service keeps the
    default path on the shared engine."""
    from app.pipeline.profiles import PipelineProfile
    from app.pipeline.rag_pipeline import RAGPipeline

    assert RAGPipeline()._engine_for(PipelineProfile.ADVANCED) is RAGPipeline()._engine_for(PipelineProfile.ADVANCED)
