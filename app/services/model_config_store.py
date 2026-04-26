from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.services.auth_db import AuthDBService
from app.services.network_security import OutboundURLValidationError, validate_api_base_url_for_provider

GLOBAL_MODEL_SETTINGS_KEY = "global_model_settings"
PROVIDERS = {"local", "ollama", "openai", "anthropic", "deepseek", "custom"}


def default_global_model_settings() -> dict[str, Any]:
    settings = get_settings()
    provider = str(settings.model_backend or "ollama").strip().lower()
    if provider not in PROVIDERS:
        provider = "ollama"
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


def _default_base_url(provider: str) -> str:
    settings = get_settings()
    provider = str(provider or "").strip().lower()
    if provider == "ollama":
        return str(settings.ollama_base_url or "http://localhost:11434").rstrip("/")
    if provider == "openai":
        return str(settings.openai_base_url or "https://api.openai.com/v1").rstrip("/")
    if provider == "anthropic":
        return "https://api.anthropic.com/v1"
    if provider == "deepseek":
        return "https://api.deepseek.com/v1"
    return ""


def _default_chat_model(provider: str) -> str:
    settings = get_settings()
    provider = str(provider or "").strip().lower()
    if provider == "local":
        return "local-evidence"
    if provider == "ollama":
        return str(settings.ollama_chat_model or "qwen2.5:7b-instruct")
    if provider in {"openai", "deepseek", "custom"}:
        return str(settings.openai_chat_model or "gpt-5.4-codex") if provider != "deepseek" else "deepseek-chat"
    if provider == "anthropic":
        return str(settings.anthropic_chat_model or "claude-sonnet-4-6")
    return ""


def _default_reasoning_model(provider: str) -> str:
    settings = get_settings()
    provider = str(provider or "").strip().lower()
    if provider == "local":
        return "local-evidence"
    if provider == "ollama":
        return str(settings.ollama_reasoning_model or settings.ollama_chat_model or "qwen2.5:7b-instruct")
    if provider in {"openai", "deepseek", "custom"}:
        return str(settings.openai_reasoning_model or settings.openai_chat_model or "gpt-5.4-codex")
    if provider == "anthropic":
        return str(settings.anthropic_reasoning_model or settings.anthropic_chat_model or "claude-sonnet-4-6")
    return ""


def _default_embedding_model(provider: str) -> str:
    settings = get_settings()
    provider = str(provider or "").strip().lower()
    if provider == "local":
        return "local-hash-384"
    if provider == "ollama":
        return str(settings.ollama_embed_model or "nomic-embed-text")
    return str(settings.openai_embed_model or "text-embedding-3-small")


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
    if provider != "anthropic" and not embedding_model:
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
        "temperature": min(2.0, max(0.0, float(current.get("temperature", 0.7) or 0.7))),
        "max_tokens": min(8192, max(256, int(current.get("max_tokens", 2048) or 2048))),
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


def save_global_model_settings(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_global_model_settings(raw)
    AuthDBService().set_system_metadata(GLOBAL_MODEL_SETTINGS_KEY, normalized)
    return normalized


def normalize_global_model_settings(raw: dict[str, Any]) -> dict[str, Any]:
    return _normalize_global_model_settings(raw)


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
