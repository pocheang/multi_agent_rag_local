import re

SMALLTALK_PATTERNS = [
    r"^\s*(hi|hello|hey|yo)\s*[!.?]*\s*$",
    r"^\s*(你好|您好|哈喽|嗨|在吗|在么|早上好|中午好|下午好|晚上好)\s*[！。.!?？]*\s*$",
    r"^\s*(谢谢|多谢|thanks|thank you)\s*[！。.!?？]*\s*$",
]

FORCE_WEB_PATTERNS = [
    r"(上网|联网|网络|互联网|网页|web|google|bing).{0,6}(查|搜索|检索|看看|找)",
    r"(查|搜索|检索|找).{0,6}(上网|联网|网络|互联网|网页|web|google|bing)",
    r"(请|帮我|麻烦).{0,6}(上网|联网).{0,6}(查|搜)",
]

FRESHNESS_PATTERNS = [
    r"(最新|近期|最近|今天|今日|刚刚|实时|当下|本周|本月|今年)",
    r"(breaking|today|latest|recent|real[- ]?time)",
]


def is_smalltalk_query(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    for p in SMALLTALK_PATTERNS:
        if re.match(p, t, flags=re.IGNORECASE):
            return True
    return False


def should_force_web_research(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    for p in FORCE_WEB_PATTERNS:
        if re.search(p, t, flags=re.IGNORECASE):
            return True
    for p in FRESHNESS_PATTERNS:
        if re.search(p, t, flags=re.IGNORECASE):
            return True
    return False
