from app.services.memory_store import (
    build_long_term_memory_context,
    build_memory_context,
    build_short_term_memory_context,
    retrieve_relevant_long_term_memories,
)


def test_short_term_context_uses_latest_three_rounds_only():
    messages = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "q3"},
        {"role": "assistant", "content": "a3"},
        {"role": "user", "content": "q4"},
        {"role": "assistant", "content": "a4"},
    ]
    context = build_short_term_memory_context(messages)
    assert "q1" not in context
    assert "q2" in context
    assert "q3" in context
    assert "q4" in context


def test_long_term_retrieval_prefers_bm25_hits():
    memories = [
        {"candidate_id": "m1", "question": "linux hardening", "answer": "ssh policy", "score": 0.7, "created_at": "2026-01-01T00:00:00+00:00"},
        {"candidate_id": "m2", "question": "sql injection defense", "answer": "parameterized queries", "score": 0.9, "created_at": "2026-01-02T00:00:00+00:00"},
        {"candidate_id": "m3", "question": "xss mitigation", "answer": "output encoding", "score": 0.8, "created_at": "2026-01-03T00:00:00+00:00"},
    ]
    selected = retrieve_relevant_long_term_memories("how to prevent sql injection", memories)
    assert selected
    assert selected[0]["candidate_id"] == "m2"
    context = build_long_term_memory_context("how to prevent sql injection", memories)
    assert "sql injection" in context


def test_long_term_retrieval_falls_back_to_latest_two_when_no_positive_hit():
    memories = [
        {"candidate_id": "m1", "question": "topic one", "answer": "answer one", "score": 0.6, "created_at": "2026-01-01T00:00:00+00:00"},
        {"candidate_id": "m2", "question": "topic two", "answer": "answer two", "score": 0.7, "created_at": "2026-01-02T00:00:00+00:00"},
        {"candidate_id": "m3", "question": "topic three", "answer": "answer three", "score": 0.8, "created_at": "2026-01-03T00:00:00+00:00"},
    ]
    selected = retrieve_relevant_long_term_memories("zzzxxyy unmatched", memories)
    assert [x["candidate_id"] for x in selected] == ["m3", "m2"]


def test_combined_memory_context_contains_short_and_long_sections():
    messages = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "u3"},
        {"role": "assistant", "content": "a3"},
    ]
    long_term = [
        {"candidate_id": "m1", "question": "incident response", "answer": "isolate host", "score": 0.9, "created_at": "2026-01-03T00:00:00+00:00"}
    ]
    context = build_memory_context("incident response playbook", messages, long_term)
    assert "Short-term memory" in context
    assert "Long-term memory" in context
