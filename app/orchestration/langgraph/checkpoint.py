"""Checkpoint identity helpers with fail-closed tenant scoping."""

from __future__ import annotations

from typing import Any

from app.orchestration.request import OrchestrationRequest


def checkpoint_thread_id(request: OrchestrationRequest) -> str | None:
    """Return a tenant-scoped thread id only when every identity part exists."""

    actor = request.actor
    if actor is None:
        return None
    tenant_id = str(actor.tenant_id or actor.user_id or "").strip()
    user_id = str(actor.user_id or "").strip()
    session_id = str(request.session_id or "").strip()
    request_id = str(request.request_id or request.execution_id or "").strip()
    if not all((tenant_id, user_id, session_id, request_id)):
        return None
    return ":".join((tenant_id, user_id, session_id, request_id))


def checkpoint_config(request: OrchestrationRequest) -> dict[str, Any] | None:
    """Build LangGraph config or select request-local, non-persistent execution."""

    thread_id = checkpoint_thread_id(request)
    if thread_id is None:
        return None
    return {"configurable": {"thread_id": thread_id}}


__all__ = ["checkpoint_config", "checkpoint_thread_id"]
