from app.api.deps.query import _query_cache_key


def _key(*, conversation, request_id=None):
    return _query_cache_key(
        user={"user_id": "user-1"},
        session_id="session-1",
        question="What about it?",
        use_web_fallback=False,
        use_reasoning=False,
        retrieval_strategy="advanced",
        agent_class_hint=None,
        request_id=request_id,
        conversation=conversation,
        index_fingerprint_fn=lambda _user: "index",
        model_fingerprint_fn=lambda _user: "model",
    )


def test_query_cache_key_changes_with_conversation_context():
    first = _key(conversation=[{"role": "system", "content": "topic A"}])
    second = _key(conversation=[{"role": "system", "content": "topic B"}])

    assert first != second


def test_request_id_keeps_retry_key_stable_across_history_mutation():
    first = _key(
        request_id="request-1",
        conversation=[{"role": "system", "content": "before request"}],
    )
    retry = _key(
        request_id="request-1",
        conversation=[{"role": "system", "content": "after request"}],
    )
    different_request = _key(
        request_id="request-2",
        conversation=[{"role": "system", "content": "after request"}],
    )

    assert first == retry
    assert first != different_request
