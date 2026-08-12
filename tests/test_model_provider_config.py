from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.deps.query import _user_api_settings_for_runtime
from app.core.models import (
    AnthropicRelayChatModel,
    OutboundRedactedChatModel,
    OutboundRedactedEmbeddings,
    _build_chat_model_cached,
    _global_embedding_override,
    get_chat_model,
    get_reasoning_model,
)
from app.core.schemas import (
    AdminModelSettings,
    AdminModelSettingsView,
    UserApiSettings,
    UserApiSettingsView,
)
from app.services.model_catalog import get_model_catalog, provider_defaults
from app.services.model_config_store import (
    default_global_model_settings,
    get_user_api_settings,
    normalize_global_model_settings,
)
from app.services.network_security import validate_api_base_url_for_provider
from app.services.request_context import request_context


def test_anthropic_base_url_uses_sdk_root_path():
    assert (
        validate_api_base_url_for_provider("https://api.anthropic.com/v1", provider="anthropic")
        == "https://api.anthropic.com"
    )
    assert validate_api_base_url_for_provider("https://cc-vibe.com", provider="anthropic") == "https://cc-vibe.com"


def test_openai_compatible_root_base_url_gets_v1_path():
    assert validate_api_base_url_for_provider("https://example.com", provider="custom") == "https://example.com/v1"


def test_schema_defaults_use_local_provider():
    assert UserApiSettings().provider == "local"
    assert AdminModelSettings().provider == "local"


def test_model_setting_schemas_reject_temperature_above_one():
    for schema in (
        AdminModelSettings,
        AdminModelSettingsView,
        UserApiSettings,
        UserApiSettingsView,
    ):
        with pytest.raises(ValidationError):
            schema(temperature=1.1)


def test_legacy_global_temperature_is_normalized_to_one(monkeypatch):
    monkeypatch.setattr(
        "app.services.model_config_store.default_global_model_settings",
        lambda: {
            "enabled": False,
            "provider": "local",
            "api_key": "",
            "base_url": "",
            "chat_model": "local-evidence",
            "reasoning_model": "local-evidence",
            "embedding_model": "local-hash-384",
            "temperature": 0.7,
            "max_tokens": 2048,
        },
    )
    normalized = normalize_global_model_settings({"provider": "local", "temperature": 1.7})

    assert normalized["temperature"] == 1.0


@pytest.mark.parametrize(
    ("temperature", "expected"),
    [
        (0, 0.0),
        (-0.5, 0.0),
        (float("nan"), 0.7),
        (float("inf"), 0.7),
        (float("-inf"), 0.7),
    ],
)
def test_global_temperature_preserves_zero_and_safely_normalizes_invalid_values(
    monkeypatch, temperature, expected
):
    monkeypatch.setattr(
        "app.services.model_config_store.default_global_model_settings",
        lambda: {
            "enabled": False,
            "provider": "local",
            "api_key": "",
            "base_url": "",
            "chat_model": "local-evidence",
            "reasoning_model": "local-evidence",
            "embedding_model": "local-hash-384",
            "temperature": 0.7,
            "max_tokens": 2048,
        },
    )

    normalized = normalize_global_model_settings({"provider": "local", "temperature": temperature})

    assert normalized["temperature"] == expected


def test_custom_runtime_temperature_is_bounded_without_narrowing_openai(monkeypatch):
    captured: list[dict[str, object]] = []

    monkeypatch.setattr("app.core.models.get_global_model_settings", lambda: {"enabled": False})
    monkeypatch.setattr(
        "app.core.models._build_chat_model_cached",
        lambda **kwargs: captured.append(kwargs) or SimpleNamespace(),
    )

    for provider in ("custom", "openai"):
        with request_context(
            timeout_ms=12000,
            overload_mode=False,
            api_settings={
                "provider": provider,
                "api_key": "sk-test",
                "base_url": "https://example.com/v1",
                "model": "test-model",
                "temperature": 2.0,
                "max_tokens": 2048,
            },
        ):
            get_chat_model(temperature=2.0)

    assert [call["temperature"] for call in captured] == [1.0, 2.0]


def test_custom_claude_request_keeps_custom_temperature_policy_for_chat_and_reasoning(monkeypatch):
    captured: list[dict[str, object]] = []
    monkeypatch.setattr("app.core.models.get_global_model_settings", lambda: {"enabled": False})
    monkeypatch.setattr(
        "app.core.models._build_chat_model_cached",
        lambda **kwargs: captured.append(kwargs) or SimpleNamespace(),
    )

    with request_context(
        timeout_ms=12000,
        overload_mode=False,
        api_settings={
            "provider": "custom",
            "api_key": "sk-test",
            "base_url": "https://cc-vibe.com",
            "model": "claude-opus-4-8",
            "temperature": 2.0,
            "max_tokens": 2048,
        },
    ):
        get_chat_model()
        get_reasoning_model()

    assert [
        (call["provider"], call["backend"], call["temperature"])
        for call in captured
    ] == [
        ("custom", "anthropic", 1.0),
        ("custom", "anthropic", 1.0),
    ]


def test_custom_claude_global_override_keeps_custom_temperature_policy_for_chat_and_reasoning(monkeypatch):
    captured: list[dict[str, object]] = []
    monkeypatch.setattr("app.core.models._local_backend_forced", lambda: False)
    monkeypatch.setattr(
        "app.core.models.get_global_model_settings",
        lambda: {
            "enabled": True,
            "provider": "custom",
            "api_key": "sk-test",
            "base_url": "https://cc-vibe.com/v1",
            "chat_model": "claude-sonnet-4-6",
            "reasoning_model": "claude-opus-4-8",
            "embedding_model": "text-embedding-3-small",
            "temperature": 2.0,
            "max_tokens": 2048,
        },
    )
    monkeypatch.setattr(
        "app.core.models._build_chat_model_cached",
        lambda **kwargs: captured.append(kwargs) or SimpleNamespace(),
    )

    get_chat_model()
    get_reasoning_model()

    assert [
        (call["provider"], call["backend"], call["temperature"])
        for call in captured
    ] == [
        ("custom", "anthropic", 1.0),
        ("custom", "anthropic", 1.0),
    ]


def test_legacy_user_temperature_is_normalized_before_runtime_model_construction(monkeypatch):
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.services.model_config_store.AuthDBService.get_user_metadata",
        lambda _service, _user_id, _key: {
            "provider": "local",
            "api_key": "",
            "base_url": "",
            "model": "local-evidence",
            "temperature": 1.4,
            "max_tokens": 2048,
        },
    )
    monkeypatch.setattr("app.core.models.get_global_model_settings", lambda: {"enabled": False})
    monkeypatch.setattr(
        "app.core.models._build_chat_model_cached",
        lambda **kwargs: captured.append(kwargs) or SimpleNamespace(),
    )

    api_settings = get_user_api_settings("u-test")
    with request_context(timeout_ms=12000, overload_mode=False, api_settings=api_settings):
        get_chat_model()

    assert api_settings["temperature"] == 1.0
    assert captured[0]["temperature"] == 1.0


def test_authenticated_query_runtime_normalizes_only_legacy_user_temperature():
    class AuthService:
        def get_user_metadata(self, user_id, key):
            assert user_id == "u-legacy"
            assert key == "api_settings"
            return {
                "provider": "openai",
                "api_key": "sk-legacy-key",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-5.5",
                "temperature": 1.4,
                "max_tokens": 4096,
            }

    runtime_settings = _user_api_settings_for_runtime(
        {"user_id": "u-legacy", "role": "viewer"},
        AuthService(),
    )

    assert runtime_settings == {
        "provider": "openai",
        "api_key": "sk-legacy-key",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5.5",
        "temperature": 1.0,
        "max_tokens": 4096,
    }


def test_global_model_settings_default_uses_local_provider(monkeypatch):
    monkeypatch.setattr(
        "app.services.model_config_store.get_settings",
        lambda: SimpleNamespace(
            model_backend="local",
            ollama_base_url="http://localhost:11434",
            openai_base_url="https://api.openai.com/v1",
            ollama_chat_model="qwen3:14b",
            anthropic_chat_model="claude-opus-4-8",
            openai_chat_model="gpt-5.5",
            ollama_reasoning_model="deepseek-r1:32b",
            openai_reasoning_model="gpt-5.5",
            anthropic_reasoning_model="claude-opus-4-8",
            ollama_embed_model="nomic-embed-text",
            openai_embed_model="text-embedding-3-small",
        ),
    )

    settings = default_global_model_settings()

    assert settings["provider"] == "local"
    assert settings["chat_model"] == "local-evidence"
    assert settings["embedding_model"] == "local-hash-384"


def test_anthropic_model_uses_relay_client_for_custom_base_url():
    _build_chat_model_cached.cache_clear()

    model = _build_chat_model_cached(
        provider="anthropic",
        backend="anthropic",
        temperature=0.7,
        openai_model="unused",
        openai_api_key="",
        openai_base_url="",
        ollama_model="unused",
        ollama_base_url="",
        anthropic_model="claude-opus-4-8",
        anthropic_api_key="sk-test",
        anthropic_base_url="https://cc-vibe.com",
        max_tokens=2048,
    )

    assert isinstance(model, OutboundRedactedChatModel)
    assert isinstance(model._inner, AnthropicRelayChatModel)
    assert model.base_url == "https://cc-vibe.com"
    assert model.model == "claude-opus-4-8"


def test_anthropic_relay_message_payload_maps_system_and_user_messages():
    model = AnthropicRelayChatModel(
        model="claude-opus-4-8",
        api_key="sk-test",
        base_url="https://cc-vibe.com",
        temperature=0.7,
        max_tokens=2048,
    )

    payload = model._message_payload([("system", "system prompt"), ("human", "hello")])

    assert payload["system"] == "system prompt"
    assert payload["messages"] == [{"role": "user", "content": "hello"}]


def test_anthropic_relay_extracts_multiple_response_shapes():
    model = AnthropicRelayChatModel(
        model="claude-opus-4-8",
        api_key="sk-test",
        base_url="https://cc-vibe.com",
    )

    assert model._extract_content({"content": [{"type": "text", "text": "OK"}]}) == "OK"
    assert model._extract_content({"content": "OK"}) == "OK"
    assert model._extract_content({"choices": [{"message": {"content": "OK"}}]}) == "OK"


def test_anthropic_relay_invoke_accepts_string_content_response(monkeypatch):
    model = AnthropicRelayChatModel(
        model="claude-opus-4-8",
        api_key="sk-test",
        base_url="https://cc-vibe.com",
    )
    seen = {}

    class Response:
        status_code = 200
        text = '{"content":"OK"}'

        def json(self):
            return {"content": "OK"}

    def fake_post(url, headers, json, timeout):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr("httpx.post", fake_post)

    result = model.invoke([("system", "reply OK"), ("human", "test")])

    assert result.content == "OK"
    assert seen["url"] == "https://cc-vibe.com/v1/messages"
    assert seen["json"]["messages"] == [{"role": "user", "content": "test"}]


def test_custom_provider_with_claude_model_uses_anthropic_relay_client(monkeypatch):
    _build_chat_model_cached.cache_clear()
    monkeypatch.setattr("app.core.models.get_global_model_settings", lambda: {"enabled": False})

    with request_context(
        timeout_ms=12000,
        overload_mode=False,
        api_settings={
            "provider": "custom",
            "api_key": "sk-test",
            "base_url": "https://cc-vibe.com",
            "model": "claude-opus-4-8",
            "temperature": 0.7,
            "max_tokens": 2048,
        },
    ):
        model = get_chat_model()

    assert isinstance(model, OutboundRedactedChatModel)
    assert isinstance(model._inner, AnthropicRelayChatModel)
    assert model.base_url == "https://cc-vibe.com"
    assert model.model == "claude-opus-4-8"


def test_outbound_redacted_chat_model_masks_messages_before_inner_invoke():
    seen = {}

    class Inner:
        def invoke(self, messages):
            seen["messages"] = messages
            return SimpleNamespace(content="OK")

    model = OutboundRedactedChatModel(Inner(), provider="deepseek")
    result = model.invoke([("human", "mail alice@example.com path /srv/a.txt token=sk-test-123456")])

    assert result.content == "OK"
    payload = seen["messages"][0][1]
    assert "alice@example.com" not in payload
    assert "/srv/a.txt" not in payload
    assert "sk-test-123456" not in payload
    assert "<EMAIL_1>" in payload
    assert "<PATH_1>" in payload
    assert "<SECRET_1>" in payload


def test_outbound_redacted_embeddings_masks_texts_before_embedding():
    seen = {}

    class Inner:
        def embed_documents(self, texts):
            seen["texts"] = texts
            return [[0.1] for _ in texts]

        def embed_query(self, text):
            seen["query"] = text
            return [0.1]

    model = OutboundRedactedEmbeddings(Inner(), provider="openai")

    vectors = model.embed_documents(["Contact alice@example.com", "See /srv/ops.txt"])
    query = model.embed_query("token=sk-test-123456")

    assert vectors == [[0.1], [0.1]]
    assert query == [0.1]
    assert "alice@example.com" not in seen["texts"][0]
    assert "/srv/ops.txt" not in seen["texts"][1]
    assert "sk-test-123456" not in seen["query"]


def test_current_cloud_provider_catalog_uses_official_model_ids():
    catalog = get_model_catalog()

    assert provider_defaults("openai")["chat_model"] == "gpt-5.5"
    assert provider_defaults("openai")["reasoning_model"] == "gpt-5.5"
    assert provider_defaults("deepseek")["chat_model"] == "deepseek-v4-flash"
    assert provider_defaults("deepseek")["reasoning_model"] == "deepseek-v4-pro"
    assert provider_defaults("anthropic")["chat_model"] == "claude-sonnet-5"
    assert catalog["deepseek"]["supports_embeddings"] is False
    assert catalog["anthropic"]["supports_embeddings"] is False


def test_non_embedding_cloud_provider_keeps_existing_embedding_pipeline(monkeypatch):
    monkeypatch.setattr(
        "app.core.models.get_global_model_settings",
        lambda: {
            "enabled": True,
            "provider": "deepseek",
            "api_key": "sk-test",
            "base_url": "https://api.deepseek.com/v1",
            "embedding_model": "",
        },
    )

    assert _global_embedding_override() == {}
