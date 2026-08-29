"""Admin operations routes used by the frontend admin console."""

from __future__ import annotations

import csv
import io
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.api import dependencies as api_dependencies
from app.api.dependencies import (
    _audit,
    _check_chroma_ready,
    _check_ollama_ready,
    _extract_grounding_support_from_detail,
    _filter_audit_rows,
    _history_store_for_user,
    _parse_audit_ts,
    _parse_request_ts,
    _require_permission,
    _require_user,
    _runtime_diagnostics_summary,
    auth_service,
    runtime_metrics,
    settings,
)
from app.api.routes.compatibility.pipeline_compat import execute_standard_compatibility
from app.api.transport.errors import bad_request, service_unavailable
from app.api.transport.middleware import get_request_metrics
from app.services.models.config_store import get_global_model_settings, public_global_model_settings
from app.services.observability.log_buffer import list_log_levels, reset_logger_levels, set_logger_level
from app.services.runtime.runtime_ops import (
    apply_replay_autotune,
    build_ops_alerts,
    build_ops_overview,
    build_runtime_snapshot,
    cached_service_health,
    probe_neo4j_ready,
    read_benchmark_trends,
    read_replay_trends,
    run_benchmark,
    run_replay,
    system_resource_snapshot,
)

router = APIRouter(prefix="/admin/ops", tags=["admin", "ops"])


def _service_health_snapshot() -> dict[str, dict[str, Any]]:
    return cached_service_health(
        {
            "api": lambda: {"ok": True, "required": True, "latency_ms": 0},
            "database": _check_database_ready,
            "vector_store": _check_chroma_ready,
            "graph_store": lambda: probe_neo4j_ready(settings.neo4j_uri),
            "ollama": _check_ollama_ready,
        }
    )


def _check_database_ready() -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with auth_service._connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"ok": True, "required": True, "latency_ms": int((time.perf_counter() - started) * 1000)}
    except Exception as exc:
        return {
            "ok": False,
            "required": True,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error": str(exc),
        }


def _runtime_snapshot_payload() -> dict[str, Any]:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=5)
    rows = [row for row in get_request_metrics() if _parse_request_ts(str(row.get("ts", ""))) >= cutoff]
    global_model = get_global_model_settings()
    public_model = public_global_model_settings(global_model)
    provider = str(global_model.get("provider", "local") or "local")
    model_ready = provider in {"local", "ollama"} or bool(global_model.get("api_key"))
    return build_runtime_snapshot(
        generated_at=now,
        request_rows=rows,
        resources=system_resource_snapshot(settings.app_db_path.parent),
        services=_service_health_snapshot(),
        public_model=public_model,
        model_ready=model_ready,
        model_required=bool(global_model.get("enabled", False)),
        active_requests=int((runtime_metrics.snapshot().get("gauges") or {}).get("query_guard_inflight", 0) or 0),
    )


def _overview_payload(
    *,
    hours: int,
    actor_user_id: str | None,
    action_keyword: str | None,
) -> dict[str, Any]:
    window_hours = max(1, min(int(hours or 24), 24 * 7))
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=window_hours)

    audit_rows = auth_service.list_audit_logs(limit=2000)
    window_rows = _filter_audit_rows(
        rows=audit_rows,
        cutoff=cutoff,
        actor_user_id=actor_user_id,
        action_keyword=action_keyword,
    )

    users = auth_service.list_users()
    active_sessions = auth_service.count_active_sessions()
    req_rows = get_request_metrics()
    req_window = [row for row in req_rows if _parse_request_ts(str(row.get("ts", ""))) >= cutoff]
    services = {
        "ollama": _check_ollama_ready(),
        "chroma": _check_chroma_ready(),
        "neo4j": {"ok": True, "required": False, "message": "not probed in admin overview"},
    }
    return build_ops_overview(
        generated_at=now,
        window_hours=window_hours,
        window_rows=window_rows,
        users=users,
        active_sessions=active_sessions,
        request_rows=req_window,
        services=services,
        diagnostics=_runtime_diagnostics_summary(),
        bucket_for_row=lambda row: _parse_audit_ts(str(row.get("created_at", ""))).strftime("%Y-%m-%d %H:00"),
        actor_user_id=actor_user_id,
        action_keyword=action_keyword,
    )


def _alerts_payload(*, hours: int) -> dict[str, Any]:
    window_hours = max(1, min(int(hours or 24), 24 * 7))
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=window_hours)

    audit_rows = auth_service.list_audit_logs(limit=2000)
    window_rows = _filter_audit_rows(rows=audit_rows, cutoff=cutoff, actor_user_id=None, action_keyword=None)
    req_rows = get_request_metrics()
    req_window = [row for row in req_rows if _parse_request_ts(str(row.get("ts", ""))) >= cutoff]
    return build_ops_alerts(
        generated_at=now,
        window_hours=window_hours,
        window_rows=window_rows,
        request_rows=req_window,
        extract_grounding_support=_extract_grounding_support_from_detail,
        p95_latency_threshold=int(settings.slo_p95_latency_ms_threshold),
        error_rate_threshold=float(settings.slo_error_rate_percent_threshold),
        grounding_threshold=float(settings.slo_grounding_support_ratio_threshold),
    )


def _execute_standard_profile(question: str) -> dict[str, Any]:
    """Keep operations comparisons on the standard RAGPipeline compatibility contract."""
    return execute_standard_compatibility(
        question=question,
        use_web_fallback=True,
        use_reasoning=False,
    )


@router.get("/runtime")
def admin_ops_runtime(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:audit_read", request, "admin")
    return _runtime_snapshot_payload()


@router.get("/overview")
def admin_ops_overview(
    request: Request,
    hours: int = 24,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    return _overview_payload(hours=hours, actor_user_id=actor_user_id, action_keyword=action_keyword)


@router.get("/export.csv")
def admin_ops_export_csv(
    request: Request,
    hours: int = 24,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    overview = _overview_payload(hours=hours, actor_user_id=actor_user_id, action_keyword=action_keyword)
    cutoff = datetime.now(UTC) - timedelta(hours=max(1, min(int(hours or 24), 24 * 7)))
    window_rows = _filter_audit_rows(
        rows=auth_service.list_audit_logs(limit=2000),
        cutoff=cutoff,
        actor_user_id=actor_user_id,
        action_keyword=action_keyword,
    )

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["section", "key", "value"])
    writer.writerow(["meta", "generated_at", overview["generated_at"]])
    writer.writerow(["meta", "window_hours", overview["window_hours"]])
    writer.writerow(["summary", "status", overview["status"]])
    writer.writerow(["summary", "request_count", overview["kpi"]["requests_total"]])
    writer.writerow(["summary", "requests_total", overview["kpi"]["requests_total"]])
    writer.writerow(["summary", "requests_success", overview["kpi"]["requests_success"]])
    writer.writerow(["summary", "requests_error", overview["kpi"]["requests_error"]])
    writer.writerow(["summary", "error_rate_percent", overview["kpi"]["error_rate_percent"]])
    writer.writerow([])
    writer.writerow(
        [
            "audit_created_at",
            "actor_user_id",
            "actor_role",
            "action",
            "resource_type",
            "resource_id",
            "result",
            "detail",
        ]
    )
    for row in window_rows:
        writer.writerow(
            [
                str(row.get("created_at", "")),
                str(row.get("actor_user_id", "")),
                str(row.get("actor_role", "")),
                str(row.get("action", "")),
                str(row.get("resource_type", "")),
                str(row.get("resource_id", "")),
                str(row.get("result", "")),
                str(row.get("detail", "")),
            ]
        )
    filename = f"ops_report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/benchmark/trends")
def admin_ops_benchmark_trends(
    request: Request,
    limit: int = 30,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = read_benchmark_trends(limit=max(1, min(limit, 300)))
    return {"items": rows, "count": len(rows)}


@router.post("/benchmark/run", status_code=202)
def admin_ops_benchmark_run(
    request: Request,
    max_queries: int = 20,
    user: dict[str, Any] = Depends(_require_user),
):
    """Accept a benchmark run and execute it off the request path.

    A run executes up to ``max_queries`` full RAG queries; doing that inline kept
    one HTTP request open for minutes (well past any reverse-proxy timeout) and
    occupied a threadpool worker the whole time.  Results land in the existing
    benchmark history, readable via ``GET /admin/ops/benchmark/trends``.
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    if max_queries < 1:
        raise bad_request("max_queries must be >= 1")
    queue = api_dependencies.get_query_runtime().shadow_queue
    accepted = queue.submit(run_benchmark, max_queries=max_queries, execute_query=_execute_standard_profile)
    if not accepted:
        raise service_unavailable("background queue is full; retry shortly")
    _audit(
        request,
        action="admin.ops.benchmark.run",
        resource_type="admin",
        result="accepted",
        user=user,
        detail=f"queries={max_queries}",
    )
    return {"ok": True, "status": "accepted", "max_queries": max_queries}


@router.get("/audit-report.md")
def admin_ops_audit_report_md(
    request: Request,
    hours: int = 24,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    overview = _overview_payload(hours=hours, actor_user_id=None, action_keyword=None)
    alerts = _alerts_payload(hours=hours)
    lines = [
        "# Ops Audit Report",
        "",
        f"- generated_at: {datetime.now(UTC).isoformat()}",
        f"- window_hours: {hours}",
        f"- status: {overview.get('status', 'unknown')}",
        "",
        "## KPI",
        "",
        f"- requests_total: {overview.get('kpi', {}).get('requests_total', 0)}",
        f"- requests_success: {overview.get('kpi', {}).get('requests_success', 0)}",
        f"- requests_error: {overview.get('kpi', {}).get('requests_error', 0)}",
        f"- error_rate_percent: {overview.get('kpi', {}).get('error_rate_percent', 0)}",
        "",
        "## SLO",
        "",
        f"- p95_latency_ms: {alerts.get('slo', {}).get('p95_latency_ms', 0)}",
        f"- error_rate_percent: {alerts.get('slo', {}).get('error_rate_percent', 0)}",
        f"- grounding_support_ratio_avg: {alerts.get('slo', {}).get('grounding_support_ratio_avg', 0)}",
        "",
        "## Top Actions",
        "",
    ]
    for row in overview.get("top_actions", [])[:10]:
        lines.append(f"- {row.get('action', 'unknown')}: {row.get('count', 0)}")
    lines.extend(["", "## Alerts", ""])
    if not alerts.get("alerts"):
        lines.append("- no_active_alerts")
    else:
        for row in alerts.get("alerts", []):
            lines.append(
                f"- {row.get('type', 'unknown')} ({row.get('severity', 'unknown')}): "
                f"value={row.get('value')} threshold={row.get('threshold')}"
            )
    text = "\n".join(lines) + "\n"
    filename = f"ops_audit_report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.md"
    return Response(
        content=text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/replay/trends")
def admin_ops_replay_trends(
    request: Request,
    limit: int = 30,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = read_replay_trends(limit=max(1, min(limit, 300)))
    return {"items": rows, "count": len(rows)}


@router.post("/autotune")
def admin_ops_autotune(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    target_p95 = float(payload.get("target_p95_ms", 3000) or 3000)
    target_grounding = float(payload.get("target_grounding", 0.65) or 0.65)
    try:
        latest, patch = apply_replay_autotune(
            target_p95=target_p95,
            target_grounding=target_grounding,
            settings=settings,
        )
    except ValueError as exc:
        raise bad_request(str(exc))
    _audit(
        request,
        action="admin.ops.autotune",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"patch={patch}",
    )
    return {"ok": True, "latest": latest, "applied_patch": patch}


@router.post("/replay/run", status_code=202)
def admin_ops_replay_run(
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """Accept a replay run and execute it off the request path.

    Same reasoning as the benchmark endpoint: up to 50 full RAG queries is
    minutes of work, not an HTTP request.
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    max_questions = max(1, min(int(payload.get("max_questions", 30) or 30), 50))
    history_store = _history_store_for_user(user)
    queue = api_dependencies.get_query_runtime().shadow_queue
    accepted = queue.submit(
        run_replay,
        history_store=history_store,
        max_questions=max_questions,
        execute_query=_execute_standard_profile,
    )
    if not accepted:
        raise service_unavailable("background queue is full; retry shortly")
    _audit(
        request,
        action="admin.ops.replay.run",
        resource_type="admin",
        result="accepted",
        user=user,
        detail=f"questions={max_questions}",
    )
    return {"ok": True, "status": "accepted", "max_questions": max_questions}


# ============================================================================
# Log Level Management Endpoints
# ============================================================================


@router.get("/logging/levels")
def get_log_levels(
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """
    Get current log levels for all active loggers.

    Returns a dictionary of logger names and their current levels.
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    return list_log_levels()


@router.post("/logging/level")
def set_log_level(
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """
    Set log level for a specific logger or all loggers.

    Request body:
    {
        "logger": "app.agents.enhanced_router_agent",  // or "root" for all
        "level": "DEBUG"  // DEBUG, INFO, WARNING, ERROR, CRITICAL
    }

    Returns:
        Updated log level configuration
    """
    _require_permission(user, "admin:ops_manage", request, "admin")

    logger_name = str(payload.get("logger", "")).strip()
    level_str = str(payload.get("level", "")).strip().upper()
    try:
        result = set_logger_level(logger_name=logger_name, level=level_str)
    except ValueError as exc:
        raise bad_request(str(exc))

    # Audit the change
    _audit(
        request,
        action="admin.logging.set_level",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"logger={logger_name},level={level_str}",
    )

    return result


@router.post("/logging/reset")
def reset_log_levels(
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """
    Reset all log levels to default (INFO).

    This is useful after debugging to restore normal logging behavior.
    """
    _require_permission(user, "admin:ops_manage", request, "admin")

    result = reset_logger_levels()

    _audit(
        request,
        action="admin.logging.reset",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"reset_count={result['reset_count']}",
    )
    return result
