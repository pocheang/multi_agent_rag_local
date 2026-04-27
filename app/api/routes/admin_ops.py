"""Admin operations routes for the Multi-Agent Local RAG API."""
import csv
import io
import json
import logging
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from app.api.dependencies import (    auth_service,    query_result_cache,    runtime_metrics,    settings,    shadow_queue,    _require_user,    _audit,    _require_permission,    _parse_audit_ts,    _filter_audit_rows,    _parse_request_ts,    _extract_grounding_support_from_detail,    _load_benchmark_queries,    _check_ollama_ready,    _check_chroma_ready,    _runtime_diagnostics_summary,    _history_store_for_user,)
from app.api.middleware import get_request_metrics
from app.graph.workflow import run_query
from app.services.index_manager import rebuild_all_vector_index
from app.services.retrieval_profiles import normalize_retrieval_profile
from app.services.runtime_ops import (    append_benchmark_trend,    append_index_freshness,    append_replay_trend,    append_shadow_run,    apply_rollback_profile,    choose_shadow,    get_runtime_state,    read_benchmark_trends,    read_index_freshness,    read_replay_trends,    read_shadow_runs,    set_active_profile,    set_canary,    set_feature_flags,    set_shadow,)

router = APIRouter(prefix="/admin/ops", tags=["admin", "ops"])
logger = logging.getLogger(__name__)


@router.get("/overview")
def admin_ops_overview(
    request: Request,
    hours: int = 24,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    window_hours = max(1, min(hours, 24 * 7))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    audit_rows = auth_service.list_audit_logs(limit=1000)
    window_rows = _filter_audit_rows(
        rows=audit_rows,
        cutoff=cutoff,
        actor_user_id=actor_user_id,
        action_keyword=action_keyword,
    )

    total_requests = len(window_rows)
    error_count = sum(1 for row in window_rows if str(row.get("result", "")).lower() != "success")
    success_count = max(0, total_requests - error_count)
    error_rate = round((error_count / total_requests) * 100, 2) if total_requests > 0 else 0.0

    action_counter = Counter(str(row.get("action", "") or "unknown") for row in window_rows)
    resource_counter = Counter(str(row.get("resource_type", "") or "unknown") for row in window_rows)
    actor_users = {str(row.get("actor_user_id")) for row in window_rows if row.get("actor_user_id")}
    error_reason_counter = Counter(
        str(row.get("detail", "") or str(row.get("action", "") or "unknown_error"))
        for row in window_rows
        if str(row.get("result", "")).lower() != "success"
    )

    users = auth_service.list_users()
    user_total = len(users)
    user_active = sum(1 for row in users if str(row.get("status", "")).lower() == "active")
    user_disabled = user_total - user_active
    user_admin = sum(1 for row in users if str(row.get("role", "")).lower() == "admin")

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
        for key, value in sorted(bucket_counter.items(), key=lambda x: x[0])
    ]

    with _request_metrics_lock:
        req_rows = list(_request_metrics)
    req_window = [r for r in req_rows if _parse_request_ts(str(r.get("ts", ""))) >= cutoff]
    slow_requests = sorted(req_window, key=lambda x: int(x.get("duration_ms", 0)), reverse=True)[:10]
    slow_requests_view = [
        {
            "ts": str(row.get("ts", "")),
            "method": str(row.get("method", "")),
            "path": str(row.get("path", "")),
            "status_code": int(row.get("status_code", 0)),
            "duration_ms": int(row.get("duration_ms", 0)),
            "error": str(row.get("error", "")),
        }
        for row in slow_requests
    ]

    services = {
        "ollama": _check_ollama_ready(),
        "neo4j": _check_neo4j_ready(),
        "chroma": _check_chroma_ready(),
    }
    services_ok = all(bool(x.get("ok")) for x in services.values())

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
            "total": user_total,
            "active": user_active,
            "disabled": user_disabled,
            "admin": user_admin,
        },
        "top_actions": [{"action": k, "count": v} for k, v in action_counter.most_common(8)],
        "top_resource_types": [{"resource_type": k, "count": v} for k, v in resource_counter.most_common(8)],
        "top_error_reasons": [{"reason": k, "count": v} for k, v in error_reason_counter.most_common(8)],
        "slow_requests": slow_requests_view,
        "hourly": hourly,
        "services": services,
        "diagnostics": _runtime_diagnostics_summary(),
        "filters": {
            "actor_user_id": (actor_user_id or "").strip(),
            "action_keyword": (action_keyword or "").strip(),
        },
    }


@router.get("/export.csv")
def admin_ops_export_csv(
    request: Request,
    hours: int = 24,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    window_hours = max(1, min(hours, 24 * 7))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    audit_rows = auth_service.list_audit_logs(limit=1000)
    window_rows = _filter_audit_rows(
        rows=audit_rows,
        cutoff=cutoff,
        actor_user_id=actor_user_id,
        action_keyword=action_keyword,
    )

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["section", "key", "value"])
    writer.writerow(["meta", "generated_at", now.isoformat()])
    writer.writerow(["meta", "window_hours", str(window_hours)])
    writer.writerow(["meta", "actor_user_id", (actor_user_id or "").strip()])
    writer.writerow(["meta", "action_keyword", (action_keyword or "").strip()])
    writer.writerow(["summary", "request_count", str(len(window_rows))])
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

    filename = f"ops_report_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


    _require_permission(user, "admin:audit_read", request, "admin")
    window_hours = max(1, min(hours, 24 * 7))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    audit_rows = auth_service.list_audit_logs(limit=2000)
    window_rows = _filter_audit_rows(rows=audit_rows, cutoff=cutoff)
    total = len(window_rows)
    errors = sum(1 for row in window_rows if str(row.get("result", "")).lower() != "success")
    error_rate = (errors / total) * 100 if total > 0 else 0.0

    with _request_metrics_lock:
        req_rows = list(_request_metrics)
    req_window = [r for r in req_rows if _parse_request_ts(str(r.get("ts", ""))) >= cutoff]
    durations = sorted([int(r.get("duration_ms", 0) or 0) for r in req_window])
    p95 = durations[max(0, int(len(durations) * 0.95) - 1)] if durations else 0

    grounding_values = []
    for row in window_rows:
        if str(row.get("action", "")).strip() != "query.run":
            continue
        v = _extract_grounding_support_from_detail(str(row.get("detail", "")))
        if v is not None:
            grounding_values.append(v)
    grounding_avg = (sum(grounding_values) / len(grounding_values)) if grounding_values else 1.0

    alerts = []
    if p95 > int(settings.slo_p95_latency_ms_threshold):
        alerts.append({"type": "latency", "severity": "high", "value": p95, "threshold": int(settings.slo_p95_latency_ms_threshold)})
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


@router.get("/retrieval-profile")
def admin_ops_retrieval_profile(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:audit_read", request, "admin")
    state = get_runtime_state()
    return {
        **state,
        "profiles": [
            {"id": "baseline", "label": "Baseline", "desc": "Conservative retrieval, lower risk."},
            {"id": "advanced", "label": "Advanced", "desc": "Default RAGFlow-like advanced strategy."},
            {"id": "safe", "label": "Safe", "desc": "Local-only retrieval, web fallback disabled."},
        ],
    }


    _require_permission(user, "admin:ops_manage", request, "admin")
    follow_default = bool(payload.get("follow_config_default", False))
    profile = str(payload.get("profile", "") or "")
    state = set_active_profile(profile=profile or "advanced", follow_config_default=follow_default)
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
    enabled = bool(payload.get("enabled", False))
    baseline_percent = int(payload.get("baseline_percent", 0) or 0)
    safe_percent = int(payload.get("safe_percent", 0) or 0)
    seed = str(payload.get("seed", "default") or "default")
    state = set_canary(enabled=enabled, baseline_percent=baseline_percent, safe_percent=safe_percent, seed=seed)
    _audit(
        request,
        action="admin.ops.canary.set",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"enabled={enabled}; baseline={baseline_percent}; safe={safe_percent}; seed={seed}",
    )
    return state


@router.post("/feature-flags")
def admin_ops_set_feature_flags(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    flags = payload.get("flags", {})
    if not isinstance(flags, dict):
        raise HTTPException(status_code=400, detail="flags must be an object")
    state = set_feature_flags({str(k): str(v) for k, v in flags.items()})
    _audit(
        request,
        action="admin.ops.feature_flags.set",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"flags={len(state.get('feature_flags', {}) or {})}",
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


    _require_permission(user, "admin:audit_read", request, "admin")
    rows = read_benchmark_trends(limit=max(1, min(limit, 300)))
    return {"items": rows, "count": len(rows)}


@router.get("/shadow")
def admin_ops_shadow_get(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:audit_read", request, "admin")
    return get_runtime_state().get("shadow", {})


@router.post("/shadow")
def admin_ops_shadow_set(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    state = set_shadow(
        enabled=bool(payload.get("enabled", False)),
        strategy=str(payload.get("strategy", "baseline") or "baseline"),
        sample_percent=int(payload.get("sample_percent", 10) or 10),
        seed=str(payload.get("seed", "shadow") or "shadow"),
    )
    _audit(
        request,
        action="admin.ops.shadow.set",
        resource_type="admin",
        result="success",
        user=user,
        detail=(
            f"enabled={state.get('shadow', {}).get('enabled')}; "
            f"strategy={state.get('shadow', {}).get('strategy')}; "
            f"sample={state.get('shadow', {}).get('sample_percent')}"
        ),
    )
    return state.get("shadow", {})


@router.get("/shadow/runs")
def admin_ops_shadow_runs(request: Request, limit: int = 100, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = read_shadow_runs(limit=max(1, min(limit, 1000)))
    return {"items": rows, "count": len(rows)}


@router.post("/ab-compare")
def admin_ops_ab_compare(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    question = str(payload.get("question", "") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    strategies = payload.get("strategies")
    if not isinstance(strategies, list) or not strategies:
        strategies = ["baseline", "advanced", "safe"]
    normalized = [normalize_retrieval_profile(str(x)) for x in strategies]
    runs: dict[str, Any] = {}
    for s in normalized:
        t0 = time.perf_counter()
        res = run_query(question, use_web_fallback=not profile_force_local_only(s), use_reasoning=False, retrieval_strategy=s)
        runs[s] = {
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            "answer": str(res.get("answer", "") or ""),
            "grounding_support_ratio": float((res.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0),
            "citations": len(res.get("vector_result", {}).get("citations", []) or [])
            + len(res.get("web_result", {}).get("citations", []) or []),
        }
    base = runs.get("advanced") or next(iter(runs.values()))
    diff = {}
    for s, r in runs.items():
        diff[s] = {
            "answer_similarity_vs_advanced": round(text_similarity(str(base.get("answer", "")), str(r.get("answer", ""))), 4),
            "latency_delta_ms_vs_advanced": round(float(r.get("latency_ms", 0.0)) - float(base.get("latency_ms", 0.0)), 2),
            "grounding_delta_vs_advanced": round(
                float(r.get("grounding_support_ratio", 0.0)) - float(base.get("grounding_support_ratio", 0.0)),
                4,
            ),
        }
    return {"question": question, "runs": runs, "diff": diff}


    _require_permission(user, "admin:ops_manage", request, "admin")
    max_questions = max(1, min(int(payload.get("max_questions", 30) or 30), 200))
    strategy = normalize_retrieval_profile(str(payload.get("strategy", "advanced") or "advanced"))
    history_store = _history_store_for_user(user)
    sessions = history_store.list_sessions()
    questions: list[str] = []
    for s in sessions:
        sid = str(s.get("session_id", "") or "")
        if not sid:
            continue
        detail = history_store.get_session(sid) or {}
        for m in detail.get("messages", []) or []:
            if str(m.get("role", "")) == "user":
                q = str(m.get("content", "") or "").strip()
                if q:
                    questions.append(q)
            if len(questions) >= max_questions:
                break
        if len(questions) >= max_questions:
            break
    if not questions:
        raise HTTPException(status_code=400, detail="no historical questions found")

    latencies: list[float] = []
    groundings: list[float] = []
    conflicts = 0
    for q in questions:
        t0 = time.perf_counter()
        res = run_query(q, use_web_fallback=not profile_force_local_only(strategy), use_reasoning=False, retrieval_strategy=strategy)
        latencies.append((time.perf_counter() - t0) * 1000.0)
        groundings.append(float((res.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0))
        all_citations = list(res.get("vector_result", {}).get("citations", []) or []) + list(res.get("web_result", {}).get("citations", []) or [])
        if detect_evidence_conflict(all_citations).get("conflict"):
            conflicts += 1
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "num_questions": len(questions),
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2),
            "p95": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2),
            "avg": round(statistics.mean(latencies), 2),
        },
        "grounding_support_ratio": {"avg": round(statistics.mean(groundings), 4), "min": round(min(groundings), 4)},
        "conflict_rate": round(conflicts / len(questions), 4),
    }
    append_replay_trend(summary)
    _audit(
        request,
        action="admin.ops.replay.run",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"questions={len(questions)}; strategy={strategy}",
    )
    return {"ok": True, "summary": summary}


@router.get("/replay/trends")
def admin_ops_replay_trends(request: Request, limit: int = 30, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = read_replay_trends(limit=max(1, min(limit, 300)))
    return {"items": rows, "count": len(rows)}


    _require_permission(user, "admin:audit_read", request, "admin")
    rows = read_index_freshness(limit=max(1, min(limit, 1000)))
    total = len(rows)
    breached = sum(1 for r in rows if float(r.get("freshness_seconds", 0.0) or 0.0) > float(sla_seconds))
    return {
        "items": rows,
        "count": total,
        "sla_seconds": sla_seconds,
        "breach_count": breached,
        "breach_rate": round((breached / total), 4) if total > 0 else 0.0,
    }


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


    _require_permission(user, "admin:ops_manage", request, "admin")
    query_path = Path("data/eval/benchmark_queries.txt")
    queries = _load_benchmark_queries(query_path, limit=max(1, min(max_queries, 100)))
    if not queries:
        raise HTTPException(status_code=400, detail="benchmark query set is empty")

    latencies: list[float] = []
    support_ratios: list[float] = []
    citation_counts: list[int] = []
    used_profile = normalize_retrieval_profile(strategy)
    for q in queries:
        t0 = time.perf_counter()
        result = run_query(
            q,
            use_web_fallback=True,
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


    _require_permission(user, "admin:audit_read", request, "admin")
    overview = admin_ops_overview(
        request=request,
        hours=hours,
        actor_user_id=None,
        action_keyword=None,
        user=user,
    )
    alerts = admin_ops_alerts(request=request, hours=hours, user=user)
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


