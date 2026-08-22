from __future__ import annotations

from copy import deepcopy
from typing import Any

CATALOG_VERSION = "2026-07-01"

_MODEL_CATALOG: dict[str, dict[str, Any]] = {
    "local": {
        "label": "Local runtime",
        "base_url": "",
        "default_chat_model": "local-evidence",
        "default_reasoning_model": "local-evidence",
        "default_embedding_model": "local-hash-384",
        "requires_api_key": False,
        "supports_embeddings": True,
        "api_style": "local",
        "models": [{"id": "local-evidence", "label": "Local Evidence", "roles": ["chat", "reasoning"]}],
    },
    "ollama": {
        "label": "Ollama",
        "base_url": "http://localhost:11434",
        "default_chat_model": "qwen3:14b",
        "default_reasoning_model": "deepseek-r1:32b",
        "default_embedding_model": "nomic-embed-text",
        "requires_api_key": False,
        "supports_embeddings": True,
        "api_style": "ollama",
        "models": [
            {"id": "qwen3:14b", "label": "Qwen 3 14B", "roles": ["chat"]},
            {"id": "deepseek-r1:32b", "label": "DeepSeek R1 32B", "roles": ["chat", "reasoning"]},
            {"id": "nomic-embed-text", "label": "Nomic Embed Text", "roles": ["embedding"]},
        ],
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_chat_model": "gpt-5.5",
        "default_reasoning_model": "gpt-5.5",
        "default_embedding_model": "text-embedding-3-small",
        "requires_api_key": True,
        "supports_embeddings": True,
        "api_style": "openai",
        "note": "GPT-5.5 uses reasoning effort; it does not use a separate -thinking model ID.",
        "models": [
            {"id": "gpt-5.5", "label": "GPT-5.5", "roles": ["chat", "reasoning"], "recommended": True},
            {"id": "gpt-5-mini", "label": "GPT-5 mini", "roles": ["chat", "reasoning"]},
            {"id": "text-embedding-3-large", "label": "Text Embedding 3 Large", "roles": ["embedding"]},
            {"id": "text-embedding-3-small", "label": "Text Embedding 3 Small", "roles": ["embedding"]},
        ],
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_chat_model": "deepseek-v4-flash",
        "default_reasoning_model": "deepseek-v4-pro",
        "default_embedding_model": "",
        "requires_api_key": True,
        "supports_embeddings": False,
        "api_style": "openai",
        "note": "DeepSeek V4 switches thinking mode through request options. Embeddings stay on the existing pipeline.",
        "models": [
            {
                "id": "deepseek-v4-flash",
                "label": "DeepSeek V4 Flash",
                "roles": ["chat", "reasoning"],
                "recommended": True,
            },
            {"id": "deepseek-v4-pro", "label": "DeepSeek V4 Pro", "roles": ["chat", "reasoning"]},
            {
                "id": "deepseek-chat",
                "label": "DeepSeek Chat (deprecated)",
                "roles": ["chat"],
                "deprecated_after": "2026-07-24T15:59:00Z",
            },
            {
                "id": "deepseek-reasoner",
                "label": "DeepSeek Reasoner (deprecated)",
                "roles": ["reasoning"],
                "deprecated_after": "2026-07-24T15:59:00Z",
            },
        ],
    },
    "anthropic": {
        "label": "Anthropic",
        "base_url": "https://api.anthropic.com",
        "default_chat_model": "claude-sonnet-5",
        "default_reasoning_model": "claude-fable-5",
        "default_embedding_model": "",
        "requires_api_key": True,
        "supports_embeddings": False,
        "api_style": "anthropic",
        "note": "Anthropic does not provide embeddings; the existing embedding pipeline remains active.",
        "models": [
            {"id": "claude-sonnet-5", "label": "Claude Sonnet 5", "roles": ["chat", "reasoning"], "recommended": True},
            {"id": "claude-fable-5", "label": "Claude Fable 5", "roles": ["chat", "reasoning"]},
            {"id": "claude-opus-4-8", "label": "Claude Opus 4.8", "roles": ["chat", "reasoning"]},
            {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6", "roles": ["chat", "reasoning"]},
            {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5", "roles": ["chat", "reasoning"]},
        ],
    },
    "custom": {
        "label": "Custom compatible API",
        "base_url": "",
        "default_chat_model": "",
        "default_reasoning_model": "",
        "default_embedding_model": "",
        "requires_api_key": True,
        "supports_embeddings": True,
        "api_style": "openai",
        "models": [],
    },
}


def get_model_catalog() -> dict[str, dict[str, Any]]:
    return deepcopy(_MODEL_CATALOG)


def provider_metadata(provider: str) -> dict[str, Any]:
    key = str(provider or "").strip().lower()
    if key not in _MODEL_CATALOG:
        raise ValueError("unsupported provider")
    return deepcopy(_MODEL_CATALOG[key])


def provider_defaults(provider: str) -> dict[str, str]:
    metadata = provider_metadata(provider)
    return {
        "base_url": str(metadata["base_url"]),
        "chat_model": str(metadata["default_chat_model"]),
        "reasoning_model": str(metadata["default_reasoning_model"]),
        "embedding_model": str(metadata["default_embedding_model"]),
    }


def provider_supports_embeddings(provider: str) -> bool:
    return bool(provider_metadata(provider)["supports_embeddings"])
