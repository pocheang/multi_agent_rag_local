from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

api_main = pytest.importorskip("app.api.main")


def _settings(base: Path):
    docs = base / "docs"
    uploads = base / "uploads"
    docs.mkdir(parents=True, exist_ok=True)
    uploads.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(docs_path=docs, uploads_path=uploads)


def _make_tmp_dir(prefix: str) -> Path:
    path = Path("tests/.tmp") / f"{prefix}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_data_docs_are_visible_as_shared_knowledge(monkeypatch):
    settings = _settings(_make_tmp_dir("api-rag-scope-docs"))
    doc = settings.docs_path / "shared.md"
    doc.write_text("shared knowledge", encoding="utf-8")
    monkeypatch.setattr(api_main, "settings", settings)
    monkeypatch.setattr(
        api_main,
        "list_indexed_files",
        lambda: [
            {
                "filename": "shared.md",
                "source": str(doc),
                "chunks": 1,
                "owner_user_id": None,
                "visibility": "private",
            }
        ],
    )

    visible = api_main._list_visible_documents_for_user({"user_id": "u1", "role": "viewer"})

    assert [x["source"] for x in visible] == [str(doc)]


def test_pdf_filename_selection_restricts_allowed_sources(monkeypatch):
    settings = _settings(_make_tmp_dir("api-rag-scope-pdf"))
    user_dir = settings.uploads_path / "u1"
    user_dir.mkdir(parents=True, exist_ok=True)
    a = user_dir / "a.pdf"
    b = user_dir / "b.pdf"
    a.write_bytes(b"%PDF-a")
    b.write_bytes(b"%PDF-b")
    monkeypatch.setattr(api_main, "settings", settings)
    monkeypatch.setattr(
        api_main,
        "list_indexed_files",
        lambda: [
            {"filename": "a.pdf", "source": str(a), "chunks": 2, "owner_user_id": "u1", "visibility": "private"},
            {"filename": "b.pdf", "source": str(b), "chunks": 2, "owner_user_id": "u1", "visibility": "private"},
        ],
    )

    allowed = api_main._allowed_sources_for_visible_filenames({"user_id": "u1", "role": "viewer"}, ["b.pdf"])

    assert allowed == [str(b)]


def test_query_cache_key_changes_when_user_model_settings_change(monkeypatch):
    user_settings = {
        "provider": "openai",
        "api_key": "sk-a",
        "base_url": "https://api.openai.com/v1",
        "model": "model-a",
        "temperature": 0.7,
        "max_tokens": 512,
    }
    monkeypatch.setattr(api_main, "_visible_index_fingerprint_for_user", lambda _user: "idx")
    monkeypatch.setattr(api_main, "get_global_model_settings", lambda: {"enabled": False})
    monkeypatch.setattr(api_main.auth_service, "get_user_metadata", lambda _uid, _key: dict(user_settings))
    user = {"user_id": "u1"}

    key_a = api_main._query_cache_key(
        user=user,
        session_id="s1",
        question="q",
        use_web_fallback=False,
        use_reasoning=False,
        retrieval_strategy="advanced",
        agent_class_hint=None,
        request_id=None,
    )
    user_settings["model"] = "model-b"
    key_b = api_main._query_cache_key(
        user=user,
        session_id="s1",
        question="q",
        use_web_fallback=False,
        use_reasoning=False,
        retrieval_strategy="advanced",
        agent_class_hint=None,
        request_id=None,
    )

    assert key_a != key_b
