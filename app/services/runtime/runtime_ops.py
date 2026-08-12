from __future__ import annotations

import hashlib
import json
import socket
import statistics
import threading
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlparse

from app.domain.text import normalize_string
from app.core.config import get_settings
from app.services.retrieval.profiles import normalize_retrieval_profile

_LOCK = threading.Lock()
_STATE: dict[str, Any] = {
    "active_profile": None,  # None means follow settings.retrieval_profile
    "canary": {
        "enabled": False,
        "baseline_percent": 0,
        "safe_percent": 0,
        "seed": "default",
    },
    "shadow": {
        "enabled": False,
        "strategy": "baseline",
        "sample_percent": 10,
        "seed": "shadow",
    },
    "feature_flags": {},
    "updated_at": datetime.now(UTC).isoformat(),
}
_SERVICE_HEALTH_CACHE: dict[str, Any] = {"expires_at": 0.0, "services": {}}
_SERVICE_HEALTH_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def probe_neo4j_ready(neo4j_uri: str) -> dict[str, Any]:
    """Probe the configured graph store without importing a transport route."""
    started = time.perf_counter()
    try:
        parsed = urlparse(neo4j_uri or "")
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 7687)
        with socket.create_connection((host, port), timeout=3):
            pass
        return {"ok": True, "required": True, "latency_ms": int((time.perf_counter() - started) * 1000)}
    except Exception as exc:
        return {
            "ok": False,
            "required": True,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error": str(exc),
        }


def cached_service_health(probes: Mapping[str, Callable[[], dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Cache injected dependency probes for the admin runtime dashboard."""
    now = time.monotonic()
    with _SERVICE_HEALTH_LOCK:
        cached = _SERVICE_HEALTH_CACHE["services"]
        if cached and now < float(_SERVICE_HEALTH_CACHE["expires_at"]):
            return {name: dict(detail) for name, detail in cached.items()}
        services = {name: probe() for name, probe in probes.items()}
        _SERVICE_HEALTH_CACHE["services"] = services
        _SERVICE_HEALTH_CACHE["expires_at"] = now + 30.0
        return {name: dict(detail) for name, detail in services.items()}


def system_resource_snapshot(data_root: Path) -> dict[str, float]:
    """Return process and host utilization without making psutil a hard dependency."""
    try:
        import psutil

        process = psutil.Process()
        disk = psutil.disk_usage(str(data_root.resolve()))
        return {
            "cpu_percent": round(float(psutil.cpu_percent(interval=None)), 1),
            "memory_percent": round(float(psutil.virtual_memory().percent), 1),
            "disk_percent": round(float(disk.percent), 1),
            "process_memory_mb": round(float(process.memory_info().rss) / (1024 * 1024), 1),
        }
    except (ImportError, OSError, RuntimeError):
        return {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "disk_percent": 0.0,
            "process_memory_mb": 0.0,
        }


def build_runtime_snapshot(
    *,
    generated_at: datetime,
    request_rows: list[dict[str, Any]],
    resources: dict[str, float],
    services: dict[str, dict[str, Any]],
    public_model: dict[str, Any],
    model_ready: bool,
    model_required: bool,
    active_requests: int,
) -> dict[str, Any]:
    """Aggregate injected runtime inputs while preserving the admin response schema."""
    durations = [float(row.get("duration_ms", 0) or 0) for row in request_rows]
    errors = sum(1 for row in request_rows if int(row.get("status_code", 0) or 0) >= 400 or row.get("error"))
    total = len(request_rows)
    snapshot_services = {name: dict(detail) for name, detail in services.items()}
    snapshot_services["model"] = {
        "ok": model_ready,
        "required": model_required,
        "message": "configured" if model_ready else "API key is missing",
    }
    blocking = [name for name, detail in snapshot_services.items() if detail.get("required") and not detail.get("ok")]
    return {
        "generated_at": generated_at.isoformat(),
        "status": "healthy" if not blocking else "degraded",
        "blocking_services": blocking,
        "resources": resources,
        "traffic": {
            "window_seconds": 300,
            "requests_total": total,
            "requests_per_second": round(total / 300, 3),
            "avg_response_ms": round(statistics.fmean(durations), 1) if durations else 0.0,
            "p95_response_ms": round(sorted(durations)[max(0, int(len(durations) * 0.95) - 1)], 1)
            if durations
            else 0.0,
            "error_rate_percent": round((errors / total) * 100, 2) if total else 0.0,
            "active_requests": int(active_requests or 0),
        },
        "services": snapshot_services,
        "model": public_model,
    }


def build_ops_overview(
    *,
    generated_at: datetime,
    window_hours: int,
    window_rows: list[dict[str, Any]],
    users: list[dict[str, Any]],
    active_sessions: int,
    request_rows: list[dict[str, Any]],
    services: dict[str, dict[str, Any]],
    diagnostics: dict[str, Any],
    bucket_for_row: Callable[[dict[str, Any]], str],
    actor_user_id: str | None,
    action_keyword: str | None,
) -> dict[str, Any]:
    """Aggregate injected admin data without depending on API dependencies."""
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
    login_success = sum(
        1
        for row in window_rows
        if str(row.get("action", "")) == "auth.login" and str(row.get("result", "")).lower() == "success"
    )
    login_failed = sum(
        1
        for row in window_rows
        if str(row.get("action", "")) == "auth.login" and str(row.get("result", "")).lower() != "success"
    )
    query_requests = sum(1 for row in window_rows if str(row.get("action", "")).startswith("query."))
    upload_requests = sum(
        1
        for row in window_rows
        if str(row.get("action", "")) == "document.upload" and str(row.get("result", "")).lower() == "success"
    )

    bucket_counter: dict[str, dict[str, int]] = {}
    for row in window_rows:
        bucket = bucket_for_row(row)
        slot = bucket_counter.setdefault(bucket, {"count": 0, "errors": 0})
        slot["count"] += 1
        if str(row.get("result", "")).lower() != "success":
            slot["errors"] += 1
    hourly = [
        {"bucket": key, "count": value["count"], "errors": value["errors"]}
        for key, value in sorted(bucket_counter.items(), key=lambda item: item[0])
    ]

    slow_requests = sorted(request_rows, key=lambda row: int(row.get("duration_ms", 0) or 0), reverse=True)[:10]
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
    services_ok = all(bool(item.get("ok")) for item in services.values() if item.get("required", True))

    return {
        "generated_at": generated_at.isoformat(),
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
        "top_resource_types": [
            {"resource_type": key, "count": value} for key, value in resource_counter.most_common(8)
        ],
        "top_error_reasons": [{"reason": key, "count": value} for key, value in error_reason_counter.most_common(8)],
        "slow_requests": slow_requests_view,
        "hourly": hourly,
        "services": services,
        "diagnostics": diagnostics,
        "filters": {
            "actor_user_id": (actor_user_id or "").strip(),
            "action_keyword": (action_keyword or "").strip(),
        },
    }


def build_ops_alerts(
    *,
    generated_at: datetime,
    window_hours: int,
    window_rows: list[dict[str, Any]],
    request_rows: list[dict[str, Any]],
    extract_grounding_support: Callable[[str], float | None],
    p95_latency_threshold: int,
    error_rate_threshold: float,
    grounding_threshold: float,
) -> dict[str, Any]:
    """Evaluate existing SLO thresholds against injected admin telemetry."""
    total = len(window_rows)
    errors = sum(1 for row in window_rows if str(row.get("result", "")).lower() != "success")
    error_rate = (errors / total) * 100 if total > 0 else 0.0
    durations = sorted(int(row.get("duration_ms", 0) or 0) for row in request_rows)
    p95 = durations[max(0, int(len(durations) * 0.95) - 1)] if durations else 0
    grounding_values = [
        value
        for row in window_rows
        if str(row.get("action", "")).strip() == "query.run"
        if (value := extract_grounding_support(str(row.get("detail", "")))) is not None
    ]
    grounding_avg = (sum(grounding_values) / len(grounding_values)) if grounding_values else 1.0

    alerts: list[dict[str, Any]] = []
    if p95 > p95_latency_threshold:
        alerts.append({"type": "latency", "severity": "high", "value": p95, "threshold": p95_latency_threshold})
    if error_rate > error_rate_threshold:
        alerts.append(
            {"type": "error_rate", "severity": "high", "value": round(error_rate, 2), "threshold": error_rate_threshold}
        )
    if grounding_avg < grounding_threshold:
        alerts.append(
            {
                "type": "grounding_support",
                "severity": "medium",
                "value": round(grounding_avg, 3),
                "threshold": grounding_threshold,
            }
        )
    return {
        "generated_at": generated_at.isoformat(),
        "window_hours": window_hours,
        "status": "alerting" if alerts else "ok",
        "slo": {
            "p95_latency_ms": p95,
            "error_rate_percent": round(error_rate, 2),
            "grounding_support_ratio_avg": round(grounding_avg, 3),
        },
        "alerts": alerts,
    }


def _default_profile() -> str:
    return normalize_retrieval_profile(None)


def _effective_active_profile() -> str:
    with _LOCK:
        profile = _STATE.get("active_profile")
    return normalize_retrieval_profile(profile if isinstance(profile, str) and profile else _default_profile())


def get_runtime_state() -> dict[str, Any]:
    with _LOCK:
        canary = dict(_STATE.get("canary", {}) or {})
        shadow = dict(_STATE.get("shadow", {}) or {})
        feature_flags = dict(_STATE.get("feature_flags", {}) or {})
        active = _STATE.get("active_profile")
        updated = str(_STATE.get("updated_at", "") or "")
    return {
        "active_profile": normalize_retrieval_profile(
            active if isinstance(active, str) and active else _default_profile()
        ),
        "config_default_profile": _default_profile(),
        "follow_config_default": not bool(active),
        "canary": {
            "enabled": bool(canary.get("enabled", False)),
            "baseline_percent": int(canary.get("baseline_percent", 0) or 0),
            "safe_percent": int(canary.get("safe_percent", 0) or 0),
            "seed": str(canary.get("seed", "default") or "default"),
        },
        "shadow": {
            "enabled": bool(shadow.get("enabled", False)),
            "strategy": normalize_retrieval_profile(str(shadow.get("strategy", "baseline") or "baseline")),
            "sample_percent": max(0, min(int(shadow.get("sample_percent", 10) or 10), 100)),
            "seed": str(shadow.get("seed", "shadow") or "shadow"),
        },
        "feature_flags": feature_flags,
        "updated_at": updated or _now_iso(),
    }


def set_active_profile(profile: str, follow_config_default: bool = False) -> dict[str, Any]:
    normalized = normalize_retrieval_profile(profile)
    with _LOCK:
        _STATE["active_profile"] = None if follow_config_default else normalized
        _STATE["updated_at"] = _now_iso()
    return get_runtime_state()


def set_canary(enabled: bool, baseline_percent: int, safe_percent: int, seed: str = "default") -> dict[str, Any]:
    baseline = max(0, min(int(baseline_percent), 100))
    safe = max(0, min(int(safe_percent), 100))
    if baseline + safe > 100:
        safe = max(0, 100 - baseline)
    with _LOCK:
        _STATE["canary"] = {
            "enabled": bool(enabled),
            "baseline_percent": baseline,
            "safe_percent": safe,
            "seed": str(seed or "default"),
        }
        _STATE["updated_at"] = _now_iso()
    return get_runtime_state()


def apply_rollback_profile() -> dict[str, Any]:
    with _LOCK:
        _STATE["active_profile"] = "baseline"
        _STATE["canary"] = {
            "enabled": False,
            "baseline_percent": 0,
            "safe_percent": 0,
            "seed": "default",
        }
        _STATE["shadow"] = {
            "enabled": False,
            "strategy": "baseline",
            "sample_percent": 10,
            "seed": "shadow",
        }
        _STATE["feature_flags"] = {}
        _STATE["updated_at"] = _now_iso()
    return get_runtime_state()


def set_shadow(
    enabled: bool, strategy: str = "baseline", sample_percent: int = 10, seed: str = "shadow"
) -> dict[str, Any]:
    with _LOCK:
        _STATE["shadow"] = {
            "enabled": bool(enabled),
            "strategy": normalize_retrieval_profile(strategy),
            "sample_percent": max(0, min(int(sample_percent), 100)),
            "seed": str(seed or "shadow"),
        }
        _STATE["updated_at"] = _now_iso()
    return get_runtime_state()


def set_feature_flags(flags: dict[str, str]) -> dict[str, Any]:
    normalized: dict[str, str] = {}
    for k, v in (flags or {}).items():
        name = normalize_string(k, lowercase=True)
        rule = normalize_string(v, lowercase=True)
        if not name:
            continue
        if rule in {"on", "off"} or rule.startswith("pct:"):
            normalized[name] = rule
    with _LOCK:
        _STATE["feature_flags"] = normalized
        _STATE["updated_at"] = _now_iso()
    return get_runtime_state()


def _feature_flags_from_settings() -> dict[str, str]:
    raw = str(get_settings().feature_flags or "").strip()
    if not raw:
        return {}
    out: dict[str, str] = {}
    pairs = [x.strip() for x in raw.split(",") if x.strip()]
    for p in pairs:
        if "=" not in p:
            continue
        n, r = p.split("=", 1)
        name = n.strip().lower()
        rule = r.strip().lower()
        if not name:
            continue
        if rule in {"on", "off"} or rule.startswith("pct:"):
            out[name] = rule
    return out


def feature_enabled(
    name: str,
    *,
    user_id: str = "",
    session_id: str = "",
    question: str = "",
) -> bool:
    feature = normalize_string(name, lowercase=True)
    if not feature:
        return False
    state = get_runtime_state()
    flags = dict(state.get("feature_flags", {}) or {})
    if feature not in flags:
        flags = _feature_flags_from_settings()
    rule = str(flags.get(feature, "") or "").strip().lower()
    if not rule:
        return True
    if rule == "on":
        return True
    if rule == "off":
        return False
    if rule.startswith("pct:"):
        try:
            pct = max(0, min(int(rule.split(":", 1)[1]), 100))
        except (ValueError, IndexError):
            return True
        seed = str(get_settings().feature_flag_seed or "feature")
        key = f"{seed}|{feature}|{user_id}|{session_id}|{question}"
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        bucket = int(h[:8], 16) % 100
        return bucket < pct
    return True


def choose_shadow(
    *,
    user_id: str,
    session_id: str,
    question: str,
) -> tuple[bool, str | None]:
    state = get_runtime_state()
    shadow = state.get("shadow", {}) or {}
    if not bool(shadow.get("enabled", False)):
        return False, None
    sample = max(0, min(int(shadow.get("sample_percent", 0) or 0), 100))
    if sample <= 0:
        return False, None
    seed = str(shadow.get("seed", "shadow") or "shadow")
    key = f"{seed}|{user_id}|{session_id}|{question}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    bucket = int(h[:8], 16) % 100
    if bucket >= sample:
        return False, None
    return True, normalize_retrieval_profile(str(shadow.get("strategy", "baseline") or "baseline"))


def resolve_profile_for_request(
    explicit_profile: str | None,
    *,
    user_id: str = "",
    session_id: str = "",
    question: str = "",
) -> tuple[str, dict[str, Any]]:
    if explicit_profile:
        normalized = normalize_retrieval_profile(explicit_profile)
        return normalized, {"reason": "explicit", "bucket": None}

    state = get_runtime_state()
    active = normalize_retrieval_profile(state.get("active_profile"))
    canary = state.get("canary", {}) or {}
    if not bool(canary.get("enabled", False)):
        return active, {"reason": "active_profile", "bucket": None}

    baseline_pct = max(0, min(int(canary.get("baseline_percent", 0) or 0), 100))
    safe_pct = max(0, min(int(canary.get("safe_percent", 0) or 0), 100))
    seed = str(canary.get("seed", "default") or "default")
    key = f"{seed}|{user_id}|{session_id}|{question}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    bucket = int(h[:8], 16) % 100
    if bucket < baseline_pct:
        return "baseline", {"reason": "canary_baseline", "bucket": bucket}
    if bucket < baseline_pct + safe_pct:
        return "safe", {"reason": "canary_safe", "bucket": bucket}
    return active, {"reason": "canary_active", "bucket": bucket}


def benchmark_trend_path() -> Path:
    data_root = get_settings().app_db_path.parent
    return data_root / "eval" / "benchmark_trends.jsonl"


def shadow_log_path() -> Path:
    data_root = get_settings().app_db_path.parent
    return data_root / "eval" / "shadow_runs.jsonl"


def index_freshness_path() -> Path:
    data_root = get_settings().app_db_path.parent
    return data_root / "eval" / "index_freshness.jsonl"


def replay_trend_path() -> Path:
    data_root = get_settings().app_db_path.parent
    return data_root / "eval" / "replay_trends.jsonl"


def append_benchmark_trend(entry: dict[str, Any]) -> None:
    p = benchmark_trend_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(entry)
    payload.setdefault("created_at", _now_iso())
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def run_benchmark(
    *,
    max_queries: int,
    strategy: str,
    execute_query: Callable[[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Run the configured benchmark through the supplied pipeline adapter."""
    query_path = Path("data/eval/benchmark_queries.txt")
    if not query_path.exists():
        queries: list[str] = []
    else:
        queries = [line.strip() for line in query_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    queries = queries[: max(1, min(int(max_queries), 100))]
    if not queries:
        raise ValueError("benchmark query set is empty")

    used_profile = normalize_retrieval_profile(strategy)
    latencies: list[float] = []
    support_ratios: list[float] = []
    citation_counts: list[int] = []
    for question in queries:
        started = time.perf_counter()
        result = execute_query(question, used_profile)
        latencies.append((time.perf_counter() - started) * 1000.0)
        support_ratios.append(float((result.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0))
        citation_counts.append(
            len(result.get("vector_result", {}).get("citations", []) or [])
            + len(result.get("web_result", {}).get("citations", []) or [])
        )

    entry = {
        "created_at": _now_iso(),
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
    return entry


def compare_retrieval_profiles(
    *,
    question: str,
    strategies: Any,
    execute_query: Callable[[str, str], dict[str, Any]],
    similarity: Callable[[str, str], float],
) -> dict[str, Any]:
    """Execute a controlled profile comparison via the supplied pipeline adapter."""
    if not question:
        raise ValueError("question is required")
    raw_strategies = strategies if isinstance(strategies, list) and strategies else ["baseline", "advanced", "safe"]
    normalized = [normalize_retrieval_profile(str(item)) for item in raw_strategies]
    runs: dict[str, Any] = {}
    for strategy in normalized:
        started = time.perf_counter()
        result = execute_query(question, strategy)
        runs[strategy] = {
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 2),
            "answer": str(result.get("answer", "") or ""),
            "grounding_support_ratio": float((result.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0),
            "citations": len(result.get("vector_result", {}).get("citations", []) or [])
            + len(result.get("web_result", {}).get("citations", []) or []),
        }
    base = runs.get("advanced") or next(iter(runs.values()))
    diff = {
        strategy: {
            "answer_similarity_vs_advanced": round(
                similarity(str(base.get("answer", "")), str(row.get("answer", ""))), 4
            ),
            "latency_delta_ms_vs_advanced": round(
                float(row.get("latency_ms", 0.0)) - float(base.get("latency_ms", 0.0)), 2
            ),
            "grounding_delta_vs_advanced": round(
                float(row.get("grounding_support_ratio", 0.0))
                - float(base.get("grounding_support_ratio", 0.0)),
                4,
            ),
        }
        for strategy, row in runs.items()
    }
    return {"question": question, "runs": runs, "diff": diff}


class _HistoryStore(Protocol):
    def list_sessions(self) -> list[dict[str, Any]]: ...

    def get_session(self, session_id: str) -> dict[str, Any] | None: ...


def _collect_replay_questions(*, history_store: _HistoryStore, max_questions: int) -> list[str]:
    """Collect bounded historical user questions in their persisted order."""
    max_questions = max(1, min(int(max_questions or 30), 200))
    questions: list[str] = []
    for session in history_store.list_sessions():
        session_id = str(session.get("session_id", "") or "")
        if not session_id:
            continue
        detail = history_store.get_session(session_id) or {}
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
        raise ValueError("no historical questions found")
    return questions


def build_replay_summary(*, history_store: _HistoryStore, max_questions: int, strategy: str) -> dict[str, Any]:
    """Return replay candidate metadata for callers that only need a preview."""
    questions = _collect_replay_questions(history_store=history_store, max_questions=max_questions)
    return {
        "created_at": _now_iso(),
        "strategy": normalize_retrieval_profile(strategy),
        "num_questions": len(questions),
    }


def run_replay(
    *,
    history_store: _HistoryStore,
    max_questions: int,
    strategy: str,
    execute_query: Callable[[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Replay historical questions through an injected standard pipeline adapter."""
    questions = _collect_replay_questions(history_store=history_store, max_questions=max_questions)
    used_profile = normalize_retrieval_profile(strategy)
    latencies: list[float] = []
    support_ratios: list[float] = []
    citation_counts: list[int] = []
    for question in questions:
        started = time.perf_counter()
        result = execute_query(question, used_profile)
        latencies.append((time.perf_counter() - started) * 1000.0)
        support_ratios.append(float((result.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0))
        citation_counts.append(
            len(result.get("vector_result", {}).get("citations", []) or [])
            + len(result.get("web_result", {}).get("citations", []) or [])
        )
    entry = {
        "created_at": _now_iso(),
        "strategy": used_profile,
        "num_questions": len(questions),
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
    append_replay_trend(entry)
    return entry


def apply_replay_autotune(
    *, target_p95: float, target_grounding: float, settings: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply the existing in-memory retrieval tuning policy to the latest replay trend."""
    trends = read_replay_trends(limit=1)
    if not trends:
        raise ValueError("no replay trends found; run replay first")
    latest = trends[-1]
    latest_p95 = float((latest.get("latency_ms", {}) or {}).get("p95", 0.0) or 0.0)
    latest_grounding = float((latest.get("grounding_support_ratio", {}) or {}).get("avg", 0.0) or 0.0)
    patch: dict[str, Any] = {}
    if latest_p95 > target_p95:
        patch["TOP_K"] = max(2, int(settings.top_k) - 1)
        patch["MAX_CONTEXT_CHUNKS"] = max(3, int(settings.max_context_chunks) - 1)
    if latest_grounding < target_grounding:
        patch["TOP_K"] = max(int(patch.get("TOP_K", settings.top_k)), int(settings.top_k) + 1)
        patch["RANK_FEATURE_ENABLED"] = True
        patch["DYNAMIC_RETRIEVAL_ENABLED"] = True
    if not patch:
        return latest, {"status": "no_change"}
    if "TOP_K" in patch:
        settings.top_k = int(patch["TOP_K"])
    if "MAX_CONTEXT_CHUNKS" in patch:
        settings.max_context_chunks = int(patch["MAX_CONTEXT_CHUNKS"])
    if "RANK_FEATURE_ENABLED" in patch:
        settings.rank_feature_enabled = bool(patch["RANK_FEATURE_ENABLED"])
    if "DYNAMIC_RETRIEVAL_ENABLED" in patch:
        settings.dynamic_retrieval_enabled = bool(patch["DYNAMIC_RETRIEVAL_ENABLED"])
    return latest, patch


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(payload)
    row.setdefault("created_at", _now_iso())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_shadow_run(entry: dict[str, Any]) -> None:
    _append_jsonl(shadow_log_path(), entry)


def append_replay_trend(entry: dict[str, Any]) -> None:
    _append_jsonl(replay_trend_path(), entry)


def append_index_freshness(entry: dict[str, Any]) -> None:
    _append_jsonl(index_freshness_path(), entry)


def read_benchmark_trends(limit: int = 30) -> list[dict[str, Any]]:
    p = benchmark_trend_path()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                rows.append(json.loads(s))
            except json.JSONDecodeError:
                continue
    if limit <= 0:
        return rows
    return rows[-limit:]


def _read_jsonl(path: Path, limit: int = 30) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                rows.append(json.loads(s))
            except json.JSONDecodeError:
                continue
    if limit <= 0:
        return rows
    return rows[-limit:]


def read_shadow_runs(limit: int = 100) -> list[dict[str, Any]]:
    return _read_jsonl(shadow_log_path(), limit=limit)


def read_replay_trends(limit: int = 30) -> list[dict[str, Any]]:
    return _read_jsonl(replay_trend_path(), limit=limit)


def read_index_freshness(limit: int = 200) -> list[dict[str, Any]]:
    return _read_jsonl(index_freshness_path(), limit=limit)
