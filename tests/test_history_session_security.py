import shutil
import uuid
from pathlib import Path

import pytest

from app.services.history import HistoryStore, validate_session_id


def test_validate_session_id_rejects_path_like_value():
    with pytest.raises(ValueError):
        validate_session_id("../escape")


def test_history_store_rejects_invalid_session_id_for_append():
    tmp_dir = Path("data/.test_tmp") / f"history_security_{uuid.uuid4().hex}"
    try:
        store = HistoryStore(base_dir=tmp_dir / "sessions")
        with pytest.raises(ValueError):
            store.append_message("../escape", "user", "hello")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_history_store_get_session_returns_none_for_invalid_id():
    tmp_dir = Path("data/.test_tmp") / f"history_security_{uuid.uuid4().hex}"
    try:
        store = HistoryStore(base_dir=tmp_dir / "sessions")
        assert store.get_session("../escape") is None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
