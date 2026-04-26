import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

api_main = pytest.importorskip("app.api.main")


def _mock_user():
    return {"user_id": "u-test", "username": "tester", "role": "viewer", "status": "active"}


def _mock_admin():
    return {"user_id": "u-admin", "username": "admin", "role": "admin", "status": "active"}


def test_user_api_settings_test_success(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_user
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)

    calls: dict[str, object] = {}

    class _Resp:
        content = "OK"

    class _Model:
        def invoke(self, messages):
            calls["messages"] = messages
            return _Resp()

    monkeypatch.setattr(api_main, "get_chat_model", lambda temperature=None: _Model())
    try:
        res = client.post(
            "/user/api-settings/test",
            json={
                "provider": "anthropic",
                "api_key": "sk-ant-xxx",
                "base_url": "https://api.anthropic.com/v1",
                "model": "claude-sonnet-4-6",
                "temperature": 0.7,
                "max_tokens": 512,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["reachable"] is True
        assert body["provider"] == "anthropic"
        assert body["model"] == "claude-sonnet-4-6"
        assert "succeeded" in (body["message"] or "").lower()
        assert "ok" in (body["preview"] or "").lower()
        assert isinstance(calls.get("messages"), list)
    finally:
        api_main.app.dependency_overrides.clear()


def test_user_api_settings_test_failure(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_user
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)

    class _Model:
        def invoke(self, _messages):
            raise RuntimeError("probe failed")

    monkeypatch.setattr(api_main, "get_chat_model", lambda temperature=None: _Model())
    try:
        res = client.post(
            "/user/api-settings/test",
            json={
                "provider": "openai",
                "api_key": "sk-openai-xxx",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-5.4-codex",
                "temperature": 0.7,
                "max_tokens": 512,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is False
        assert body["reachable"] is False
        assert "probe failed" in (body["message"] or "")
    finally:
        api_main.app.dependency_overrides.clear()


def test_user_api_settings_test_requires_api_key_for_cloud(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_user
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    try:
        res = client.post(
            "/user/api-settings/test",
            json={
                "provider": "anthropic",
                "api_key": "",
                "base_url": "https://api.anthropic.com/v1",
                "model": "claude-sonnet-4-6",
                "temperature": 0.7,
                "max_tokens": 512,
            },
        )
        assert res.status_code == 400
        assert "api_key is required" in (res.json().get("detail", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()


def test_user_api_settings_supports_local_without_key_or_base_url(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_user
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)

    class _Resp:
        content = "OK"

    class _Model:
        def invoke(self, _messages):
            return _Resp()

    monkeypatch.setattr(api_main, "get_chat_model", lambda temperature=None: _Model())
    try:
        res = client.post(
            "/user/api-settings/test",
            json={
                "provider": "local",
                "api_key": "",
                "base_url": "",
                "model": "local-evidence",
                "temperature": 0.7,
                "max_tokens": 512,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["provider"] == "local"
    finally:
        api_main.app.dependency_overrides.clear()


def test_user_api_settings_test_anthropic_custom_base_url_returns_hint(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_user
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)

    called = {"model": False}

    def _fake_get_chat_model(temperature=None):
        called["model"] = True
        raise AssertionError("should not invoke model for anthropic custom-base-url hint")

    monkeypatch.setattr(api_main, "get_chat_model", _fake_get_chat_model)
    try:
        res = client.post(
            "/user/api-settings/test",
            json={
                "provider": "anthropic",
                "api_key": "sk-ant-xxx",
                "base_url": "https://cc-vibe.com",
                "model": "claude-sonnet-4-6",
                "temperature": 0.7,
                "max_tokens": 512,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is False
        assert body["reachable"] is False
        assert "provider=anthropic" in (body["message"] or "")
        assert called["model"] is False
    finally:
        api_main.app.dependency_overrides.clear()


def test_save_user_api_settings_normalizes_ollama_base_url(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_user
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)

    saved: dict[str, object] = {}

    def _fake_set_user_metadata(user_id: str, key: str, value):
        saved["user_id"] = user_id
        saved["key"] = key
        saved["value"] = value

    monkeypatch.setattr(api_main.auth_service, "set_user_metadata", _fake_set_user_metadata)
    try:
        res = client.post(
            "/user/api-settings",
            json={
                "provider": "ollama",
                "api_key": "",
                "base_url": "http://localhost:11434/v1",
                "model": "qwen2.5:7b",
                "temperature": 0.7,
                "max_tokens": 2048,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["settings"]["base_url"] == "http://localhost:11434"
        assert saved["user_id"] == "u-test"
        assert saved["key"] == "api_settings"
        assert (saved["value"] or {}).get("base_url") == "http://localhost:11434"
    finally:
        api_main.app.dependency_overrides.clear()


def test_get_user_api_settings_masks_api_key(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_user
    monkeypatch.setattr(
        api_main.auth_service,
        "get_user_metadata",
        lambda _user_id, _key: {
            "provider": "openai",
            "api_key": "sk-live-secret-123456",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-5.4-codex",
            "temperature": 0.7,
            "max_tokens": 2048,
        },
    )
    try:
        res = client.get("/user/api-settings")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert "api_key" not in (body.get("settings") or {})
        masked = str((body.get("settings") or {}).get("api_key_masked", "") or "")
        assert masked.startswith("sk-")
        assert masked != "sk-live-secret-123456"
    finally:
        api_main.app.dependency_overrides.clear()


def test_save_user_api_settings_response_does_not_return_plain_api_key(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_user
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main.auth_service, "set_user_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main.auth_service, "get_user_metadata", lambda *_args, **_kwargs: None)
    try:
        res = client.post(
            "/user/api-settings",
            json={
                "provider": "openai",
                "api_key": "sk-openai-plain-xyz",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-5.4-codex",
                "temperature": 0.7,
                "max_tokens": 2048,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert "api_key" not in (body.get("settings") or {})
        assert str((body.get("settings") or {}).get("api_key_masked", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "blocked_base_url",
    [
        "http://127.0.0.1:8000/v1",
        "http://localhost:8080/v1",
        "http://169.254.10.20/v1",
        "http://10.0.0.1/v1",
        "http://172.16.0.5/v1",
        "http://192.168.1.7/v1",
    ],
)
def test_user_api_settings_test_rejects_private_or_loopback_base_url(monkeypatch, blocked_base_url: str):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_user
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    try:
        res = client.post(
            "/user/api-settings/test",
            json={
                "provider": "custom",
                "api_key": "sk-custom-123",
                "base_url": blocked_base_url,
                "model": "gpt-4o-mini",
                "temperature": 0.7,
                "max_tokens": 512,
            },
        )
        assert res.status_code == 400
        assert "unsafe base_url" in (res.json().get("detail", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()


def test_save_user_api_settings_rejects_private_or_loopback_base_url(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_user
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    try:
        res = client.post(
            "/user/api-settings",
            json={
                "provider": "custom",
                "api_key": "sk-custom-xyz",
                "base_url": "http://127.0.0.1:11434/v1",
                "model": "custom-model",
                "temperature": 0.7,
                "max_tokens": 2048,
            },
        )
        assert res.status_code == 400
        assert "unsafe base_url" in (res.json().get("detail", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()


def test_save_user_api_settings_keeps_existing_api_key_when_request_api_key_empty(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_user
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api_main.auth_service,
        "get_user_metadata",
        lambda _user_id, _key: {
            "provider": "openai",
            "api_key": "sk-existing-1234",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-5.4-codex",
            "temperature": 0.7,
            "max_tokens": 512,
        },
    )
    saved: dict[str, object] = {}

    def _fake_set_user_metadata(user_id: str, key: str, value):
        saved["user_id"] = user_id
        saved["key"] = key
        saved["value"] = value

    monkeypatch.setattr(api_main.auth_service, "set_user_metadata", _fake_set_user_metadata)
    try:
        res = client.post(
            "/user/api-settings",
            json={
                "provider": "openai",
                "api_key": "",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-5.4-codex",
                "temperature": 0.7,
                "max_tokens": 512,
            },
        )
        assert res.status_code == 200
        assert ((saved.get("value") or {}).get("api_key")) == "sk-existing-1234"
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_model_settings_save_masks_api_key_and_clears_caches(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_admin
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "get_global_model_settings", lambda: {"provider": "openai", "api_key": "sk-existing"})
    saved: dict[str, object] = {}

    def _fake_save(payload):
        saved["payload"] = dict(payload)
        return {
            "enabled": True,
            "provider": "openai",
            "api_key": "sk-admin-secret-123456",
            "base_url": "https://api.openai.com/v1",
            "chat_model": "gpt-5.4-codex",
            "reasoning_model": "gpt-5.4-codex",
            "embedding_model": "text-embedding-3-small",
            "temperature": 0.7,
            "max_tokens": 2048,
        }

    monkeypatch.setattr(api_main, "save_global_model_settings", _fake_save)
    monkeypatch.setattr(api_main, "clear_model_caches", lambda: saved.setdefault("model_cache_cleared", True))
    monkeypatch.setattr(api_main, "clear_vector_store_cache", lambda: saved.setdefault("vector_cache_cleared", True))
    monkeypatch.setattr(api_main, "rebuild_all_vector_index", lambda: saved.setdefault("reindex_result", {"ok": True, "records_reindexed": 7}))
    try:
        res = client.post(
            "/admin/model-settings",
            json={
                "enabled": True,
                "provider": "openai",
                "api_key": "sk-admin-secret-123456",
                "base_url": "https://api.openai.com/v1",
                "chat_model": "gpt-5.4-codex",
                "reasoning_model": "gpt-5.4-codex",
                "embedding_model": "text-embedding-3-small",
                "temperature": 0.7,
                "max_tokens": 2048,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert "api_key" not in body["settings"]
        assert body["settings"]["api_key_masked"].startswith("sk-")
        assert saved["model_cache_cleared"] is True
        assert saved["vector_cache_cleared"] is True
        assert body["settings"]["embedding_reindexed"] is True
        assert body["settings"]["records_reindexed"] == 7
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_model_settings_does_not_reindex_when_embedding_unchanged(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_admin
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    current = {
        "enabled": True,
        "provider": "openai",
        "api_key": "sk-existing",
        "base_url": "https://api.openai.com/v1",
        "chat_model": "old-chat",
        "reasoning_model": "old-reasoning",
        "embedding_model": "text-embedding-3-small",
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    monkeypatch.setattr(api_main, "get_global_model_settings", lambda: dict(current))
    saved: dict[str, object] = {}

    def _fake_save(payload):
        out = dict(current)
        out.update(payload)
        out["api_key"] = "sk-existing"
        return out

    def _unexpected_reindex():
        raise AssertionError("embedding did not change")

    monkeypatch.setattr(api_main, "save_global_model_settings", _fake_save)
    monkeypatch.setattr(api_main, "clear_model_caches", lambda: None)
    monkeypatch.setattr(api_main, "clear_vector_store_cache", lambda: None)
    monkeypatch.setattr(api_main, "rebuild_all_vector_index", _unexpected_reindex)
    try:
        res = client.post(
            "/admin/model-settings",
            json={
                "enabled": True,
                "provider": "openai",
                "api_key": "",
                "base_url": "https://api.openai.com/v1",
                "chat_model": "new-chat",
                "reasoning_model": "new-reasoning",
                "embedding_model": "text-embedding-3-small",
                "temperature": 0.7,
                "max_tokens": 2048,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["settings"].get("embedding_reindexed") is False
        assert body["settings"].get("records_reindexed") == 0
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_model_settings_rejects_unsafe_custom_base_url(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = _mock_admin
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    try:
        res = client.post(
            "/admin/model-settings",
            json={
                "enabled": True,
                "provider": "custom",
                "api_key": "sk-custom",
                "base_url": "http://127.0.0.1:8000/v1",
                "chat_model": "custom-chat",
                "reasoning_model": "custom-chat",
                "embedding_model": "text-embedding-3-small",
                "temperature": 0.7,
                "max_tokens": 2048,
            },
        )
        assert res.status_code == 400
        assert "unsafe base_url" in (res.json().get("detail", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()
