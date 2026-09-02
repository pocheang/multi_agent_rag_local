"""The approve-then-resume cycle, end to end.

Before this it was broken in three independent places: the frontend approved a
token and then only cleared its panel, `OrchestrationRequest` had no field to
carry a token back, and `_call_fingerprint` included `execution_id` -- so even a
client that did resend could not match the approved call, because every chat
turn is a new execution.

Resume is **replay**, not checkpoint restore: the run re-executes from the top
and the tool stage replays the approved call. That is deliberate. Re-running
means `privacy_permission` re-resolves the caller's access scope instead of
restoring a scope captured before the pause -- permissions can change while a
human is looking at a confirmation dialog, and replaying a stale scope would be
a privilege bug that a checkpoint restore would have introduced silently.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from app.agents.tool.selector import ToolSelection
from app.agents.tool.service import SELECTOR_TOOL_ID, ToolAgentService
from app.core.config import get_settings
from app.mcp.approvals import ApprovalStore
from app.mcp.contracts import ToolArgument, ToolCall
from app.mcp.runtime import DISABLE_CONNECTOR_TOOL_ID, get_tool_stack, reset_tool_stack
from app.orchestration.request import OrchestrationRequest, RequestActor

_ACTOR = RequestActor(user_id="alice", tenant_id="acme", role="viewer")
_OTHER = RequestActor(user_id="mallory", tenant_id="acme", role="viewer")


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


def _picks_disable():
    class _Selector:
        async def select(self, question, conversation, catalog, *, observations=(), execution_id):
            del question, conversation, catalog, observations
            return ToolSelection(
                call=ToolCall(
                    tool_id=DISABLE_CONNECTOR_TOOL_ID,
                    arguments=(ToolArgument(name="connector_id", value="slack"),),
                    execution_id=execution_id,
                ),
                reason="user asked",
            )

    return _Selector()


def _request(**overrides) -> OrchestrationRequest:
    return OrchestrationRequest(**{"question": "disable connector slack", "actor": _ACTOR, **overrides})


@pytest.mark.asyncio
async def test_the_full_cycle_reaches_the_executor():
    stack = get_tool_stack()
    agent = ToolAgentService(selector=_picks_disable())

    first = (await agent.invoke_requested(_request(), execution_id="run-1"))[0]
    assert first.status == "approval_required"

    stack.approvals.approve(first.approval_token, _ACTOR)

    # A *different* execution id, as every real second turn would have.
    resumed = (await agent.invoke_requested(_request(approval_token=first.approval_token), execution_id="run-2"))[0]

    # It reached the registered executor: alice owns no such connector, so the
    # executor -- not the approval gate -- is what refuses.
    assert resumed.status == "failed"
    assert "owned connector not found" in resumed.summary


@pytest.mark.asyncio
async def test_resume_replays_the_approved_call_not_a_fresh_selection():
    """A model re-reading the same question is not obliged to choose the same
    call. The approval authorized one action; resume must run that one."""

    class _WouldPickSomethingElse:
        called = False

        async def select(self, *args, **kwargs):
            type(self).called = True
            raise AssertionError("resume must not consult the selector")

    stack = get_tool_stack()
    first = (await ToolAgentService(selector=_picks_disable()).invoke_requested(_request(), execution_id="run-1"))[0]
    stack.approvals.approve(first.approval_token, _ACTOR)

    await ToolAgentService(selector=_WouldPickSomethingElse()).invoke_requested(
        _request(question="something completely different", approval_token=first.approval_token),
        execution_id="run-2",
    )

    assert _WouldPickSomethingElse.called is False


@pytest.mark.asyncio
async def test_an_unapproved_token_does_not_execute():
    stack = get_tool_stack()
    first = (await ToolAgentService(selector=_picks_disable()).invoke_requested(_request(), execution_id="run-1"))[0]
    assert stack  # token exists but was never approved

    resumed = (
        await ToolAgentService(selector=_picks_disable()).invoke_requested(
            _request(approval_token=first.approval_token), execution_id="run-2"
        )
    )[0]

    assert resumed.status == "failed"
    assert resumed.tool_id == SELECTOR_TOOL_ID
    assert "no longer valid" in resumed.summary


@pytest.mark.asyncio
async def test_a_token_is_useless_to_a_different_actor():
    stack = get_tool_stack()
    first = (await ToolAgentService(selector=_picks_disable()).invoke_requested(_request(), execution_id="run-1"))[0]
    stack.approvals.approve(first.approval_token, _ACTOR)

    stolen = OrchestrationRequest(question="disable connector slack", actor=_OTHER, approval_token=first.approval_token)
    resumed = (await ToolAgentService(selector=_picks_disable()).invoke_requested(stolen, execution_id="run-2"))[0]

    assert resumed.status == "failed"
    assert "no longer valid" in resumed.summary


@pytest.mark.asyncio
async def test_a_token_is_single_use():
    stack = get_tool_stack()
    agent = ToolAgentService(selector=_picks_disable())
    first = (await agent.invoke_requested(_request(), execution_id="run-1"))[0]
    stack.approvals.approve(first.approval_token, _ACTOR)

    await agent.invoke_requested(_request(approval_token=first.approval_token), execution_id="run-2")
    replayed = (await agent.invoke_requested(_request(approval_token=first.approval_token), execution_id="run-3"))[0]

    assert replayed.status == "failed"
    assert "no longer valid" in replayed.summary


def test_the_fingerprint_no_longer_depends_on_the_run():
    """Including `execution_id` made a token structurally unredeemable: the
    retry's fingerprint could never equal the approved call's."""
    from app.mcp.approvals import _call_fingerprint

    arguments = (ToolArgument(name="connector_id", value="slack"),)
    turn_one = ToolCall(tool_id=DISABLE_CONNECTOR_TOOL_ID, arguments=arguments, execution_id="run-1")
    turn_two = ToolCall(tool_id=DISABLE_CONNECTOR_TOOL_ID, arguments=arguments, execution_id="run-2")

    assert _call_fingerprint(turn_one) == _call_fingerprint(turn_two)


def test_a_different_call_still_gets_a_different_fingerprint():
    from app.mcp.approvals import _call_fingerprint

    slack = ToolCall(tool_id=DISABLE_CONNECTOR_TOOL_ID, arguments=(ToolArgument(name="connector_id", value="slack"),))
    payroll = ToolCall(
        tool_id=DISABLE_CONNECTOR_TOOL_ID, arguments=(ToolArgument(name="connector_id", value="payroll"),)
    )

    assert _call_fingerprint(slack) != _call_fingerprint(payroll)


def test_the_approval_record_carries_the_arguments_it_authorized():
    store = ApprovalStore()
    call = ToolCall(
        tool_id=DISABLE_CONNECTOR_TOOL_ID,
        arguments=(ToolArgument(name="connector_id", value="slack"),),
        execution_id="run-1",
    )
    request = store.create(call, _ACTOR)
    store.approve(request.token, _ACTOR)

    replayed = store.approved_call(request.token, _ACTOR)

    assert replayed is not None
    assert replayed.tool_id == DISABLE_CONNECTOR_TOOL_ID
    assert replayed.arguments == call.arguments
    assert replayed.approval_token == request.token
