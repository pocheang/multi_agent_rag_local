"""Admin settings and configuration routes for the Multi-Agent Local RAG API."""
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import (
    _admin_model_settings_view,
    _api_settings_view,
    _audit,
    _require_user,
    _require_permission,
    _trace_id,
    auth_service,
    query_guard,
    query_result_cache,
    quota_guard,
    runtime_metrics,
    settings,
    shadow_queue,
)
from app.core.config import reload_settings
from app.core.models import clear_model_caches, get_chat_model
from app.core.schemas import (
    AdminModelSettings,
    AdminModelSettingsResponse,
    UserApiSettings,
    UserApiSettingsResponse,
    UserApiSettingsTestResponse,
)
from app.graph.neo4j_client import Neo4jClient
from app.retrievers.vector_store import clear_vector_store_cache
from app.services.alerting import emit_alert
from app.services.background_queue import BackgroundTaskQueue
from app.services.bulkhead import reset_bulkheads
from app.services.index_manager import rebuild_all_vector_index
from app.services.model_config_store import (
    get_global_model_settings,
    normalize_global_model_settings,
    public_global_model_settings,
    save_global_model_settings,
)
from app.services.rag_runtime_scope import embedding_settings_signature
from app.services.network_security import OutboundURLValidationError, validate_api_base_url_for_provider
from app.services.query_guard import QueryLoadGuard
from app.services.query_result_cache import QueryResultCache
from app.services.quota_guard import QuotaGuard
from app.services.request_context import request_context
from app.services.runtime_ops import apply_rollback_profile

router = APIRouter(tags=["admin", "settings"])


@router.get("/admin/model-settings", response_model=AdminModelSettingsResponse)
def admin_get_model_settings(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    return _admin_model_settings_view(get_global_model_settings())


@router.post("/admin/model-settings", response_model=AdminModelSettingsResponse)
def admin_save_model_settings(
    req: AdminModelSettings,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:ops_manage", request, "admin")
    payload = req.model_dump()
    current = get_global_model_settings()
    embedding_before = embedding_settings_signature(current)
    provider = str(payload.get("provider", "") or "").strip().lower()
    incoming_api_key = str(payload.get("api_key", "") or "").strip()
    if not incoming_api_key and provider == str(current.get("provider", "") or "").strip().lower():
        payload["api_key"] = str(current.get("api_key", "") or "")
    try:
        saved = save_global_model_settings(payload)
    except OutboundURLValidationError as e:
        raise HTTPException(status_code=400, detail=f"unsafe base_url: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    clear_model_caches()
    clear_vector_store_cache()
    embedding_after = embedding_settings_signature(saved)
    reindex_result: dict[str, Any] | None = None
    if embedding_after != embedding_before:
        try:
            reindex_result = rebuild_all_vector_index()
            runtime_metrics.inc("admin_model_settings_embedding_reindex_total")
        except Exception as e:
            runtime_metrics.inc("admin_model_settings_embedding_reindex_failed_total")
            emit_alert(
                "admin_model_settings_embedding_reindex_failed",
                {
                    "trace_id": _trace_id(request),
                    "message": f"{type(e).__name__}: {e}",
                    "provider": str(saved.get("provider", "")),
                    "embedding_model": str(saved.get("embedding_model", "")),
                },
            )
            raise HTTPException(status_code=500, detail="model settings saved, but embedding reindex failed")
    _audit(
        request,
        action="admin.model_settings.save",
        resource_type="admin",
        result="success",
        user=user,
        detail=(
            f"enabled={saved['enabled']}; provider={saved['provider']}; chat_model={saved['chat_model']}; "
            f"embedding_reindexed={bool(reindex_result)}; records_reindexed={int((reindex_result or {}).get('records_reindexed', 0) or 0)}"
        ),
    )
    response = _admin_model_settings_view(saved)
    if reindex_result is not None:
        response.settings.embedding_reindexed = True
        response.settings.records_reindexed = int(reindex_result.get("records_reindexed", 0) or 0)
    return response


@router.post("/admin/model-settings/test", response_model=UserApiSettingsTestResponse)
def admin_test_model_settings(
    req: AdminModelSettings,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:ops_manage", request, "admin")
    payload = req.model_dump()
    current = get_global_model_settings()
    provider = str(payload.get("provider", "") or "").strip().lower()
    if not str(payload.get("api_key", "") or "").strip() and provider == str(current.get("provider", "") or "").strip().lower():
        payload["api_key"] = str(current.get("api_key", "") or "")
    try:
        normalized = normalize_global_model_settings({**payload, "enabled": bool(payload.get("enabled", False))})
    except OutboundURLValidationError as e:
        raise HTTPException(status_code=400, detail=f"unsafe base_url: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    started = time.perf_counter()
    api_settings_payload = {
        "provider": normalized["provider"],
        "api_key": normalized["api_key"],
        "base_url": normalized["base_url"],
        "model": normalized["chat_model"],
        "temperature": normalized["temperature"],
        "max_tokens": normalized["max_tokens"],
    }
    try:
        with request_context(timeout_ms=12000, overload_mode=False, api_settings=api_settings_payload):
            model = get_chat_model(temperature=float(normalized["temperature"]))
            probe_result = model.invoke(
                [
                    ("system", "You are a connectivity probe. Reply with exactly OK."),
                    ("human", "Reply with OK."),
                ]
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        preview = str(getattr(probe_result, "content", probe_result) or "").strip().replace("\n", " ")
        if len(preview) > 180:
            preview = preview[:177] + "..."
        _audit(
            request,
            action="admin.model_settings.test",
            resource_type="admin",
            result="success",
            user=user,
            detail=f"provider={normalized['provider']}; model={normalized['chat_model']}; latency_ms={latency_ms}",
        )
        return UserApiSettingsTestResponse(
            ok=True,
            reachable=True,
            provider=normalized["provider"],
            model=normalized["chat_model"],
            latency_ms=latency_ms,
            message="Model connectivity test succeeded",
            preview=preview,
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - started) * 1000)
        reason = str(e) or type(e).__name__
        if len(reason) > 240:
            reason = reason[:237] + "..."
        _audit(
            request,
            action="admin.model_settings.test",
            resource_type="admin",
            result="failed",
            user=user,
            detail=f"provider={normalized['provider']}; model={normalized['chat_model']}; latency_ms={latency_ms}; reason={reason}",
        )
        return UserApiSettingsTestResponse(
            ok=False,
            reachable=False,
            provider=normalized["provider"],
            model=normalized["chat_model"],
            latency_ms=latency_ms,
            message=reason,
            preview="",
        )


@router.post("/admin/config/reload")
def admin_reload_config(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    global settings, query_guard, query_result_cache, quota_guard, shadow_queue
    from app.api.dependencies import auto_ingest_watcher
    settings = reload_settings()
    clear_model_caches()
    clear_vector_store_cache()
    Neo4jClient.close_shared_driver()
    reset_bulkheads()
    shadow_queue.stop(timeout=1.0)
    query_guard = QueryLoadGuard(
        per_user_max_requests=settings.query_rate_limit_max_attempts,
        per_user_window_seconds=settings.query_rate_limit_window_seconds,
        max_concurrent=settings.query_max_concurrent,
        max_waiting=settings.query_max_waiting,
        acquire_timeout_ms=settings.query_acquire_timeout_ms,
        backend=settings.query_guard_backend,
    )
    query_result_cache = QueryResultCache(
        backend=settings.query_result_cache_backend,
        ttl_seconds=settings.query_result_cache_ttl_seconds,
        max_items=settings.query_result_cache_max_items,
        session_ttl_seconds=settings.query_result_session_ttl_seconds,
    )
    quota_guard = QuotaGuard()
    shadow_queue = BackgroundTaskQueue(
        maxsize=settings.shadow_queue_maxsize,
        workers=settings.shadow_queue_workers,
        name="shadow-query",
    )
    shadow_queue.start()
    auto_ingest_watcher.settings = settings
    _audit(
        request,
        action="admin.config.reload",
        resource_type="admin",
        result="success",
        user=user,
        detail="settings_reloaded",
    )
    return {
        "ok": True,
        "reloaded_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": {
            "retrieval_profile": settings.retrieval_profile,
            "top_k": settings.top_k,
            "max_context_chunks": settings.max_context_chunks,
            "retrieval_cache_enabled": settings.retrieval_cache_enabled,
            "dynamic_retrieval_enabled": settings.dynamic_retrieval_enabled,
            "query_rewrite_enabled": settings.query_rewrite_enabled,
            "query_decompose_enabled": settings.query_decompose_enabled,
            "rank_feature_enabled": settings.rank_feature_enabled,
            "global_model_settings": public_global_model_settings(get_global_model_settings()),
        },
    }


@router.post("/admin/ops/rollback")
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


@router.get("/user/api-settings", response_model=UserApiSettingsResponse)
def get_user_api_settings(user: dict[str, Any] = Depends(_require_user)):
    """Get user's API settings"""
    user_id = user["user_id"]
    settings_data = auth_service.get_user_metadata(user_id, "api_settings")

    if settings_data:
        user_settings = UserApiSettings(**settings_data)
    else:
        # Return default settings
        user_settings = UserApiSettings(
            provider="ollama",
            api_key="",
            base_url="http://localhost:11434",
            model="qwen2.5:7b",
            temperature=0.7,
            max_tokens=2048
        )

    return UserApiSettingsResponse(ok=True, settings=_api_settings_view(user_settings))


@router.post("/user/api-settings", response_model=UserApiSettingsResponse)
def save_user_api_settings(
    req_settings: UserApiSettings,
    user: dict[str, Any] = Depends(_require_user)
):
    """Save user's API settings"""
    user_id = user["user_id"]

    provider = str(req_settings.provider or "").strip().lower()
    allowed_providers = {"local", "openai", "anthropic", "deepseek", "ollama", "custom"}
    if provider not in allowed_providers:
        raise HTTPException(status_code=400, detail="unsupported provider")
    normalized_base_url = str(req_settings.base_url or "").strip().rstrip("/")
    if provider == "ollama":
        normalized_base_url = re.sub(r"/v1$", "", normalized_base_url, flags=re.IGNORECASE)
    if provider == "local":
        normalized_base_url = ""
    else:
        if not normalized_base_url:
            raise HTTPException(status_code=400, detail="base_url is required")
        try:
            normalized_base_url = validate_api_base_url_for_provider(normalized_base_url, provider=provider)
        except OutboundURLValidationError as e:
            raise HTTPException(status_code=400, detail=f"unsafe base_url: {e}")
    existing = auth_service.get_user_metadata(user_id, "api_settings")
    incoming_api_key = str(req_settings.api_key or "").strip()
    existing_api_key = ""
    existing_provider = ""
    if isinstance(existing, dict):
        existing_api_key = str(existing.get("api_key", "") or "").strip()
        existing_provider = str(existing.get("provider", "") or "").strip().lower()
    effective_api_key = incoming_api_key
    if (not effective_api_key) and provider != "ollama" and existing_provider == provider:
        effective_api_key = existing_api_key
    if provider not in {"local", "ollama"} and not effective_api_key:
        raise HTTPException(status_code=400, detail="api_key is required for this provider")
    if provider in {"local", "ollama"} and not incoming_api_key:
        effective_api_key = ""
    normalized_settings = req_settings.model_copy(
        update={"provider": provider, "base_url": normalized_base_url, "api_key": effective_api_key}
    )

    # Store settings in user metadata
    auth_service.set_user_metadata(user_id, "api_settings", normalized_settings.model_dump())

    return UserApiSettingsResponse(ok=True, settings=_api_settings_view(normalized_settings))


@router.post("/user/api-settings/test", response_model=UserApiSettingsTestResponse)
def test_user_api_settings(
    req: UserApiSettings,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    provider = str(req.provider or "").strip().lower()
    model_name = str(req.model or "").strip()
    base_url = str(req.base_url or "").strip().rstrip("/")
    api_key = str(req.api_key or "").strip()
    allowed_providers = {"local", "openai", "anthropic", "deepseek", "ollama", "custom"}
    if provider not in allowed_providers:
        raise HTTPException(status_code=400, detail="unsupported provider")
    if provider != "local" and not base_url:
        raise HTTPException(status_code=400, detail="base_url is required")
    if not model_name:
        raise HTTPException(status_code=400, detail="model is required")
    if provider not in {"local", "ollama"} and not api_key:
        raise HTTPException(status_code=400, detail="api_key is required for this provider")
    if provider == "ollama":
        base_url = re.sub(r"/v1$", "", base_url, flags=re.IGNORECASE)
    if provider == "local":
        base_url = ""
    else:
        try:
            base_url = validate_api_base_url_for_provider(base_url, provider=provider)
        except OutboundURLValidationError as e:
            raise HTTPException(status_code=400, detail=f"unsafe base_url: {e}")
    if provider == "anthropic":
        host = str(urlparse(base_url).hostname or "").lower()
        if host and ("anthropic.com" not in host):
            return UserApiSettingsTestResponse(
                ok=False,
                reachable=False,
                provider=provider,
                model=model_name,
                latency_ms=0,
                message="provider=anthropic currently expects official Anthropic endpoint. Use provider=custom for OpenAI-compatible proxy URLs.",
                preview="",
            )

    started = time.perf_counter()
    api_settings_payload = {
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "model": model_name,
        "temperature": float(req.temperature),
        "max_tokens": int(req.max_tokens),
    }

    try:
        with request_context(timeout_ms=12000, overload_mode=False, api_settings=api_settings_payload):
            model = get_chat_model(temperature=float(req.temperature))
            probe_result = model.invoke(
                [
                    ("system", "You are a connectivity probe. Reply with exactly OK."),
                    ("human", "Reply with OK."),
                ]
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        preview = str(getattr(probe_result, "content", probe_result) or "").strip().replace("\n", " ")
        if len(preview) > 180:
            preview = preview[:177] + "..."
        _audit(
            request,
            action="user.api_settings.test",
            resource_type="settings",
            result="success",
            user=user,
            detail=f"provider={provider}; model={model_name}; latency_ms={latency_ms}",
        )
        return UserApiSettingsTestResponse(
            ok=True,
            reachable=True,
            provider=provider,
            model=model_name,
            latency_ms=latency_ms,
            message="API connectivity test succeeded",
            preview=preview,
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - started) * 1000)
        reason = str(e) or type(e).__name__
        if len(reason) > 240:
            reason = reason[:237] + "..."
        _audit(
            request,
            action="user.api_settings.test",
            resource_type="settings",
            result="failed",
            user=user,
            detail=f"provider={provider}; model={model_name}; latency_ms={latency_ms}; reason={reason}",
        )
        return UserApiSettingsTestResponse(
            ok=False,
            reachable=False,
            provider=provider,
            model=model_name,
            latency_ms=latency_ms,
            message=reason,
            preview="",
        )
