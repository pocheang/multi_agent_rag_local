import re

SMALLTALK_PATTERNS = [
    r"^\s*(hi|hello|hey|yo)\s*[!.?]*\s*$",
    r"^\s*(你好|您好|哈喽|嗨|在吗|在么|早上好|中午好|下午好|晚上好)\s*[！。.!?？]*\s*$",
    r"^\s*(谢谢|多谢|thanks|thank you)\s*[！。.!?？]*\s*$",
]


def is_smalltalk_query(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    for p in SMALLTALK_PATTERNS:
        if re.match(p, t, flags=re.IGNORECASE):
            return True
    return False
