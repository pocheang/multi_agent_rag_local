"""What the governed tool loop did has to reach the caller.

`FinalAnswer.tool_results` was consumed only to derive `pending_approval`, so a
request that ran two tools produced one answer and no record of what happened --
the multi-step loop was invisible to everything except the answer prose the model
happened to write.
"""

from __future__ import annotations

from app.domain.contracts import FinalAnswer, ToolResult
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline

_TOKEN = "t" * 64


def _result(*tool_results: ToolResult):
    return RAGPipeline._result_from_final_answer(
        PipelineProfile.ADVANCED,
        FinalAnswer(answer="done", tool_results=tool_results),
    )


def test_every_tool_run_reaches_the_public_result():
    result = _result(
        ToolResult(tool_id="querymind_step_one", status="succeeded", summary="fetched"),
        ToolResult(tool_id="querymind_step_two", status="succeeded", summary="wrote a note"),
    )

    assert [(run.tool_id, run.status, run.summary) for run in result.tool_runs] == [
        ("querymind_step_one", "succeeded", "fetched"),
        ("querymind_step_two", "succeeded", "wrote a note"),
    ]


def test_a_failed_run_is_reported_too():
    result = _result(ToolResult(tool_id="querymind_step_one", status="failed", summary="nope"))

    assert result.status == "complete"  # the answer is still an answer
    assert [run.status for run in result.tool_runs] == ["failed"]


def test_a_pending_approval_is_both_a_run_and_the_discriminator():
    result = _result(
        ToolResult(
            tool_id="querymind_connector_disable_owned",
            status="approval_required",
            approval_status="pending",
            approval_token=_TOKEN,
            summary="needs confirmation",
        )
    )

    assert result.status == "pending_approval"
    assert result.pending_approval is not None
    assert result.pending_approval.token == _TOKEN
    assert [run.status for run in result.tool_runs] == ["approval_required"]


def test_the_run_list_never_carries_the_token():
    """`pending_approval` is the one place a client should look for an action it
    can confirm; duplicating the token into a list invites a second code path."""
    result = _result(
        ToolResult(
            tool_id="querymind_connector_disable_owned",
            status="approval_required",
            approval_token=_TOKEN,
        )
    )

    assert _TOKEN not in result.tool_runs[0].model_dump_json()


def test_a_run_with_no_tools_reports_none():
    result = _result()

    assert result.tool_runs == ()
    assert result.status == "complete"
    assert result.pending_approval is None
