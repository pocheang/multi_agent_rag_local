"""Admin operations routes used by the frontend admin console."""
from __future__ import annotations

import csv
import io
import statistics
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.api.dependencies import (
    _audit,
    _check_chroma_ready,
    _check_ollama_ready,
    _extract_grounding_support_from_detail,
    _filter_audit_rows,
    _history_store_for_user,
    _load_benchmark_queries,
    _parse_audit_ts,
    _parse_request_ts,
    _require_permission,
    _require_user,
    _runtime_diagnostics_summary,
    auth_service,
    settings,
)
from app.api.middleware import get_request_metrics
from app.graph.workflow import run_query
from app.services.consistency_guard import text_similarity
from app.services.retrieval_profiles import normalize_retrieval_profile, profile_force_local_only
from app.services.runtime_ops import (
    append_benchmark_trend,
    apply_rollback_profile,
    get_runtime_state,
    read_benchmark_trends,
    read_replay_trends,
    set_active_profile,
    set_canary,
)

router = APIRouter(prefix="/admin/ops", tags=["admin", "ops"])


def _overview_payload(
    *,
    request: Request,
    hours: int,
    actor_user_id: str | None,
    action_keyword: str | None,
) -> dict[str, Any]:
    window_hours = max(1, min(int(hours or 24), 24 * 7))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    audit_rows = auth_service.list_audit_logs(limit=2000)
    window_rows = _filter_audit_rows(
        rows=audit_rows,
        cutoff=cutoff,
        actor_user_id=actor_user_id,
        action_keyword=action_keyword,
    )

    total_requests = len(window_rows)
    error_count = sum(1 for row in window_rows if str(row.get("result", "")).lower() != "success")
    success_count = max(0, total_requests - error_count)
    error_rate = round((error_count / total_requests) * 100, 2) if total_requests else 0.0

    action_counter = Counter(str(row.get("action", "") or "unknown") for row in window_rows)
    resource_counter = Counter(str(row.get("resource_type", "") or "unknown") for row in window_rows)
    actor_users = {str(row.get("actor_user_id")) for row in window_rows if row.get("actor_user_id")}
    error_reason_counter = Counter(
        str(row.get("detail", "") or str(row.get("action", "") or "unknown_error"))
        for row in window_rows
        if str(row.get("result", "")).lower() != "success"
    )

    users = auth_service.list_users()
    active_sessions = auth_service.count_active_sessions()
    login_success = sum(
        1 for row in window_rows if str(row.get("action", "")) == "auth.login" and str(row.get("result", "")).lower() == "success"
    )
    login_failed = sum(
        1 for row in window_rows if str(row.get("action", "")) == "auth.login" and str(row.get("result", "")).lower() != "success"
    )
    query_requests = sum(1 for row in window_rows if str(row.get("action", "")).startswith("query."))
    upload_requests = sum(
        1
        for row in window_rows
        if str(row.get("action", "")) == "document.upload" and str(row.get("result", "")).lower() == "success"
    )

    bucket_counter: dict[str, dict[str, int]] = {}
    for row in window_rows:
        created_at = _parse_audit_ts(str(row.get("created_at", "")))
        bucket = created_at.strftime("%Y-%m-%d %H:00")
        slot = bucket_counter.setdefault(bucket, {"count": 0, "errors": 0})
        slot["count"] += 1
        if str(row.get("result", "")).lower() != "success":
            slot["errors"] += 1
    hourly = [
        {"bucket": key, "count": value["count"], "errors": value["errors"]}
        for key, value in sorted(bucket_counter.items(), key=lambda item: item[0])
    ]

    req_rows = get_request_metrics()
    req_window = [row for row in req_rows if _parse_request_ts(str(row.get("ts", ""))) >= cutoff]
    slow_requests = sorted(req_window, key=lambda row: int(row.get("duration_ms", 0) or 0), reverse=True)[:10]
    slow_requests_view = [
        {
            "ts": str(row.get("ts", "")),
            "method": str(row.get("method", "")),
            "path": str(row.get("path", "")),
            "status_code": int(row.get("status_code", 0) or 0),
            "duration_ms": int(row.get("duration_ms", 0) or 0),
            "error": str(row.get("error", "")),
        }
        for row in slow_requests
    ]

    services = {
        "ollama": _check_ollama_ready(),
        "chroma": _check_chroma_ready(),
        "neo4j": {"ok": True, "required": False, "message": "not probed in admin overview"},
    }
    services_ok = all(bool(item.get("ok")) for item in services.values() if item.get("required", True))

    return {
        "generated_at": now.isoformat(),
        "window_hours": window_hours,
        "status": "healthy" if services_ok else "degraded",
        "kpi": {
            "requests_total": total_requests,
            "requests_success": success_count,
            "requests_error": error_count,
            "error_rate_percent": error_rate,
            "active_users": len(actor_users),
            "active_sessions": active_sessions,
            "queries": query_requests,
            "uploads": upload_requests,
            "login_success": login_success,
            "login_failed": login_failed,
        },
        "users": {
            "total": len(users),
            "active": sum(1 for row in users if str(row.get("status", "")).lower() == "active"),
            "disabled": sum(1 for row in users if str(row.get("status", "")).lower() != "active"),
            "admin": sum(1 for row in users if str(row.get("role", "")).lower() == "admin"),
        },
        "top_actions": [{"action": key, "count": value} for key, value in action_counter.most_common(8)],
        "top_resource_types": [{"resource_type": key, "count": value} for key, value in resource_counter.most_common(8)],
        "top_error_reasons": [{"reason": key, "count": value} for key, value in error_reason_counter.most_common(8)],
        "slow_requests": slow_requests_view,
        "hourly": hourly,
        "services": services,
        "diagnostics": _runtime_diagnostics_summary(),
        "filters": {
            "actor_user_id": (actor_user_id or "").strip(),
            "action_keyword": (action_keyword or "").strip(),
        },
    }


def _alerts_payload(*, hours: int) -> dict[str, Any]:
    window_hours = max(1, min(int(hours or 24), 24 * 7))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    audit_rows = auth_service.list_audit_logs(limit=2000)
    window_rows = _filter_audit_rows(rows=audit_rows, cutoff=cutoff, actor_user_id=None, action_keyword=None)
    total = len(window_rows)
    errors = sum(1 for row in window_rows if str(row.get("result", "")).lower() != "success")
    error_rate = (errors / total) * 100 if total > 0 else 0.0

    req_rows = get_request_metrics()
    req_window = [row for row in req_rows if _parse_request_ts(str(row.get("ts", ""))) >= cutoff]
    durations = sorted(int(row.get("duration_ms", 0) or 0) for row in req_window)
    p95 = durations[max(0, int(len(durations) * 0.95) - 1)] if durations else 0

    grounding_values: list[float] = []
    for row in window_rows:
        if str(row.get("action", "")).strip() != "query.run":
            continue
        value = _extract_grounding_support_from_detail(str(row.get("detail", "")))
        if value is not None:
            grounding_values.append(value)
    grounding_avg = (sum(grounding_values) / len(grounding_values)) if grounding_values else 1.0

    alerts: list[dict[str, Any]] = []
    if p95 > int(settings.slo_p95_latency_ms_threshold):
        alerts.append(
            {
                "type": "latency",
                "severity": "high",
                "value": p95,
                "threshold": int(settings.slo_p95_latency_ms_threshold),
            }
        )
    if error_rate > float(settings.slo_error_rate_percent_threshold):
        alerts.append(
            {
                "type": "error_rate",
                "severity": "high",
                "value": round(error_rate, 2),
                "threshold": float(settings.slo_error_rate_percent_threshold),
            }
        )
    if grounding_avg < float(settings.slo_grounding_support_ratio_threshold):
        alerts.append(
            {
                "type": "grounding_support",
                "severity": "medium",
                "value": round(grounding_avg, 3),
                "threshold": float(settings.slo_grounding_support_ratio_threshold),
            }
        )

    return {
        "generated_at": now.isoformat(),
        "window_hours": window_hours,
        "status": "alerting" if alerts else "ok",
        "slo": {
            "p95_latency_ms": p95,
            "error_rate_percent": round(error_rate, 2),
            "grounding_support_ratio_avg": round(grounding_avg, 3),
        },
        "alerts": alerts,
    }


@router.get("/overview")
def admin_ops_overview(
    request: Request,
    hours: int = 24,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    return _overview_payload(request=request, hours=hours, actor_user_id=actor_user_id, action_keyword=action_keyword)


@router.get("/export.csv")
def admin_ops_export_csv(
    request: Request,
    hours: int = 24,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    overview = _overview_payload(request=request, hours=hours, actor_user_id=actor_user_id, action_keyword=action_keyword)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, min(int(hours or 24), 24 * 7)))
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
    writer.writerow(["summary", "requests_total", overview["kpi"]["requests_total"]])
    writer.writerow(["summary", "requests_success", overview["kpi"]["requests_success"]])
    writer.writerow(["summary", "requests_error", overview["kpi"]["requests_error"]])
    writer.writerow(["summary", "error_rate_percent", overview["kpi"]["error_rate_percent"]])
    writer.writerow([])
    writer.writerow(["audit_created_at", "actor_user_id", "actor_role", "action", "resource_type", "resource_id", "result", "detail"])
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
    filename = f"ops_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/retrieval-profile")
def admin_ops_retrieval_profile(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:audit_read", request, "admin")
    state = get_runtime_state()
    return {
        **state,
        "profiles": [
            {"id": "baseline", "label": "Baseline", "desc": "Conservative retrieval, lower risk."},
            {"id": "advanced", "label": "Advanced", "desc": "Default strategy."},
            {"id": "safe", "label": "Safe", "desc": "Local-only retrieval, web fallback disabled."},
        ],
    }


@router.post("/retrieval-profile")
def admin_ops_set_retrieval_profile(
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:ops_manage", request, "admin")
    follow_default = bool(payload.get("follow_config_default", False))
    profile = str(payload.get("profile", "") or "advanced")
    state = set_active_profile(profile=profile, follow_config_default=follow_default)
    _audit(
        request,
        action="admin.ops.profile.set",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"profile={state['active_profile']}; follow_default={state['follow_config_default']}",
    )
    return state


@router.post("/canary")
def admin_ops_set_canary(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    state = set_canary(
        enabled=bool(payload.get("enabled", False)),
        baseline_percent=int(payload.get("baseline_percent", 0) or 0),
        safe_percent=int(payload.get("safe_percent", 0) or 0),
        seed=str(payload.get("seed", "default") or "default"),
    )
    _audit(
        request,
        action="admin.ops.canary.set",
        resource_type="admin",
        result="success",
        user=user,
        detail=(
            f"enabled={state['canary']['enabled']}; baseline={state['canary']['baseline_percent']}; "
            f"safe={state['canary']['safe_percent']}; seed={state['canary']['seed']}"
        ),
    )
    return state


@router.post("/rollback")
def admin_ops_rollback(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    state = apply_rollback_profile()
    _audit(
        request,
        action="admin.ops.rollback",
        resource_type="admin",
        result="success",
        user=user,
        detail="runtime_profile_rollback_to_baseline",
    )
    return {"ok": True, "state": state}


@router.get("/benchmark/trends")
def admin_ops_benchmark_trends(
    request: Request,
    limit: int = 30,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = read_benchmark_trends(limit=max(1, min(limit, 300)))
    return {"items": rows, "count": len(rows)}


@router.post("/benchmark/run")
def admin_ops_benchmark_run(
    request: Request,
    max_queries: int = 20,
    strategy: str = "advanced",
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:ops_manage", request, "admin")
    query_path = Path("data/eval/benchmark_queries.txt")
    queries = _load_benchmark_queries(query_path, limit=max(1, min(max_queries, 100)))
    if not queries:
        raise HTTPException(status_code=400, detail="benchmark query set is empty")

    used_profile = normalize_retrieval_profile(strategy)
    latencies: list[float] = []
    support_ratios: list[float] = []
    citation_counts: list[int] = []
    for question in queries:
        t0 = time.perf_counter()
        result = run_query(
            question,
            use_web_fallback=not profile_force_local_only(used_profile),
            use_reasoning=False,
            retrieval_strategy=used_profile,
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)
        support_ratios.append(float((result.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0))
        citation_counts.append(
            len(result.get("vector_result", {}).get("citations", []) or [])
            + len(result.get("web_result", {}).get("citations", []) or [])
        )

    entry = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "num_queries": len(queries),
        "strategy": used_profile,
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2),
            "p95": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2),
            "avg": round(statistics.mean(latencies), 2),
        },
        "grounding_support_ratio": {
            "avg": round(statistics.mean(support_ratios), 4),
            "min": round(min(support_ratios), 4),
        },
        "citations": {
            "avg": round(statistics.mean(citation_counts), 2),
            "max": max(citation_counts),
        },
    }
    append_benchmark_trend(entry)
    _audit(
        request,
        action="admin.ops.benchmark.run",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"queries={len(queries)}; strategy={used_profile}",
    )
    return {"ok": True, "result": entry}


@router.get("/audit-report.md")
def admin_ops_audit_report_md(
    request: Request,
    hours: int = 24,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    overview = _overview_payload(request=request, hours=hours, actor_user_id=None, action_keyword=None)
    alerts = _alerts_payload(hours=hours)
    lines = [
        "# Ops Audit Report",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
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
    filename = f"ops_audit_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
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


@router.post("/ab-compare")
def admin_ops_ab_compare(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    question = str(payload.get("question", "") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    raw_strategies = payload.get("strategies")
    strategies = raw_strategies if isinstance(raw_strategies, list) and raw_strategies else ["baseline", "advanced", "safe"]
    normalized = [normalize_retrieval_profile(str(item)) for item in strategies]
    runs: dict[str, Any] = {}
    for strategy in normalized:
        t0 = time.perf_counter()
        result = run_query(
            question,
            use_web_fallback=not profile_force_local_only(strategy),
            use_reasoning=False,
            retrieval_strategy=strategy,
        )
        runs[strategy] = {
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            "answer": str(result.get("answer", "") or ""),
            "grounding_support_ratio": float((result.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0),
            "citations": len(result.get("vector_result", {}).get("citations", []) or [])
            + len(result.get("web_result", {}).get("citations", []) or []),
        }
    base = runs.get("advanced") or next(iter(runs.values()))
    diff = {}
    for strategy, row in runs.items():
        diff[strategy] = {
            "answer_similarity_vs_advanced": round(text_similarity(str(base.get("answer", "")), str(row.get("answer", ""))), 4),
            "latency_delta_ms_vs_advanced": round(float(row.get("latency_ms", 0.0)) - float(base.get("latency_ms", 0.0)), 2),
            "grounding_delta_vs_advanced": round(
                float(row.get("grounding_support_ratio", 0.0)) - float(base.get("grounding_support_ratio", 0.0)),
                4,
            ),
        }
    return {"question": question, "runs": runs, "diff": diff}


@router.post("/autotune")
def admin_ops_autotune(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    target_p95 = float(payload.get("target_p95_ms", 3000) or 3000)
    target_grounding = float(payload.get("target_grounding", 0.65) or 0.65)
    trends = read_replay_trends(limit=1)
    if not trends:
        raise HTTPException(status_code=400, detail="no replay trends found; run replay first")
    latest = trends[-1]
    latest_p95 = float(((latest.get("latency_ms", {}) or {}).get("p95", 0.0) or 0.0))
    latest_grounding = float(((latest.get("grounding_support_ratio", {}) or {}).get("avg", 0.0) or 0.0))
    patch: dict[str, Any] = {}
    if latest_p95 > target_p95:
        patch["TOP_K"] = max(2, int(settings.top_k) - 1)
        patch["MAX_CONTEXT_CHUNKS"] = max(3, int(settings.max_context_chunks) - 1)
    if latest_grounding < target_grounding:
        patch["TOP_K"] = max(int(patch.get("TOP_K", settings.top_k)), int(settings.top_k) + 1)
        patch["RANK_FEATURE_ENABLED"] = True
        patch["DYNAMIC_RETRIEVAL_ENABLED"] = True
    if not patch:
        patch = {"status": "no_change"}
    else:
        if "TOP_K" in patch:
            settings.top_k = int(patch["TOP_K"])
        if "MAX_CONTEXT_CHUNKS" in patch:
            settings.max_context_chunks = int(patch["MAX_CONTEXT_CHUNKS"])
        if "RANK_FEATURE_ENABLED" in patch:
            settings.rank_feature_enabled = bool(patch["RANK_FEATURE_ENABLED"])
        if "DYNAMIC_RETRIEVAL_ENABLED" in patch:
            settings.dynamic_retrieval_enabled = bool(patch["DYNAMIC_RETRIEVAL_ENABLED"])
    _audit(
        request,
        action="admin.ops.autotune",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"patch={patch}",
    )
    return {"ok": True, "latest": latest, "applied_patch": patch}


@router.post("/replay/run")
def admin_ops_replay_run(
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:ops_manage", request, "admin")
    max_questions = max(1, min(int(payload.get("max_questions", 30) or 30), 200))
    strategy = normalize_retrieval_profile(str(payload.get("strategy", "advanced") or "advanced"))
    history_store = _history_store_for_user(user)
    sessions = history_store.list_sessions()
    questions: list[str] = []
    for session in sessions:
        sid = str(session.get("session_id", "") or "")
        if not sid:
            continue
        detail = history_store.get_session(sid) or {}
        for message in detail.get("messages", []) or []:
            if str(message.get("role", "")) != "user":
                continue
            question = str(message.get("content", "") or "").strip()
            if question:
                questions.append(question)
            if len(questions) >= max_questions:
                break
        if len(questions) >= max_questions:
            break
    if not questions:
        raise HTTPException(status_code=400, detail="no historical questions found")
    return {
        "ok": True,
        "summary": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "strategy": strategy,
            "num_questions": len(questions),
        },
    }
