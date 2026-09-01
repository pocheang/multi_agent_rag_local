"""A tool outcome the user needs to hear about must reach the answer.

`_render_tool_results` filtered on `status == "succeeded"`, which swallowed
exactly the two outcomes that matter most: a tool that failed, and a write
waiting on the user's approval. Both produced an ordinary RAG answer with no
hint that the action the user asked for had not happened -- and since a `write`
tool always returns `approval_required` on its first call, that was the *normal*
outcome, not an edge case.
"""

from __future__ import annotations

from app.agents.synthesizer.service import _render_tool_results
from app.domain.contracts import ToolResult


def test_a_pending_approval_is_reported_not_swallowed():
    rendered = _render_tool_results(
        (
            ToolResult(
                tool_id="querymind_connector_disable_owned",
                status="approval_required",
                approval_status="pending",
                summary="approval required before this high-risk operation can run",
            ),
        )
    )

    assert "approval_required" in rendered
    assert "approval required before this high-risk operation can run" in rendered
    # The model must not tell the user the action is done.
    assert "has NOT been performed yet" in rendered


def test_a_failed_tool_is_reported():
    rendered = _render_tool_results(
        (ToolResult(tool_id="querymind_connector_disable_owned", status="failed", summary="owned connector not found"),)
    )

    assert "failed" in rendered
    assert "owned connector not found" in rendered


def test_a_successful_tool_still_renders():
    rendered = _render_tool_results(
        (ToolResult(tool_id="querymind_connector_disable_owned", status="succeeded", summary="connector disabled"),)
    )

    assert "succeeded" in rendered
    assert "connector disabled" in rendered


def test_a_summaryless_result_still_names_its_status():
    rendered = _render_tool_results((ToolResult(tool_id="querymind_connector_disable_owned", status="skipped"),))

    assert "skipped" in rendered


def test_no_tool_results_render_nothing():
    assert _render_tool_results(()) == ""
