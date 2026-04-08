from app.services.query_intent import is_smalltalk_query


def test_is_smalltalk_query_basic_greetings():
    assert is_smalltalk_query("hi") is True
    assert is_smalltalk_query("你好") is True
    assert is_smalltalk_query("Hello!") is True


def test_is_smalltalk_query_non_greeting_questions():
    assert is_smalltalk_query("你好，帮我分析这个日志") is False
    assert is_smalltalk_query("CVE-2025-1234 的影响是什么") is False
