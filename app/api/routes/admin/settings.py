"""Admin settings and configuration routes for the QueryMind API."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import (
    _admin_model_settings_view,
    _api_settings_view,
    _audit,
    _require_permission,
    _require_user,
    _trace_id,
    runtime_metrics,
    shadow_queue,
)
from app.api.transport.errors import bad_request, internal_error
from app.core.config import reload_settings
from app.services.models.runtime import clear_model_caches, probe_chat_model_configuration
from app.api.schemas import (
    AdminModelSettings,
    AdminModelSettingsResponse,
    ModelCatalogResponse,
    UserApiSettings,
    UserApiSettingsResponse,
    UserApiSettingsTestResponse,
)
from app.graph.knowledge.client import Neo4jClient
from app.retrievers.stores.vector import clear_vector_store_cache
from app.services.observability.alerting import emit_alert
from app.services.runtime.background_queue import BackgroundTaskQueue
from app.services.runtime.bulkhead import reset_bulkheads
from app.services.models.catalog import CATALOG_VERSION, get_model_catalog
from app.services.models.config_store import (
    ModelSettingsReindexError,
    apply_global_model_settings,
    get_user_api_settings as get_user_api_settings_service,
    get_global_model_settings,
    global_model_settings_probe_payload,
    public_global_model_settings,
    save_user_api_settings as save_user_api_settings_service,
    user_api_settings_probe_payload,
)
from app.services.security.network import OutboundURLValidationError, validate_api_base_url_for_provider
from app.services.query_guard import QueryLoadGuard
from app.services.runtime.query_result_cache import QueryResultCache
from app.services.security.quota import QuotaGuard
from app.services.runtime.runtime_ops import apply_rollback_profile

router = APIRouter(tags=["admin", "settings"])


@router.get("/model-catalog", response_model=ModelCatalogResponse)
def get_available_model_catalog(user: dict[str, Any] = Depends(_require_user)):
    return ModelCatalogResponse(version=CATALOG_VERSION, providers=get_model_catalog())


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
    try:
        saved, reindex_result = apply_global_model_settings(req.model_dump())
    except ModelSettingsReindexError as e:
        runtime_metrics.inc("admin_model_settings_embedding_reindex_failed_total")
        emit_alert(
            "admin_model_settings_embedding_reindex_failed",
            {
                "trace_id": _trace_id(request),
                "message": f"{type(e.cause).__name__}: {e.cause}",
                "provider": str(e.settings_data.get("provider", "")),
                "embedding_model": str(e.settings_data.get("embedding_model", "")),
            },
        )
        raise internal_error("model settings saved, but embedding reindex failed")
    except OutboundURLValidationError as e:
        raise bad_request(f"unsafe base_url: {e}")
    except ValueError as e:
        raise bad_request(str(e))
    if reindex_result is not None:
        runtime_metrics.inc("admin_model_settings_embedding_reindex_total")
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
    try:
        probe_payload = global_model_settings_probe_payload(req.model_dump())
    except OutboundURLValidationError as e:
        raise bad_request(f"unsafe base_url: {e}")
    except ValueError as e:
        raise bad_request(str(e))
    result = probe_chat_model_configuration(probe_payload, success_message="Model connectivity test succeeded")
    if result["ok"]:
        _audit(request, action="admin.model_settings.test", resource_type="admin", result="success", user=user,
               detail=f"provider={result['provider']}; model={result['model']}; latency_ms={result['latency_ms']}")
    else:
        _audit(request, action="admin.model_settings.test", resource_type="admin", result="failed", user=user,
               detail=f"provider={result['provider']}; model={result['model']}; latency_ms={result['latency_ms']}; reason={result['message']}")
    return UserApiSettingsTestResponse(**result)


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
    query_guard = QueryLoadGuard(per_user_max_requests=settings.query_rate_limit_max_attempts,
        per_user_window_seconds=settings.query_rate_limit_window_seconds, max_concurrent=settings.query_max_concurrent,
        max_waiting=settings.query_max_waiting, acquire_timeout_ms=settings.query_acquire_timeout_ms,
        backend=settings.query_guard_backend)
    query_result_cache = QueryResultCache(backend=settings.query_result_cache_backend,
        ttl_seconds=settings.query_result_cache_ttl_seconds, max_items=settings.query_result_cache_max_items,
        session_ttl_seconds=settings.query_result_session_ttl_seconds)
    quota_guard = QuotaGuard()
    shadow_queue = BackgroundTaskQueue(maxsize=settings.shadow_queue_maxsize,
        workers=settings.shadow_queue_workers, name="shadow-query")
    shadow_queue.start()
    auto_ingest_watcher.settings = settings
    _audit(request, action="admin.config.reload", resource_type="admin", result="success", user=user,
           detail="settings_reloaded")
    return {"ok": True, "reloaded_at": datetime.now(UTC).isoformat(), "snapshot": {
        "retrieval_profile": settings.retrieval_profile, "top_k": settings.top_k,
        "max_context_chunks": settings.max_context_chunks, "retrieval_cache_enabled": settings.retrieval_cache_enabled,
        "dynamic_retrieval_enabled": settings.dynamic_retrieval_enabled,
        "query_rewrite_enabled": settings.query_rewrite_enabled,
        "query_decompose_enabled": settings.query_decompose_enabled,
        "rank_feature_enabled": settings.rank_feature_enabled,
        "global_model_settings": public_global_model_settings(get_global_model_settings()),
    }}


@router.post("/admin/ops/rollback")
def admin_ops_rollback(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    state = apply_rollback_profile()
    _audit(request, action="admin.ops.rollback", resource_type="admin", result="success", user=user,
           detail="runtime_profile_rollback_to_baseline")
    return {"ok": True, "state": state}


@router.get("/user/api-settings", response_model=UserApiSettingsResponse)
def get_user_api_settings(user: dict[str, Any] = Depends(_require_user)):
    """Get user's API settings."""
    user_id = user["user_id"]
    user_settings = UserApiSettings(**get_user_api_settings_service(user_id))
    return UserApiSettingsResponse(ok=True, settings=_api_settings_view(user_settings))


@router.post("/user/api-settings", response_model=UserApiSettingsResponse)
def save_user_api_settings(req_settings: UserApiSettings, request: Request, user: dict[str, Any] = Depends(_require_user)):
    """Save the authenticated user's API settings."""
    user_id = user["user_id"]
    try:
        saved = save_user_api_settings_service(user_id, req_settings.model_dump())
    except OutboundURLValidationError as e:
        raise bad_request(f"unsafe base_url: {e}")
    except ValueError as e:
        raise bad_request(str(e))
    return UserApiSettingsResponse(ok=True, settings=_api_settings_view(UserApiSettings(**saved)))


@router.post("/user/api-settings/test", response_model=UserApiSettingsTestResponse)
def test_user_api_settings(req: UserApiSettings, request: Request, user: dict[str, Any] = Depends(_require_user)):
    """Test the authenticated user's API settings."""
    try:
        probe_payload = user_api_settings_probe_payload(req.model_dump())
    except OutboundURLValidationError as e:
        raise bad_request(f"unsafe base_url: {e}")
    except ValueError as e:
        raise bad_request(str(e))
    result = probe_chat_model_configuration(probe_payload, success_message="API connectivity test succeeded")
    if result["ok"]:
        _audit(request, action="user.api_settings.test", resource_type="settings", result="success", user=user,
               detail=f"provider={result['provider']}; model={result['model']}; latency_ms={result['latency_ms']}")
    else:
        _audit(request, action="user.api_settings.test", resource_type="settings", result="failed", user=user,
               detail=f"provider={result['provider']}; model={result['model']}; latency_ms={result['latency_ms']}; reason={result['message']}")
    return UserApiSettingsTestResponse(**result)
