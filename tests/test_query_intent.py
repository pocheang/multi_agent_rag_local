from app.services.query_intent import is_smalltalk_query, should_force_web_research


def test_is_smalltalk_query_basic_greetings():
    assert is_smalltalk_query("hi") is True
    assert is_smalltalk_query("你好") is True
    assert is_smalltalk_query("Hello!") is True


def test_is_smalltalk_query_non_greeting_questions():
    assert is_smalltalk_query("你好，帮我分析这个日志") is False
    assert is_smalltalk_query("CVE-2025-1234 的影响是什么") is False


def test_should_force_web_research_for_explicit_web_request():
    assert should_force_web_research("请上网查一下这个漏洞") is True
    assert should_force_web_research("帮我联网搜索最新消息") is True


def test_should_force_web_research_for_freshness_queries():
    assert should_force_web_research("最新勒索软件攻击趋势") is True
    assert should_force_web_research("today's threat intel update") is True


def test_should_force_web_research_false_for_regular_local_query():
    assert should_force_web_research("解释这份本地PDF中的攻击链") is False
