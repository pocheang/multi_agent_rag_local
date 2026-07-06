from types import SimpleNamespace

from app.core.models import (
    AnthropicRelayChatModel,
    OutboundRedactedChatModel,
    OutboundRedactedEmbeddings,
    _build_chat_model_cached,
    _global_embedding_override,
    get_chat_model,
)
from app.core.schemas import AdminModelSettings, UserApiSettings
from app.services.model_catalog import get_model_catalog, provider_defaults
from app.services.model_config_store import default_global_model_settings
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


def test_custom_provider_with_claude_model_uses_anthropic_relay_client():
    _build_chat_model_cached.cache_clear()

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
