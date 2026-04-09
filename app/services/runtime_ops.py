from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
from typing import Any

from app.core.config import get_settings
from app.services.retrieval_profiles import normalize_retrieval_profile

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
    "updated_at": datetime.now(timezone.utc).isoformat(),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        "active_profile": normalize_retrieval_profile(active if isinstance(active, str) and active else _default_profile()),
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


def set_shadow(enabled: bool, strategy: str = "baseline", sample_percent: int = 10, seed: str = "shadow") -> dict[str, Any]:
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
        name = str(k or "").strip().lower()
        rule = str(v or "").strip().lower()
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
    feature = str(name or "").strip().lower()
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
        except Exception:
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
            except Exception:
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
            except Exception:
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
