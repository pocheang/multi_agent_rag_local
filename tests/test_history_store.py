import uuid
from pathlib import Path

from app.services.history import HistoryStore


def test_append_message_preserves_explicit_session_id():
    base_dir = Path("tests/.tmp") / f"history-store-{uuid.uuid4().hex[:8]}"
    base_dir.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(base_dir=base_dir)
    session_id = "session-fixed-id"

    data = store.append_message(session_id=session_id, role="user", content="hello")

    assert data["session_id"] == session_id
    assert (base_dir / f"{session_id}.json").exists()
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "hello"
    assert data["messages"][0].get("message_id")


def test_update_message_by_id():
    base_dir = Path("tests/.tmp") / f"history-update-{uuid.uuid4().hex[:8]}"
    base_dir.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(base_dir=base_dir)
    session_id = "session-update"
    store.append_message(session_id=session_id, role="user", content="第一句")
    store.append_message(session_id=session_id, role="assistant", content="第二句")
    session = store.get_session(session_id)
    target_id = session["messages"][0]["message_id"]

    updated = store.update_message(session_id=session_id, message_id=target_id, content="修改后的第一句")

    assert updated is not None
    assert updated["messages"][0]["content"] == "修改后的第一句"
    assert updated["title"] == "修改后的第一句"


def test_delete_message_by_id():
    base_dir = Path("tests/.tmp") / f"history-delete-{uuid.uuid4().hex[:8]}"
    base_dir.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(base_dir=base_dir)
    session_id = "session-delete"
    store.append_message(session_id=session_id, role="user", content="一")
    store.append_message(session_id=session_id, role="assistant", content="二")
    session = store.get_session(session_id)
    delete_id = session["messages"][0]["message_id"]

    data = store.delete_message(session_id=session_id, message_id=delete_id)

    assert data is not None
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "二"


def test_delete_session_file():
    base_dir = Path("tests/.tmp") / f"history-delete-session-{uuid.uuid4().hex[:8]}"
    base_dir.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(base_dir=base_dir)
    session_id = "session-remove"
    store.append_message(session_id=session_id, role="user", content="hello")

    ok = store.delete_session(session_id)

    assert ok is True
    assert (base_dir / f"{session_id}.json").exists() is False


def test_upsert_assistant_after_user_updates_existing_answer():
    base_dir = Path("tests/.tmp") / f"history-rerun-{uuid.uuid4().hex[:8]}"
    base_dir.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(base_dir=base_dir)
    session_id = "session-rerun"
    store.append_message(session_id=session_id, role="user", content="原问题")
    store.append_message(session_id=session_id, role="assistant", content="原回答")
    session = store.get_session(session_id)
    user_id = session["messages"][0]["message_id"]

    data = store.upsert_assistant_after_user(
        session_id=session_id,
        user_message_id=user_id,
        assistant_content="新回答",
        metadata={"route": "vector"},
    )

    assert data is not None
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["content"] == "新回答"
    assert data["messages"][1]["metadata"]["route"] == "vector"
