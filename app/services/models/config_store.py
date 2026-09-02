from __future__ import annotations

import math
import re
from typing import Any

from app.core.config import get_settings
from app.domain.text import normalize_string
from app.services.auth.auth_service import AuthDBService
from app.services.models.catalog import get_model_catalog, provider_defaults, provider_supports_embeddings
from app.services.security.network import OutboundURLValidationError, validate_api_base_url_for_provider

GLOBAL_MODEL_SETTINGS_KEY = "global_model_settings"
USER_API_SETTINGS_KEY = "api_settings"
PROVIDERS = set(get_model_catalog())


class ModelSettingsReindexError(RuntimeError):
    """Keep the persisted settings available when an embedding rebuild fails."""

    def __init__(self, settings_data: dict[str, Any], cause: Exception) -> None:
        self.settings_data = dict(settings_data)
        self.cause = cause
        super().__init__(str(cause))


def default_global_model_settings() -> dict[str, Any]:
    settings = get_settings()
    provider = str(settings.model_backend or "local").strip().lower()
    if provider not in PROVIDERS:
        provider = "local"
    return {
        "enabled": False,
        "provider": provider,
        "api_key": "",
        "base_url": _default_base_url(provider),
        "chat_model": _default_chat_model(provider),
        "reasoning_model": _default_reasoning_model(provider),
        "embedding_model": _default_embedding_model(provider),
        "temperature": 0.7,
        "max_tokens": 2048,
    }


def default_user_api_settings() -> dict[str, Any]:
    return {
        "provider": "local",
        "api_key": "",
        "base_url": "",
        "model": "local-evidence",
        "temperature": 0.7,
        "max_tokens": 2048,
    }


def _default_base_url(provider: str) -> str:
    settings = get_settings()
    provider = normalize_string(provider, lowercase=True)
    if provider == "ollama":
        return str(settings.ollama_base_url or provider_defaults(provider)["base_url"]).rstrip("/")
    if provider == "openai":
        return str(settings.openai_base_url or provider_defaults(provider)["base_url"]).rstrip("/")
    return provider_defaults(provider)["base_url"]


def _default_chat_model(provider: str) -> str:
    settings = get_settings()
    provider = normalize_string(provider, lowercase=True)
    if provider == "ollama":
        return str(settings.ollama_chat_model or provider_defaults(provider)["chat_model"])
    if provider == "openai":
        return str(settings.openai_chat_model or provider_defaults(provider)["chat_model"])
    if provider == "anthropic":
        return str(settings.anthropic_chat_model or provider_defaults(provider)["chat_model"])
    return provider_defaults(provider)["chat_model"]


def _default_reasoning_model(provider: str) -> str:
    settings = get_settings()
    provider = normalize_string(provider, lowercase=True)
    if provider == "ollama":
        return str(settings.ollama_reasoning_model or provider_defaults(provider)["reasoning_model"])
    if provider == "openai":
        return str(
            settings.openai_reasoning_model
            or settings.openai_chat_model
            or provider_defaults(provider)["reasoning_model"]
        )
    if provider == "anthropic":
        return str(
            settings.anthropic_reasoning_model
            or settings.anthropic_chat_model
            or provider_defaults(provider)["reasoning_model"]
        )
    return provider_defaults(provider)["reasoning_model"]


def _default_embedding_model(provider: str) -> str:
    settings = get_settings()
    provider = normalize_string(provider, lowercase=True)
    if not provider_supports_embeddings(provider):
        return ""
    if provider == "ollama":
        return str(settings.ollama_embed_model or provider_defaults(provider)["embedding_model"])
    if provider in {"openai", "custom"}:
        return str(settings.openai_embed_model or provider_defaults("openai")["embedding_model"])
    return provider_defaults(provider)["embedding_model"]


def normalize_persisted_temperature(value: Any, *, default: float = 0.7) -> float:
    try:
        temperature = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(temperature):
        return default
    return min(1.0, max(0.0, temperature))


def _normalize_global_model_settings(raw: dict[str, Any]) -> dict[str, Any]:
    current = default_global_model_settings()
    current.update({k: v for k, v in dict(raw or {}).items() if v is not None})
    provider = str(current.get("provider", "") or "").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError("unsupported provider")
    base_url = str(current.get("base_url", "") or "").strip().rstrip("/")
    if provider == "ollama":
        base_url = base_url.removesuffix("/v1")
    if provider != "local":
        if not base_url:
            raise ValueError("base_url is required")
        base_url = validate_api_base_url_for_provider(base_url, provider=provider)
    else:
        base_url = ""
    chat_model = str(current.get("chat_model", "") or current.get("model", "") or "").strip()
    reasoning_model = str(current.get("reasoning_model", "") or chat_model).strip()
    embedding_model = str(current.get("embedding_model", "") or "").strip()
    if not chat_model:
        raise ValueError("chat_model is required")
    if provider_supports_embeddings(provider) and not embedding_model:
        raise ValueError("embedding_model is required")
    api_key = str(current.get("api_key", "") or "").strip()
    if provider in {"openai", "anthropic", "deepseek", "custom"} and not api_key:
        raise ValueError("api_key is required for this provider")
    if provider in {"local", "ollama"}:
        api_key = ""
    return {
        "enabled": bool(current.get("enabled", False)),
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "chat_model": chat_model,
        "reasoning_model": reasoning_model,
        "embedding_model": embedding_model,
        "temperature": normalize_persisted_temperature(current.get("temperature", 0.7)),
        "max_tokens": min(131072, max(256, int(current.get("max_tokens", 2048) or 2048))),
    }


def get_global_model_settings() -> dict[str, Any]:
    stored = AuthDBService().get_system_metadata(GLOBAL_MODEL_SETTINGS_KEY)
    if not isinstance(stored, dict):
        return default_global_model_settings()
    try:
        return _normalize_global_model_settings(stored)
    except (ValueError, OutboundURLValidationError):
        safe = default_global_model_settings()
        safe["enabled"] = False
        return safe


def _reuse_existing_api_key(raw: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    payload = dict(raw or {})
    provider = normalize_string(payload.get("provider"), lowercase=True)
    incoming_api_key = str(payload.get("api_key", "") or "").strip()
    current_provider = normalize_string(current.get("provider"), lowercase=True)
    if not incoming_api_key and provider == current_provider:
        payload["api_key"] = str(current.get("api_key", "") or "").strip()
    return payload


def save_global_model_settings(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_global_model_settings(_reuse_existing_api_key(raw, get_global_model_settings()))
    AuthDBService().set_system_metadata(GLOBAL_MODEL_SETTINGS_KEY, normalized)
    return normalized


def normalize_global_model_settings(raw: dict[str, Any]) -> dict[str, Any]:
    return _normalize_global_model_settings(raw)


def global_model_settings_probe_payload(raw: dict[str, Any]) -> dict[str, Any]:
    payload = _reuse_existing_api_key(raw, get_global_model_settings())
    payload["enabled"] = bool(payload.get("enabled", False))
    normalized = _normalize_global_model_settings(payload)
    return {
        "provider": normalized["provider"],
        "api_key": normalized["api_key"],
        "base_url": normalized["base_url"],
        "model": normalized["chat_model"],
        "temperature": normalized["temperature"],
        "max_tokens": normalized["max_tokens"],
    }


def get_user_api_settings(user_id: str) -> dict[str, Any]:
    stored = AuthDBService().get_user_metadata(user_id, USER_API_SETTINGS_KEY)
    if not isinstance(stored, dict):
        return default_user_api_settings()
    normalized = dict(stored)
    normalized["temperature"] = normalize_persisted_temperature(normalized.get("temperature", 0.7))
    return normalized


def normalize_user_api_settings(
    raw: dict[str, Any], *, existing: dict[str, Any] | None = None, require_model: bool = False
) -> dict[str, Any]:
    normalized = dict(raw or {})
    provider = normalize_string(normalized.get("provider"), lowercase=True)
    if provider not in PROVIDERS:
        raise ValueError("unsupported provider")

    base_url = str(normalized.get("base_url", "") or "").strip().rstrip("/")
    if provider == "ollama":
        base_url = re.sub(r"/v1$", "", base_url, flags=re.IGNORECASE)
    if provider == "local":
        base_url = ""
    else:
        if not base_url:
            raise ValueError("base_url is required")
        base_url = validate_api_base_url_for_provider(base_url, provider=provider)

    model = str(normalized.get("model", "") or "").strip()
    if require_model and not model:
        raise ValueError("model is required")

    incoming_api_key = str(normalized.get("api_key", "") or "").strip()
    existing_api_key = ""
    existing_provider = ""
    if isinstance(existing, dict):
        existing_api_key = str(existing.get("api_key", "") or "").strip()
        existing_provider = normalize_string(existing.get("provider"), lowercase=True)
    effective_api_key = incoming_api_key
    if not effective_api_key and provider != "ollama" and existing_provider == provider:
        effective_api_key = existing_api_key
    if provider not in {"local", "ollama"} and not effective_api_key:
        raise ValueError("api_key is required for this provider")
    if provider in {"local", "ollama"} and not incoming_api_key:
        effective_api_key = ""

    normalized.update(
        {
            "provider": provider,
            "base_url": base_url,
            "api_key": effective_api_key,
            "temperature": normalize_persisted_temperature(normalized.get("temperature", 0.7)),
        }
    )
    if require_model:
        normalized["model"] = model
    return normalized


def save_user_api_settings(user_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    existing = AuthDBService().get_user_metadata(user_id, USER_API_SETTINGS_KEY)
    normalized = normalize_user_api_settings(raw, existing=existing if isinstance(existing, dict) else None)
    AuthDBService().set_user_metadata(user_id, USER_API_SETTINGS_KEY, normalized)
    return normalized


def user_api_settings_probe_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return normalize_user_api_settings(raw, require_model=True)


def apply_global_model_settings(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Persist global settings and rebuild embeddings only when their signature changed."""
    from app.retrievers.stores.vector import clear_vector_store_cache
    from app.services.documents.index_manager import rebuild_all_vector_index
    from app.services.models.runtime import clear_model_caches
    from app.services.runtime.rag_runtime_scope import embedding_settings_signature

    current = get_global_model_settings()
    embedding_before = embedding_settings_signature(current)
    saved = save_global_model_settings(raw)
    clear_model_caches()
    clear_vector_store_cache()
    if embedding_settings_signature(saved) == embedding_before:
        return saved, None
    try:
        return saved, rebuild_all_vector_index()
    except Exception as error:
        raise ModelSettingsReindexError(saved, error) from error


def mask_api_key(api_key: str) -> str:
    value = str(api_key or "").strip()
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def public_global_model_settings(settings_data: dict[str, Any]) -> dict[str, Any]:
    out = dict(settings_data)
    out["api_key_masked"] = mask_api_key(str(out.pop("api_key", "") or ""))
    return out
