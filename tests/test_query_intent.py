import types

import app.services.query_intent as query_intent


def test_is_smalltalk_query_basic_greetings():
    class FakeModel:
        def invoke(self, _messages):
            return types.SimpleNamespace(content='{"casual_chat": true, "reason": "greeting"}')

    query_intent.get_chat_model = lambda: FakeModel()
    assert query_intent.is_smalltalk_query("hi") is True
    assert query_intent.is_smalltalk_query("你好") is True
    assert query_intent.is_smalltalk_query("Hello!") is True


def test_is_smalltalk_query_non_greeting_questions():
    class FakeModel:
        def invoke(self, _messages):
            return types.SimpleNamespace(content='{"casual_chat": false, "reason": "task"}')

    query_intent.get_chat_model = lambda: FakeModel()
    assert query_intent.is_smalltalk_query("你好，帮我分析这个日志") is False
    assert query_intent.is_smalltalk_query("CVE-2025-1234 的影响是什么") is False


def test_should_force_web_research_for_explicit_web_request():
    assert query_intent.should_force_web_research("请上网查一下这个漏洞") is True
    assert query_intent.should_force_web_research("帮我联网搜索最新消息") is True


def test_should_force_web_research_for_freshness_queries():
    assert query_intent.should_force_web_research("最新勒索软件攻击趋势") is True
    assert query_intent.should_force_web_research("today's threat intel update") is True


def test_should_force_web_research_false_for_regular_local_query():
    assert query_intent.should_force_web_research("解释这份本地PDF中的攻击链") is False


def test_is_casual_chat_query_for_normal_chat():
    class FakeModel:
        def invoke(self, _messages):
            return types.SimpleNamespace(content='{"casual_chat": true, "reason": "smalltalk"}')

    query_intent.get_reasoning_model = lambda: FakeModel()
    assert query_intent.is_casual_chat_query("你是谁") is True
    assert query_intent.is_casual_chat_query("我们随便聊聊吧") is True
    assert query_intent.is_casual_chat_query("你在干嘛呢") is True


def test_is_casual_chat_query_false_for_web_freshness_request():
    assert query_intent.is_casual_chat_query("帮我上网查最新漏洞") is False


def test_is_casual_chat_query_false_for_short_fact_question():
    assert query_intent.is_casual_chat_query("你几点下班") is False


def test_is_casual_chat_query_tolerates_non_json_true_response():
    class FakeModel:
        def invoke(self, _messages):
            return types.SimpleNamespace(content="这是闲聊场景，casual_chat=true")

    query_intent.get_reasoning_model = lambda: FakeModel()
    assert query_intent.is_casual_chat_query("你好啊") is True


def test_force_web_ignores_internal_completion_guidance_block():
    text = (
        "你好啊\n\n"
        "[补全提示]\n"
        "- 优先按用户当前这条最新提问作答，不要被更早轮次覆盖。"
    )
    assert query_intent.should_force_web_research(text) is False
