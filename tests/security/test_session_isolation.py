"""A session id belonging to one user must be inert for every other user.

Session isolation is structural rather than checked: `_history_store_for_user`
hands each user a store rooted at `sessions/{user_id}` (app/api/deps/sessions.py:16),
and the sqlite backend scopes every statement with `namespace=?`. Nothing
re-validates ownership at the route layer, so these properties are the whole
defence and a change to either mechanism silently removes it.

Both backends are exercised: the file backend is the default, and the sqlite one
shares a single database file between all users, where the namespace column is
the only thing keeping them apart.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from app.services.sessions.history import HistoryStore, validate_session_id


@pytest.fixture(params=["file", "sqlite"])
def stores(request, monkeypatch) -> tuple[HistoryStore, HistoryStore]:
    """Alice's and Bob's stores, on each supported history backend."""
    from app.services.sessions import history as history_module

    root = Path(tempfile.mkdtemp(prefix="querymind-sessions-"))
    real_get_settings = history_module.get_settings

    class _Settings:
        history_backend = request.param
        sessions_path = root / "sessions"
        history_cold_path = root / "cold"
        history_sqlite_path = root / "history.db"
        history_hot_tier_days = 14
        sqlite_busy_timeout_seconds = 10

    _Settings.history_cold_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(history_module, "get_settings", lambda: _Settings)
    try:
        yield (
            HistoryStore(base_dir=_Settings.sessions_path / "alice"),
            HistoryStore(base_dir=_Settings.sessions_path / "bob"),
        )
    finally:
        monkeypatch.setattr(history_module, "get_settings", real_get_settings)
        shutil.rmtree(root, ignore_errors=True)


def test_a_session_is_invisible_to_another_users_store(stores):
    alice, bob = stores
    session_id = alice.create_session(title="performance review")["session_id"]
    alice.append_message(session_id, "user", "what is my raise")

    assert bob.get_session(session_id) is None
    assert [s["session_id"] for s in bob.list_sessions()] == []


def test_listing_never_crosses_users(stores):
    alice, bob = stores
    alice.create_session(title="alice one")
    alice.create_session(title="alice two")
    bob_session = bob.create_session(title="bob one")["session_id"]

    assert len(alice.list_sessions()) == 2
    assert [s["session_id"] for s in bob.list_sessions()] == [bob_session]


def test_another_user_cannot_delete_or_mutate_the_session(stores):
    alice, bob = stores
    session_id = alice.create_session(title="performance review")["session_id"]

    assert bob.delete_session(session_id) is False
    assert bob.update_session_title(session_id, "hijacked") is None
    assert alice.get_session(session_id)["title"] == "performance review"


def test_another_user_cannot_read_a_message_by_id(stores):
    alice, bob = stores
    session_id = alice.create_session()["session_id"]
    message = alice.append_message(session_id, "user", "my salary is confidential")
    message_id = message["messages"][-1]["message_id"]

    assert bob.get_message(session_id, message_id) is None


def test_clarification_context_does_not_cross_users(stores):
    alice, bob = stores
    session_id = alice.create_session()["session_id"]
    alice.set_clarification_context(
        session_id,
        {"collected_info": {"budget": "confidential"}, "intent": "rag_design", "max_rounds": 7},
    )

    assert bob.get_clarification_context(session_id) is None


def test_a_traversal_shaped_session_id_is_rejected():
    for candidate in ("../bob/abcdef", "..", "a/b", "alice\\bob"):
        with pytest.raises(ValueError):
            validate_session_id(candidate)
