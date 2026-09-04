import json
import logging
import re
from collections import Counter
from dataclasses import dataclass

from app.core.config import get_settings
from app.services.models.runtime import get_chat_model

logger = logging.getLogger(__name__)

ENTITY_PATTERN = re.compile(r"\b([A-Z][A-Za-z0-9_\-]{2,}|[\u4e00-\u9fff]{2,12})\b")
JSON_PATTERN = re.compile(r"\[.*\]", flags=re.DOTALL)

# What a triplet is worth, by how it was produced. Both were 0.7 -- hardcoded on
# every triplet regardless of extractor -- which made `filter_triplets` unable to
# distinguish them and its threshold inert.
#
# The rule value sits below every shipped `graph_min_confidence`
# (app/services/parser_profiles.py: 0.55 / 0.6 / 0.65 / 0.75) on purpose: a
# frequency-rank adjacency pair is not a relation, and the existing filter is the
# right place to say so. A deployment that genuinely wants rule triplets has to
# lower a threshold deliberately.
#
# Deliberately not a Settings field: a knob whose only purpose is re-enabling a
# path we judged to be fabrication is a knob for turning fabrication back on.
LLM_TRIPLET_CONFIDENCE = 0.7
RULE_TRIPLET_CONFIDENCE = 0.25


@dataclass(frozen=True)
class GraphTriplet:
    head: str
    relation: str
    tail: str
    confidence: float
    method: str


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
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"Failed to parse JSON array from LLM response: {e}")
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


def filter_triplets(triplets: list[GraphTriplet], min_confidence: float = 0.5) -> list[GraphTriplet]:
    best: dict[tuple[str, str, str], GraphTriplet] = {}
    for item in triplets:
        if item.confidence < min_confidence:
            continue
        key = (item.head.strip(), item.relation.strip(), item.tail.strip())
        if not all(key) or key[0] == key[2]:
            continue
        current = best.get(key)
        if current is None or item.confidence > current.confidence:
            best[key] = item
    return list(best.values())


def _stamp(raw: list[tuple[str, str, str]], confidence: float, method: str) -> list[GraphTriplet]:
    return [
        GraphTriplet(head=head, relation=relation, tail=tail, confidence=confidence, method=method)
        for head, relation, tail in dedupe_triplets(raw)
    ]


def extract_triplets(text: str) -> list[GraphTriplet]:
    """Extract triplets and record which extractor produced them.

    This is the only place that knows *which* extractor ran, so it is the only
    place that may stamp a confidence. It used to return bare tuples and
    ``extract_graph_triplets`` stamped every one of them ``confidence=0.7,
    method="legacy"`` -- so ``filter_triplets`` could not tell an LLM-extracted
    relation from a regex-chained one, and the threshold it applies was inert.

    That mattered because the rule extractor does not find relations: it pairs
    the ten most *frequent* regex matches by adjacent frequency rank, which is an
    artefact of sort order, and labels every pair in a chunk with one relation
    keyed off the whole chunk's wording. With ``MODEL_BACKEND=local`` -- what a
    fresh checkout runs -- the LLM cannot emit the required JSON, so the fallback
    below is the *default* path and the graph filled with invented edges that the
    graph route then served as evidence.

    Two rule methods rather than one, because "this deployment chose rules" and
    "this deployment's LLM is broken" are different facts and were previously
    indistinguishable.
    """

    settings = get_settings()
    if settings.graph_extraction_mode.lower() == "rules":
        return _stamp(extract_triplets_rules(text), RULE_TRIPLET_CONFIDENCE, "rules")

    try:
        llm_triplets = extract_triplets_llm(text)
        if llm_triplets:
            return _stamp(llm_triplets, LLM_TRIPLET_CONFIDENCE, "llm")
    except (RuntimeError, ValueError) as e:
        logger.warning(f"LLM triplet extraction failed, falling back to rules: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error in LLM triplet extraction, falling back to rules: {e}", exc_info=True)
    return _stamp(extract_triplets_rules(text), RULE_TRIPLET_CONFIDENCE, "rules_llm_fallback")


def extract_graph_triplets_with_diagnostics(
    text: str, min_confidence: float = 0.5
) -> tuple[list[GraphTriplet], dict[str, int]]:
    """Filter by confidence, and say what was dropped and by which extractor.

    The counts are not decoration. Every shipped parser profile sets
    ``graph_min_confidence`` above ``RULE_TRIPLET_CONFIDENCE``, so on an
    installation with no working LLM this now writes *nothing* -- which is the
    truthful number, but a graph route that quietly goes empty is exactly the
    kind of silence this repository keeps finding. The caller reports these.
    """

    extracted = extract_triplets(text)
    kept = filter_triplets(extracted, min_confidence=min_confidence)
    methods: dict[str, int] = {}
    for triplet in extracted:
        methods[triplet.method] = methods.get(triplet.method, 0) + 1
    methods["discarded_low_confidence"] = len(extracted) - len(kept)
    return kept, methods
