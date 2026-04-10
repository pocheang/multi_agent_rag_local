import re

FORCE_WEB_PATTERNS = [
    r"(上网|联网|网络|互联网|网页|web|google|bing).{0,6}(查|搜索|检索|看看|找)",
    r"(查|搜索|检索|找).{0,6}(上网|联网|网络|互联网|网页|web|google|bing)",
    r"(请|帮我|麻烦).{0,6}(上网|联网).{0,6}(查|搜)",
]

FRESHNESS_PATTERNS = [
    r"(最新|近期|最近|今天|今日|刚刚|实时|当下|本周|本月|今年)",
    r"(breaking|today|latest|recent|real[- ]?time)",
]

_AUGMENT_MARKERS = ("[补全提示]", "[仅聚焦以下文档文件:")

# 规则优先，保证意图判定稳定、低延迟、可测试。
_CASUAL_CHAT_PATTERNS = [
    r"^(你好|您好|hi|hello|hey|哈喽|在吗|早上好|中午好|晚上好)(啊|呀|哦|呢)?[!！,.。?？ ]*$",
    r"^(谢谢|感谢|thx|thanks)[!！,.。?？ ]*$",
    r"(你是谁|你能做什么|介绍一下你自己|自我介绍)",
    r"(你在干嘛|你在做什么|你忙吗|最近怎么样|你还在吗|陪我聊聊|聊会天)",
    r"^(嗯|哦|啊|呀|诶|哈哈|嘿嘿|晚安|早安|拜拜|再见)[!！,.。?？ ]*$",
    r"(随便聊聊|聊聊天|闲聊|smalltalk|casual chat)",
]

# 明确任务请求默认不是闲聊。
_TASK_HINT_PATTERNS = [
    r"(请|帮我|需要|如何|怎么|给出|分析|总结|解释|比较|编写|生成|优化|排查|修复|调试|实现)",
    r"(what|how|why|analyze|summarize|explain|compare|debug|implement|fix)",
]

_FACT_QUERY_HINT_PATTERNS = [
    r"(是什么|是谁|多少|几点|哪里|哪家|哪种|哪一个|何时|什么时候|多久|多大|多高|多少岁)",
    r"(价格|股价|汇率|天气|新闻|公告|财报|比分|赛程|票房|发布|更新|版本|漏洞|趋势|动态|情报|威胁)",
    r"(what is|who is|how much|when is|where is|price|weather|news|release|update|version|score)",
]

_SMALLTALK_REPLY_PATTERNS = [
    (r"^(你好|您好|hi|hello|hey|哈喽|在吗|早上好|中午好|晚上好)", "你好，我在。要不要我帮你查文档、总结内容，或者直接聊聊？"),
    (r"^(谢谢|感谢|thx|thanks)", "不客气，随时叫我。"),
    (r"(你是谁|你能做什么|介绍一下你自己|自我介绍)", "我是你的本地 RAG 助手，可以检索本地文档、总结信息、并进行问答。"),
]


def _strip_internal_guidance(text: str) -> str:
    raw = str(text or "")
    if not raw:
        return ""
    cleaned = raw
    for marker in _AUGMENT_MARKERS:
        idx = cleaned.find(marker)
        if idx >= 0:
            cleaned = cleaned[:idx]
    return cleaned.strip()


def _is_casual_chat_by_rules(text: str) -> bool:
    t = str(text or "").strip().lower()
    if not t:
        return False
    if should_force_web_research(t):
        return False
    if any(re.search(p, t, flags=re.IGNORECASE) for p in _TASK_HINT_PATTERNS):
        return False
    if any(re.search(p, t, flags=re.IGNORECASE) for p in _CASUAL_CHAT_PATTERNS):
        return True
    # Short social utterances should prefer fast smalltalk path.
    if _looks_like_information_request(t):
        return False
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", t)
    if 0 < len(tokens) <= 12 and any(x in t for x in ("你", "我", "咱们", "我们")):
        return True
    return False


def is_smalltalk_query(text: str) -> bool:
    t = _strip_internal_guidance(text)
    return _is_casual_chat_by_rules(t)


def is_casual_chat_query(text: str) -> bool:
    t = _strip_internal_guidance(text)
    return _is_casual_chat_by_rules(t)


def _looks_like_information_request(text: str) -> bool:
    t = str(text or "").strip().lower()
    if not t:
        return False
    if any(re.search(p, t, flags=re.IGNORECASE) for p in _TASK_HINT_PATTERNS):
        return True
    if any(re.search(p, t, flags=re.IGNORECASE) for p in _FACT_QUERY_HINT_PATTERNS):
        return True
    # Question marks usually indicate explicit information seeking.
    if ("?" in t) or ("？" in t):
        return True
    return False


def should_force_web_research(text: str) -> bool:
    t = _strip_internal_guidance(text).lower()
    if not t:
        return False
    for p in FORCE_WEB_PATTERNS:
        if re.search(p, t, flags=re.IGNORECASE):
            return True
    freshness_hit = any(re.search(p, t, flags=re.IGNORECASE) for p in FRESHNESS_PATTERNS)
    if not freshness_hit:
        return False
    # Freshness words alone (e.g. "今天好累") should not force web.
    if any(re.search(p, t, flags=re.IGNORECASE) for p in _CASUAL_CHAT_PATTERNS):
        return False
    return _looks_like_information_request(t)


def quick_smalltalk_reply(text: str) -> str | None:
    t = _strip_internal_guidance(text)
    if not t:
        return None
    if not _is_casual_chat_by_rules(t):
        return None
    normalized = t.strip().lower()
    for pattern, reply in _SMALLTALK_REPLY_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return reply
    return "收到，我们可以先随便聊聊；如果你要我查文档或做分析，直接说需求就行。"
