import json
import re
from collections import Counter

from app.core.config import get_settings
from app.core.models import get_chat_model

ENTITY_PATTERN = re.compile(r"\b([A-Z][A-Za-z0-9_\-]{2,}|[\u4e00-\u9fff]{2,12})\b")
JSON_PATTERN = re.compile(r"\[.*\]", flags=re.DOTALL)


EXTRACTION_PROMPT = """
你是知识图谱抽取器。请从给定文本中抽取高价值三元组。

要求：
1. 只抽取文本中明确表达的事实，不要臆造。
2. 三元组格式：[{"head":"...","relation":"...","tail":"..."}]
3. relation 使用大写下划线风格，例如 USES, DEPENDS_ON, PART_OF, STORES_IN, IMPLEMENTED_BY。
4. 去掉过于泛化的实体，如“系统”“模块”“功能”这类若无具体限定则不要抽。
5. 最多返回 12 个三元组。
6. 只输出 JSON 数组，不要解释。
"""


def infer_relation(text: str, head: str, tail: str) -> str:
    t = text.lower()
    if any(x in t for x in ["depend", "依赖", "based on", "基于"]):
        return "DEPENDS_ON"
    if any(x in t for x in ["include", "包括", "contains", "包含"]):
        return "INCLUDES"
    if any(x in t for x in ["use", "使用", "调用"]):
        return "USES"
    if any(x in t for x in ["store", "存储", "写入"]):
        return "STORES_IN"
    return "RELATED_TO"


def extract_triplets_rules(text: str) -> list[tuple[str, str, str]]:
    candidates = ENTITY_PATTERN.findall(text)
    counts = Counter([c.strip() for c in candidates if len(c.strip()) >= 2])
    entities = [k for k, _ in counts.most_common(10)]

    triplets: list[tuple[str, str, str]] = []
    if len(entities) < 2:
        return triplets

    for i in range(len(entities) - 1):
        head = entities[i]
        tail = entities[i + 1]
        if head == tail:
            continue
        relation = infer_relation(text, head, tail)
        triplets.append((head, relation, tail))
    return triplets


def _extract_json_array(text: str) -> list[dict]:
    match = JSON_PATTERN.search(text)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def extract_triplets_llm(text: str) -> list[tuple[str, str, str]]:
    model = get_chat_model()
    batch_chars = get_settings().graph_triplet_batch_chars
    payload = text[:batch_chars]
    result = model.invoke([("system", EXTRACTION_PROMPT), ("human", payload)])
    content = result.content if hasattr(result, "content") else str(result)
    rows = _extract_json_array(content)
    triplets: list[tuple[str, str, str]] = []
    for row in rows:
        head = str(row.get("head", "")).strip()
        relation = str(row.get("relation", "")).strip().upper().replace(" ", "_")
        tail = str(row.get("tail", "")).strip()
        if head and relation and tail and head != tail:
            triplets.append((head, relation, tail))
    return triplets


def dedupe_triplets(triplets: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    out = []
    seen = set()
    for item in triplets:
        key = tuple(x.strip() for x in item)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def extract_triplets(text: str) -> list[tuple[str, str, str]]:
    settings = get_settings()
    if settings.graph_extraction_mode.lower() == "rules":
        return dedupe_triplets(extract_triplets_rules(text))

    try:
        llm_triplets = extract_triplets_llm(text)
        if llm_triplets:
            return dedupe_triplets(llm_triplets)
    except Exception:
        pass
    return dedupe_triplets(extract_triplets_rules(text))
