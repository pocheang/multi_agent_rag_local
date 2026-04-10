import pytest

from app.services.history import HistoryStore, validate_session_id


def test_validate_session_id_rejects_path_like_value():
    with pytest.raises(ValueError):
        validate_session_id("../escape")


def test_history_store_rejects_invalid_session_id_for_append(tmp_path):
    store = HistoryStore(base_dir=tmp_path / "sessions")
    with pytest.raises(ValueError):
        store.append_message("../escape", "user", "hello")


def test_history_store_get_session_returns_none_for_invalid_id(tmp_path):
    store = HistoryStore(base_dir=tmp_path / "sessions")
    assert store.get_session("../escape") is None
