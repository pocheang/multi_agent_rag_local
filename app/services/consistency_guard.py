import re


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def text_similarity(a: str, b: str) -> float:
    ta = set(_TOKEN_RE.findall((a or "").lower()))
    tb = set(_TOKEN_RE.findall((b or "").lower()))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def should_stabilize(previous_answer: str, new_answer: str, threshold: float) -> bool:
    return text_similarity(previous_answer, new_answer) < float(threshold)
