import uuid
from pathlib import Path

from app.services.memory_store import MemoryStore, score_memory_candidate


def test_score_memory_candidate_caps_each_signal():
    score, normalized = score_memory_candidate(
        answer="x" * 800,
        signals={
            "vector_retrieved": 99,
            "citation_count": 99,
            "web_used": False,
            "route": "vector",
            "reason": "ok",
        },
    )
    assert score == 1.0
    assert normalized["vector_retrieved"] == 3
    assert normalized["citation_count"] == 4
    assert normalized["web_used"] is False


def test_memory_window_and_topn_promotion():
    base_dir = Path("tests/.tmp") / f"memory-window-{uuid.uuid4().hex[:8]}"
    base_dir.mkdir(parents=True, exist_ok=True)
    store = MemoryStore(base_dir=base_dir)
    session_id = "session-memory-window"

    for i in range(25):
        store.add_candidate(
            session_id=session_id,
            question=f"question {i}",
            answer=f"answer {i} " + ("x" * 80),
            signals={
                "vector_retrieved": i % 4,
                "citation_count": i % 5,
                "web_used": (i % 2 == 0),
                "route": "vector",
                "reason": "ok",
            },
        )

    payload = store.get_session_payload(session_id)
    assert len(payload["candidates"]) == 20
    assert len(payload["long_term_ids"]) == 5

    expected = sorted(
        [x for x in payload["candidates"] if not x.get("deleted")],
        key=lambda x: (float(x.get("score", 0.0) or 0.0), x.get("created_at", "")),
        reverse=True,
    )[:5]
    assert payload["long_term_ids"] == [x["candidate_id"] for x in expected]


def test_delete_long_term_marks_deleted_and_recomputes():
    base_dir = Path("tests/.tmp") / f"memory-delete-{uuid.uuid4().hex[:8]}"
    base_dir.mkdir(parents=True, exist_ok=True)
    store = MemoryStore(base_dir=base_dir)
    session_id = "session-memory-delete"

    for i in range(6):
        store.add_candidate(
            session_id=session_id,
            question=f"question {i}",
            answer=f"high quality answer {i} " + ("y" * 120),
            signals={
                "vector_retrieved": 3,
                "citation_count": min(i, 4),
                "web_used": False,
                "route": "vector",
                "reason": "ok",
            },
        )

    before = store.list_long_term(session_id)
    assert len(before) == 5
    target_id = before[0]["candidate_id"]

    ok = store.delete_long_term(session_id=session_id, candidate_id=target_id)
    assert ok is True

    payload = store.get_session_payload(session_id)
    deleted = [x for x in payload["candidates"] if x.get("candidate_id") == target_id][0]
    assert deleted["deleted"] is True

    after = store.list_long_term(session_id)
    assert len(after) == 5
    assert target_id not in {x["candidate_id"] for x in after}
    assert store.delete_long_term(session_id=session_id, candidate_id=target_id) is False
