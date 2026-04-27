from dataclasses import dataclass
import re


_COMPLEXITY_PATTERNS = {
    "complex": [
        r"\b(root cause|rca|postmortem|trade[- ]?off|architecture)\b",
        r"(根因|复盘|多阶段|多步骤|全链路|架构设计|取舍)",
        r"(对比|比较).{0,10}(并|和|与)",
        r"(时间线|timeline|attack chain)",
    ],
    "medium": [
        r"\b(how|why|compare|analyze)\b",
        r"(如何|为什么|分析|解释|方案)",
    ],
}


@dataclass(frozen=True)
class AdaptivePlan:
    level: str
    route: str
    min_vector_hits: int
    prefer_graph: bool
    prefer_web: bool
    reason: str


def _estimate_complexity_level(question: str) -> str:
    q = str(question or "").strip().lower()
    if not q:
        return "simple"
    for pattern in _COMPLEXITY_PATTERNS["complex"]:
        if re.search(pattern, q, flags=re.IGNORECASE):
            return "complex"
    for pattern in _COMPLEXITY_PATTERNS["medium"]:
        if re.search(pattern, q, flags=re.IGNORECASE):
            return "medium"
    token_count = len(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", q))
    # Align with hybrid_retriever complexity detection threshold
    if token_count >= 28:
        return "complex"
    if token_count >= 15:
        return "medium"
    return "simple"


def build_adaptive_plan(
    question: str,
    initial_route: str,
    skill: str,
    use_web_fallback: bool,
    force_web: bool,
) -> AdaptivePlan:
    level = _estimate_complexity_level(question)

    route = initial_route if initial_route in {"vector", "graph", "hybrid"} else "vector"
    prefer_graph = route in {"graph", "hybrid"}
    if level == "complex" and route == "vector":
        route = "hybrid"
        prefer_graph = True

    if level == "simple":
        min_hits = 1
    elif level == "medium":
        min_hits = 2
    else:
        min_hits = 3

    # force_web is for time-sensitive queries detected by router (should prefer web)
    # use_web_fallback is the user's explicit toggle (allows web as fallback, not preference)
    prefer_web = bool(force_web)
    reason = (
        f"adaptive_level={level}"
        f" | adaptive_route={route}"
        f" | min_vector_hits={min_hits}"
        f" | prefer_graph={prefer_graph}"
        f" | prefer_web={prefer_web}"
    )
    return AdaptivePlan(
        level=level,
        route=route,
        min_vector_hits=min_hits,
        prefer_graph=prefer_graph,
        prefer_web=prefer_web,
        reason=reason,
    )
