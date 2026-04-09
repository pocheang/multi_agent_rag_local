import re

from app.core.models import get_chat_model, get_reasoning_model


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
    r"(随便聊聊|聊聊天|闲聊|smalltalk|casual chat)",
]

# 明确任务请求默认不是闲聊。
_TASK_HINT_PATTERNS = [
    r"(请|帮我|需要|如何|怎么|给出|分析|总结|解释|比较|编写|生成|优化|排查|修复|调试|实现)",
    r"(what|how|why|analyze|summarize|explain|compare|debug|implement|fix)",
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
    return any(re.search(p, t, flags=re.IGNORECASE) for p in _CASUAL_CHAT_PATTERNS)


def is_smalltalk_query(text: str) -> bool:
    t = _strip_internal_guidance(text)
    return _is_casual_chat_by_rules(t)


def is_casual_chat_query(text: str) -> bool:
    t = _strip_internal_guidance(text)
    return _is_casual_chat_by_rules(t)


def should_force_web_research(text: str) -> bool:
    t = _strip_internal_guidance(text).lower()
    if not t:
        return False
    for p in FORCE_WEB_PATTERNS:
        if re.search(p, t, flags=re.IGNORECASE):
            return True
    for p in FRESHNESS_PATTERNS:
        if re.search(p, t, flags=re.IGNORECASE):
            return True
    return False
