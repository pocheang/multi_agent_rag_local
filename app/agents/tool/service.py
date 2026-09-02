"""Typed adapter from a user's tool request to the governed MCP gateway.

Tool *selection* lives in ``selector.py`` and is deliberately blind to retrieved
content; this module owns the governed invocation around it. Note that ``run``
takes no evidence: the orchestration contract was narrowed so the tool path has
no argument through which document content could arrive.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from app.agents.tool.selector import ToolObservation, ToolSelection, ToolSelector
from app.core.config import Settings, get_settings
from app.domain.contracts import RouteDecision, TaskPlan, ToolResult
from app.mcp.approvals import ApprovalStore
from app.mcp.contracts import ToolDefinition
from app.mcp.gateway import MCPGateway
from app.mcp.registry import ToolRegistry
from app.mcp.runtime import get_tool_stack
from app.orchestration.request import OrchestrationRequest, RequestActor

SELECTOR_TOOL_ID = "querymind_tool_selector"


class ToolAgentService:
    """Select at most one governed tool and invoke it through the registry."""

    def __init__(
        self,
        gateway: MCPGateway | None = None,
        registry: ToolRegistry | None = None,
        *,
        approvals: ApprovalStore | None = None,
        selector: ToolSelector | None = None,
        settings: Settings | None = None,
    ) -> None:
        # Injected dependencies win; otherwise the process-wide stack is resolved
        # on first *use*, not here. CoreCapabilities constructs this service by
        # default_factory, and building the stack eagerly would (a) demand
        # API_SETTINGS_ENCRYPTION_KEY of every test and script that touches
        # capabilities, and (b) still leave the pipeline on a different
        # ApprovalStore than the REST approval endpoint.
        self._gateway = gateway
        self._registry = registry
        self._approvals = approvals
        self._selector = selector or ToolSelector()
        self._max_steps = max(1, int((settings or get_settings()).tool_max_steps))

    def _resolve(self) -> tuple[MCPGateway, ToolRegistry, ApprovalStore]:
        if self._gateway is not None and self._registry is not None and self._approvals is not None:
            return self._gateway, self._registry, self._approvals
        stack = get_tool_stack()
        return stack.gateway, stack.registry, stack.approvals

    async def invoke_requested(
        self,
        request: OrchestrationRequest,
        *,
        execution_id: str,
    ) -> tuple[ToolResult, ...]:
        """Select a governed tool from the user's request and invoke it.

        Always reports an outcome once the router has asked for tools. Returning
        an empty tuple when nothing matched is what made a mis-routed request a
        silent no-op: the user got an ordinary answer and no hint that the action
        they asked for had not happened.
        """

        actor = request.actor
        if actor is None or not actor.user_id:
            return (
                ToolResult(
                    tool_id=SELECTOR_TOOL_ID,
                    status="failed",
                    summary="authentication required: no valid actor",
                ),
            )

        try:
            gateway, registry, approvals = self._resolve()
        except Exception as exc:
            return (
                ToolResult(
                    tool_id=SELECTOR_TOOL_ID,
                    status="failed",
                    summary=f"tool system unavailable: {type(exc).__name__}",
                ),
            )

        if request.approval_token:
            # A resume runs only the approved call. The rest of the pipeline
            # re-runs, but tools that already completed in the earlier turn must
            # not run twice -- replaying a whole multi-step plan would repeat
            # every action that already succeeded.
            return (await self._replay_approved(approvals, gateway, request, actor, execution_id),)

        return await self._run_steps(gateway, registry, request, actor, execution_id)

    async def _run_steps(
        self,
        gateway: MCPGateway,
        registry: ToolRegistry,
        request: OrchestrationRequest,
        actor: RequestActor,
        execution_id: str,
    ) -> tuple[ToolResult, ...]:
        """Select, invoke, observe, repeat -- up to ``TOOL_MAX_STEPS`` hops.

        Stops on anything other than a clean success. An ``approval_required``
        result means the action has *not* happened, so planning a next step on
        top of it would be reasoning from a false premise; a failure is the same
        problem. Both end the loop and are reported as-is.
        """

        catalog = registry.catalog(actor)
        results: list[ToolResult] = []
        observations: list[ToolObservation] = []
        attempted: set[tuple[str, tuple[tuple[str, str], ...]]] = set()

        for _step in range(self._max_steps):
            selection: ToolSelection = await self._selector.select(
                request.question,
                request.conversation,
                catalog,
                observations=tuple(observations),
                execution_id=execution_id,
            )
            if selection.call is None:
                if results:
                    break
                return (
                    ToolResult(
                        tool_id=SELECTOR_TOOL_ID,
                        status="skipped",
                        summary=f"no action taken: {selection.reason}",
                    ),
                )
            fingerprint = (
                selection.call.tool_id,
                tuple((argument.name, argument.value) for argument in selection.call.arguments),
            )
            if fingerprint in attempted:
                # The model is repeating itself rather than finishing. Stop
                # rather than spend the remaining hops on the same call.
                break
            attempted.add(fingerprint)

            result = await gateway.invoke(selection.call, actor)
            results.append(result)
            if result.status != "succeeded":
                break
            observations.append(_observation(result, catalog))

        return tuple(results)

    @staticmethod
    async def _replay_approved(
        approvals: ApprovalStore,
        gateway: MCPGateway,
        request: OrchestrationRequest,
        actor: RequestActor,
        execution_id: str,
    ) -> ToolResult:
        """Run the call the user approved, not whatever a selector picks now.

        Resuming re-runs the whole pipeline (which is how the caller's access
        scope gets re-resolved rather than replayed), so the selector would run
        again on the same question -- and a model is not obliged to choose the
        same call twice. The approval authorized one specific action; this
        replays exactly that one.
        """

        approved = approvals.approved_call(str(request.approval_token), actor)
        if approved is None:
            return ToolResult(
                tool_id=SELECTOR_TOOL_ID,
                status="failed",
                summary="approval is no longer valid; it may have expired, been used, or belong to someone else",
            )
        # Keep the current run's id so approval and audit events land in the
        # trace this caller is watching, not the one that raised the request.
        return await gateway.invoke(approved.model_copy(update={"execution_id": execution_id}), actor)

    async def run(
        self,
        request: OrchestrationRequest,
        route: RouteDecision,
        plan: TaskPlan,
    ) -> tuple[ToolResult, ...]:
        """Use the same governed boundary when called by the typed orchestration engine.

        No ``evidence`` parameter, on purpose: see ``selector`` for why the tool
        path must not be reachable from retrieved content.
        """
        del route, plan
        return await self.invoke_requested(
            request, execution_id=request.execution_id or request.request_id or str(uuid4())
        )


def _observation(result: ToolResult, catalog: Sequence[ToolDefinition]) -> ToolObservation:
    """Decide what an earlier hop may tell the next decision.

    An ``open_world`` tool reaches content this system does not control, so its
    text is somebody else's writing; letting it steer the next tool choice is
    the hole `selector` closes for retrieved content, one layer down. Such a
    tool contributes its id and status only.
    """

    definition = next((item for item in catalog if item.tool_id == result.tool_id), None)
    untrusted = definition is not None and definition.risk == "open_world"
    return ToolObservation(
        tool_id=result.tool_id,
        status=result.status,
        summary="" if untrusted else result.summary,
    )


__all__ = ["SELECTOR_TOOL_ID", "ToolAgentService"]
