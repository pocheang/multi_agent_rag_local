"""Tool arguments now come from a model, so the registry has to check them.

While the only tool was reached by a regex, the accepted shape of its one
argument was baked into the capture group -- `[a-z][a-z0-9_-]{0,63}` could not
produce anything else. A selector emits whatever the model wrote, so the
declared schema is the only thing standing between the model and the executor.
"""

from __future__ import annotations

import pytest

from app.domain.contracts import ToolResult
from app.mcp.approvals import ApprovalStore
from app.mcp.authorization import AuthorizationPolicy
from app.mcp.contracts import ToolArgument, ToolCall, ToolDefinition, ToolParameter
from app.mcp.registry import ToolRegistry
from app.orchestration.request import RequestActor

_ACTOR = RequestActor(user_id="u1", tenant_id="t1", role="viewer")
_TOOL_ID = "querymind_connector_disable_owned"

_DEFINITION = ToolDefinition(
    tool_id=_TOOL_ID,
    operation="read",  # read: no approval gate, so validation is what we observe
    parameters=(
        ToolParameter(name="connector_id", required=True, max_length=64, pattern=r"[a-z][a-z0-9_-]{0,63}"),
        ToolParameter(name="note", required=False, max_length=10),
    ),
)


def _registry() -> ToolRegistry:
    registry = ToolRegistry(authorization=AuthorizationPolicy(), approvals=ApprovalStore())

    async def executor(call: ToolCall, actor: RequestActor) -> ToolResult:
        del actor
        return ToolResult(tool_id=call.tool_id, status="succeeded", summary="ran")

    registry.register(_DEFINITION, executor)
    return registry


def _call(*arguments: tuple[str, str]) -> ToolCall:
    return ToolCall(
        tool_id=_TOOL_ID,
        arguments=tuple(ToolArgument(name=name, value=value) for name, value in arguments),
        execution_id="exec-1",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ((("connector_id", "slack"),), None),
        ((("connector_id", "slack"), ("note", "hi")), None),
        ((), "missing required argument: connector_id"),
        ((("wat", "x"),), "unknown argument: wat"),
        ((("connector_id", "SLACK; DROP"),), "does not match its declared pattern"),
        ((("connector_id", "slack"), ("note", "far too long a note")), "argument too long: note"),
    ],
)
async def test_the_registry_enforces_the_declared_schema(arguments, expected):
    result = await _registry().invoke(_call(*arguments), _ACTOR)

    if expected is None:
        assert result.status == "succeeded"
    else:
        assert result.status == "failed"
        assert expected in result.summary


def test_a_duplicate_argument_is_rejected():
    assert "duplicate argument" in str(
        _DEFINITION.validation_error(
            (
                ToolArgument(name="connector_id", value="a"),
                ToolArgument(name="connector_id", value="b"),
            )
        )
    )


def test_the_catalogue_only_offers_what_the_actor_may_invoke():
    """Offering a tool and then refusing it wastes a turn and leaks that the
    tool exists."""
    registry = ToolRegistry(authorization=AuthorizationPolicy(), approvals=ApprovalStore())

    async def executor(call: ToolCall, actor: RequestActor) -> ToolResult:
        del actor
        return ToolResult(tool_id=call.tool_id, status="succeeded")

    registry.register(_DEFINITION, executor)
    registry.register(
        ToolDefinition(tool_id="querymind_admin_purge", operation="delete", required_scopes=frozenset({"admin:purge"})),
        executor,
    )

    viewer_tools = {item.tool_id for item in registry.catalog(_ACTOR)}
    admin = RequestActor(user_id="u2", role="admin", permissions=frozenset({"admin:purge"}))
    admin_tools = {item.tool_id for item in registry.catalog(admin)}

    assert viewer_tools == {_TOOL_ID}
    assert admin_tools == {_TOOL_ID, "querymind_admin_purge"}


def test_an_unauthenticated_actor_is_offered_nothing():
    registry = _registry()

    assert registry.catalog(RequestActor()) == ()
