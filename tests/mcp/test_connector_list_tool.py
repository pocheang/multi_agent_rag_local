"""The governed tool catalogue gains a read.

Until now exactly one tool was registered -- `querymind_connector_disable_owned`,
a `write` -- so the whole governed stack (approval store, multi-step selector
loop, approve-then-resume replay, persistence, the frontend approval panel)
served one administrative action, and the `react` route had nothing it could
usefully do.

A read is the missing half: it is what lets the model find the id of a connector
before acting on it, and `operation="read"` skips the approval path entirely
(`ToolRegistry._REQUIRES_APPROVAL`), so it costs the user no confirmation.
"""

from __future__ import annotations

import asyncio
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.agents.tool.selector import ToolSelection, ToolSelector
from app.agents.tool.service import ToolAgentService
from app.core.config import get_settings
from app.mcp.contracts import ToolArgument, ToolCall
from app.mcp.runtime import (
    DISABLE_CONNECTOR_TOOL_ID,
    LIST_CONNECTORS_TOOL_ID,
    get_tool_stack,
    reset_tool_stack,
)
from app.orchestration.request import OrchestrationRequest, RequestActor

_ACTOR = RequestActor(user_id="u1", tenant_id="t1", role="viewer")


@pytest.fixture(autouse=True)
def _isolated_stack(monkeypatch):
    monkeypatch.setenv("API_SETTINGS_ENCRYPTION_KEY", "test-key-for-connector-credentials")
    # Building the stack writes real rows; point the app database at a temp file.
    # Deliberately not pytest's tmp_path -- see tests/mcp/test_tool_stack_sharing.py.
    root = Path(tempfile.mkdtemp(prefix="querymind-list-tool-"))
    db_path = root / "app.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    get_settings.cache_clear()
    reset_tool_stack()
    # Both connector tables carry ON DELETE CASCADE to users, so an owner has to
    # exist before a connector can reference it.
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY)")
    connection.executemany("INSERT OR IGNORE INTO users VALUES (?)", [("u1",), ("u2",)])
    connection.commit()
    connection.close()
    try:
        yield
    finally:
        reset_tool_stack()
        get_settings.cache_clear()
        shutil.rmtree(root, ignore_errors=True)


class _ScriptedSelector:
    """A selector that returns a fixed sequence of tool ids, then stops."""

    def __init__(self, *tool_ids: str | None) -> None:
        self._plan = list(tool_ids)
        self.seen_observations: list[tuple] = []

    async def select(self, question, conversation, catalog, *, observations=(), execution_id):
        del question, conversation, catalog
        self.seen_observations.append(tuple(observations))
        tool_id = self._plan.pop(0) if self._plan else None
        if tool_id is None:
            return ToolSelection(call=None, reason="done")
        arguments = (ToolArgument(name="connector_id", value="wiki"),) if tool_id == DISABLE_CONNECTOR_TOOL_ID else ()
        return ToolSelection(
            call=ToolCall(tool_id=tool_id, arguments=arguments, execution_id=execution_id),
            reason="next step",
        )


def _call(arguments: tuple[ToolArgument, ...] = ()) -> ToolCall:
    return ToolCall(tool_id=LIST_CONNECTORS_TOOL_ID, arguments=arguments, execution_id="exec-1")


def _add_connector(connector_id: str, owner_id: str, name: str = "Team wiki") -> None:
    get_tool_stack().connectors.create(
        connector_id=connector_id,
        owner_id=owner_id,
        name=name,
        base_url="https://example.invalid/api",
        allowed_hosts=frozenset({"example.invalid"}),
        secret="s" * 20,
    )


def test_the_read_tool_is_registered_alongside_the_write():
    catalog = get_tool_stack().registry.catalog(_ACTOR)

    assert LIST_CONNECTORS_TOOL_ID in {definition.tool_id for definition in catalog}


def test_a_read_tool_needs_no_approval():
    """`operation="read"` never enters the approval path, so a read costs the
    user no confirmation dialog and mints no token to redeem."""

    result = asyncio.run(get_tool_stack().gateway.invoke(_call(), _ACTOR))

    assert result.status == "succeeded"
    assert result.approval_status == "not_required"
    assert result.approval_token is None


def test_an_owner_with_no_connectors_gets_a_successful_empty_read():
    """Emptiness is a successful read, not a failure.

    `ToolAgentService._run_steps` breaks the loop on anything other than
    "succeeded", so reporting an empty list as `skipped` would end a multi-step
    plan that still had somewhere to go.
    """

    result = asyncio.run(get_tool_stack().gateway.invoke(_call(), _ACTOR))

    assert result.status == "succeeded"
    assert result.summary == "no connected integrations"


def test_a_missing_actor_identity_is_a_failure():
    result = asyncio.run(get_tool_stack().gateway.invoke(_call(), RequestActor()))

    assert result.status == "failed"


def test_a_zero_parameter_tool_accepts_no_arguments():
    _add_connector("wiki", "u1")

    result = asyncio.run(get_tool_stack().gateway.invoke(_call(), _ACTOR))

    assert result.status == "succeeded"
    assert result.summary == "1 connected integrations: wiki(enabled)"


def test_a_zero_parameter_tool_rejects_a_supplied_argument():
    """The declared schema is the whole contract; an undeclared argument is an
    error before the executor is reached."""

    definition = next(
        item for item in get_tool_stack().registry.catalog(_ACTOR) if item.tool_id == LIST_CONNECTORS_TOOL_ID
    )

    assert definition.validation_error(()) is None
    assert definition.validation_error((ToolArgument(name="connector_id", value="wiki"),)) is not None


def test_the_selector_can_call_a_tool_with_no_arguments():
    """A no-argument call has to survive the selector, not just the registry.

    The model's `arguments` object is filtered against the declared parameter
    names, so an empty one has to reach `ToolCall` as an empty tuple and then
    pass `validation_error` -- the early rejection that exists so an obviously
    wrong call never spends an approval round trip.
    """

    class _Response:
        content = '{"tool_id": "querymind_connector_list_owned", "arguments": {}, "reason": "user asked"}'

    class _Model:
        def invoke(self, _messages):
            return _Response()

    catalog = get_tool_stack().registry.catalog(_ACTOR)
    selection = asyncio.run(
        ToolSelector(model_factory=_Model).select(
            "which integrations do I have connected?",
            (),
            catalog,
            execution_id="exec-1",
        )
    )

    assert selection.call is not None
    assert selection.call.tool_id == LIST_CONNECTORS_TOOL_ID
    assert selection.call.arguments == ()


def test_a_read_then_write_run_stops_at_the_approval():
    """The composition the read exists to enable, against the real tools.

    `tests/mcp/test_tool_steps.py` covers the loop with synthetic definitions;
    this covers it with the two that are actually registered, because the
    interesting property is a `read` and a `write` behaving differently in the
    same run: the list succeeds and is observed, the disable comes back
    `approval_required`, and the loop stops there -- an approval means the action
    has *not* happened, so planning a third step on it would reason from a false
    premise.
    """

    _add_connector("wiki", "u1")
    stack = get_tool_stack()
    settings = get_settings().model_copy(update={"tool_max_steps": 3})
    selector = _ScriptedSelector(LIST_CONNECTORS_TOOL_ID, DISABLE_CONNECTOR_TOOL_ID, None)
    agent = ToolAgentService(
        stack.gateway,
        stack.registry,
        approvals=stack.approvals,
        selector=selector,
        settings=settings,
    )

    results = asyncio.run(
        agent.invoke_requested(
            OrchestrationRequest(question="disable my wiki integration", actor=_ACTOR),
            execution_id="run-1",
        )
    )

    assert [item.tool_id for item in results] == [LIST_CONNECTORS_TOOL_ID, DISABLE_CONNECTOR_TOOL_ID]
    assert results[0].status == "succeeded"
    # Two different fields: the call's outcome is `approval_required`, and the
    # approval it minted is `pending` until the user redeems the token.
    assert results[1].status == "approval_required"
    assert results[1].approval_status == "pending"
    assert results[1].approval_token
    # The read's summary was shown to the decision that followed it, and it is
    # the id-and-status form rather than the connector's own name.
    assert selector.seen_observations[1][0].summary == "1 connected integrations: wiki(enabled)"
    # Third step never ran: the loop stopped on the approval, not on the script.
    assert len(selector.seen_observations) == 2


def test_the_summary_names_a_bounded_number_of_connectors():
    for index in range(12):
        _add_connector(f"c{index}", "u1")

    result = asyncio.run(get_tool_stack().gateway.invoke(_call(), _ACTOR))

    assert result.summary.startswith("12 connected integrations:")
    assert result.summary.endswith("+2 more")
