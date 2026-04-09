from app.services.history import HistoryStore
from pathlib import Path
import uuid


def test_session_strategy_lock_roundtrip():
    base = Path("data") / "test_tmp" / f"history_lock_{uuid.uuid4().hex}"
    base.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(base_dir=base)
    session = store.create_session()
    sid = str(session["session_id"])
    assert store.get_session_strategy_lock(sid) is None
    store.set_session_strategy_lock(sid, "baseline")
    assert store.get_session_strategy_lock(sid) == "baseline"
    store.set_session_strategy_lock(sid, None)
    assert store.get_session_strategy_lock(sid) is None
