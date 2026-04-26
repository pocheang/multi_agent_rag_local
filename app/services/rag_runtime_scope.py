from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def is_under_path(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved_root = root.resolve()
    except Exception:
        return False
    return resolved == resolved_root or resolved_root in resolved.parents


def hash_secret(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def embedding_settings_signature(settings_data: dict[str, Any]) -> str:
    provider = str(settings_data.get("provider", "") or "").strip().lower()
    embedding_provider = provider
    embedding_model = str(settings_data.get("embedding_model", "") or "").strip()
    base_url = str(settings_data.get("base_url", "") or "").strip().rstrip("/")
    enabled = bool(settings_data.get("enabled", False))
    if provider == "anthropic":
        embedding_provider = ""
        embedding_model = ""
        base_url = ""
    payload = {
        "enabled": enabled,
        "provider": embedding_provider,
        "base_url": base_url,
        "embedding_model": embedding_model,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def query_model_fingerprint(
    *,
    user_api_settings: dict[str, Any] | None,
    global_model_settings: dict[str, Any],
    app_settings: Any,
) -> str:
    safe_user_settings = None
    if isinstance(user_api_settings, dict):
        safe_user_settings = dict(user_api_settings)
        safe_user_settings["api_key_hash"] = hash_secret(str(safe_user_settings.pop("api_key", "") or ""))
    safe_global_settings = dict(global_model_settings or {})
    safe_global_settings["api_key_hash"] = hash_secret(str(safe_global_settings.pop("api_key", "") or ""))
    payload = {
        "user_api_settings": safe_user_settings,
        "global_model_settings": safe_global_settings,
        "settings": {
            "model_backend": str(getattr(app_settings, "model_backend", "") or ""),
            "reasoning_model_backend": str(getattr(app_settings, "reasoning_model_backend", "") or ""),
            "openai_chat_model": str(getattr(app_settings, "openai_chat_model", "") or ""),
            "openai_embed_model": str(getattr(app_settings, "openai_embed_model", "") or ""),
            "openai_base_url": str(getattr(app_settings, "openai_base_url", "") or ""),
            "ollama_chat_model": str(getattr(app_settings, "ollama_chat_model", "") or ""),
            "ollama_embed_model": str(getattr(app_settings, "ollama_embed_model", "") or ""),
            "ollama_base_url": str(getattr(app_settings, "ollama_base_url", "") or ""),
            "anthropic_chat_model": str(getattr(app_settings, "anthropic_chat_model", "") or ""),
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def execution_route_from_result(result: dict[str, Any]) -> str:
    route = str(result.get("route", "") or "unknown")
    vector_result = result.get("vector_result", {}) or {}
    graph_result = result.get("graph_result", {}) or {}
    web_result = result.get("web_result", {}) or {}
    used: list[str] = []
    if int(vector_result.get("retrieved_count", 0) or 0) > 0 or str(vector_result.get("context", "") or "").strip():
        used.append("vector")
    if (
        str(graph_result.get("context", "") or "").strip()
        or graph_result.get("entities")
        or graph_result.get("neighbors")
        or graph_result.get("paths")
    ):
        used.append("graph")
    if bool(web_result.get("used", False)) or str(web_result.get("context", "") or "").strip():
        used.append("web")
    return "+".join(used) if used else route
