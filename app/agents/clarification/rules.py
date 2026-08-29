"""Deterministic completeness rules shared by Router and Clarification."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.domain.contracts import ClarificationQuestion

ClarificationIntent = Literal["rag_design", "document_comparison", "complete"]


@dataclass(frozen=True)
class CompletenessAssessment:
    """A retrieval-free assessment of fields required before execution."""

    intent: ClarificationIntent
    complexity: Literal["simple", "complex"]
    required_fields: tuple[str, ...] = ()
    extracted_info: dict[str, str] = field(default_factory=dict)


_QUESTIONS: dict[str, dict[str, ClarificationQuestion]] = {
    "rag_design": {
        "scenario": ClarificationQuestion(
            question="这个 RAG 系统主要用于什么场景？",
            options=["企业知识库", "客服问答", "代码知识库", "数据分析"],
            allow_custom_input=True,
            field_name="scenario",
        ),
        "data_source": ClarificationQuestion(
            question="主要数据来源是什么？",
            options=["PDF/Office 文档", "数据库", "API", "网页"],
            allow_custom_input=True,
            field_name="data_source",
        ),
        "scale": ClarificationQuestion(
            question="预计的数据规模大约是多少？",
            options=["小型（<1GB）", "中型（1-10GB）", "大型（10-100GB）", "超大型（>100GB）"],
            allow_custom_input=True,
            field_name="scale",
        ),
        "performance_requirement": ClarificationQuestion(
            question="对响应速度有什么要求？",
            options=["实时（<1秒）", "快速（1-3秒）", "一般（3-5秒）", "无严格要求"],
            allow_custom_input=True,
            field_name="performance_requirement",
        ),
    },
    "document_comparison": {
        "doc_ids": ClarificationQuestion(
            question="需要比较哪些文档或对象？",
            options=[],
            allow_custom_input=True,
            field_name="doc_ids",
        ),
        "comparison_aspect": ClarificationQuestion(
            question="希望重点比较哪些方面？",
            options=["功能", "性能", "成本", "时间或版本变化"],
            allow_custom_input=True,
            field_name="comparison_aspect",
        ),
        "output_format": ClarificationQuestion(
            question="希望使用什么输出形式？",
            options=["对比表格", "详细报告", "简要总结"],
            allow_custom_input=True,
            field_name="output_format",
        ),
    },
}

_MAX_ROUNDS = {"rag_design": 7, "document_comparison": 5, "complete": 0}


def assess_completeness(question: str) -> CompletenessAssessment:
    """Identify only cases where execution would materially depend on missing fields."""

    text = str(question or "").strip()
    lowered = text.lower()
    structured = _structured_fields(text)
    has_rag = bool(re.search(r"\brag\b|检索增强|知识库(?:系统)?|knowledge\s*base", lowered, re.IGNORECASE))
    has_design = bool(
        re.search(r"设计|搭建|构建|实现|架构|how\s+to\s+(?:build|design|implement)|architecture", lowered)
    )
    if has_rag and has_design:
        extracted = {**_extract_rag_fields(text), **structured}
        return CompletenessAssessment(
            intent="rag_design",
            complexity="complex",
            required_fields=("scenario", "data_source", "scale", "performance_requirement"),
            extracted_info=extracted,
        )

    is_comparison = bool(re.search(r"比较|对比|差异|区别|\bcompare\b|\bdifference\b|\bversus\b|\bvs\.?\b", lowered))
    if is_comparison:
        extracted = {**_extract_comparison_fields(text), **structured}
        return CompletenessAssessment(
            intent="document_comparison",
            complexity="complex",
            # Named comparison targets are essential; aspect and presentation
            # have safe general-purpose defaults and must not force extra turns.
            required_fields=("doc_ids",),
            extracted_info=extracted,
        )

    return CompletenessAssessment(intent="complete", complexity="simple", extracted_info=structured)


def missing_fields(assessment: CompletenessAssessment, collected_info: dict[str, str]) -> tuple[str, ...]:
    """Return required fields absent from both the query and prior confirmed answers."""

    known = {**assessment.extracted_info, **_nonblank(collected_info)}
    return tuple(field_name for field_name in assessment.required_fields if not known.get(field_name, "").strip())


def question_for(intent: str, field_name: str) -> ClarificationQuestion | None:
    """Return a fresh structured question so request state cannot mutate templates."""

    template = _QUESTIONS.get(intent, {}).get(field_name)
    return template.model_copy(deep=True) if template is not None else None


def max_rounds_for(intent: str) -> int:
    return _MAX_ROUNDS.get(intent, 5)


def _structured_fields(text: str) -> dict[str, str]:
    supported = {field_name for questions in _QUESTIONS.values() for field_name in questions}
    extracted: dict[str, str] = {}
    for field_name, value in re.findall(r"(?im)^\s*-\s*([a-z_]+)\s*:\s*(.+?)\s*$", text):
        if field_name in supported and value.strip():
            extracted[field_name] = value.strip()
    return extracted


def _extract_rag_fields(text: str) -> dict[str, str]:
    lowered = text.lower()
    extracted: dict[str, str] = {}
    scenario_patterns = (
        (r"企业|公司|内部|enterprise|internal", "企业知识库"),
        (r"客服|客户服务|customer\s*support|helpdesk", "客服问答"),
        (r"代码|编程|developer|code", "代码知识库"),
        (r"数据分析|报表|analytics", "数据分析"),
    )
    for pattern, value in scenario_patterns:
        if re.search(pattern, lowered):
            extracted["scenario"] = value
            break
    source_patterns = (
        (r"\bpdf\b|\bword\b|\bpptx?\b|\bexcel\b|文档|文件", "PDF/Office 文档"),
        (r"数据库|\bsql\b|mysql|postgres|database", "数据库"),
        (r"\bapi\b|接口|graphql", "API"),
        (r"网页|网站|爬取|crawl|website", "网页"),
    )
    for pattern, value in source_patterns:
        if re.search(pattern, lowered):
            extracted["data_source"] = value
            break
    scale = re.search(r"\b\d+(?:\.\d+)?\s*(?:kb|mb|gb|tb|万条|千条|条)\b", lowered)
    if scale:
        extracted["scale"] = scale.group(0)
    performance = re.search(
        r"(?:响应|延迟|latency)[^，。;\n]{0,20}|(?:<|≤)\s*\d+(?:\.\d+)?\s*(?:ms|毫秒|s|秒)", lowered
    )
    if performance:
        extracted["performance_requirement"] = performance.group(0).strip()
    return extracted


_COMPARISON_TARGET_SUFFIX_RE = re.compile(r"的?(?:区别|差异|对比|优劣|异同)$")
_COMPARISON_TARGET_NOISE_RE = re.compile(
    r"请|请问|帮我|麻烦|比较|对比|说明|分析|以及|还有|另外|compare|difference|versus", re.IGNORECASE
)


def _clean_comparison_target(raw: str) -> str | None:
    """Reject a captured `versus` group that is really a leftover instruction
    fragment (e.g. a truncated verb phrase from a narrative sentence) rather than
    an actual entity name, and strip a common trailing "的区别/差异" clause so plain
    "A和B的区别" style inputs still extract cleanly."""
    cleaned = _COMPARISON_TARGET_SUFFIX_RE.sub("", raw.strip()).strip()
    if not cleaned or _COMPARISON_TARGET_NOISE_RE.search(cleaned):
        return None
    return cleaned


def _extract_comparison_fields(text: str) -> dict[str, str]:
    extracted: dict[str, str] = {}
    quoted = re.findall(r"[\"“‘']([^\"”’']{1,80})[\"”’']", text)
    versus = re.search(
        r"([\w.\-/一-鿿]{2,60})\s*(?:与|和|及|vs\.?|versus)\s*([\w.\-/一-鿿]{2,60})", text, re.IGNORECASE
    )
    if len(quoted) >= 2:
        extracted["doc_ids"] = "、".join(quoted[:5])
    elif versus:
        left = _clean_comparison_target(versus.group(1))
        right = _clean_comparison_target(versus.group(2))
        if left and right:
            extracted["doc_ids"] = f"{left}、{right}"
    aspect = re.search(
        r"功能|性能|成本|价格|时间|版本|安全|准确率|召回率|feature|performance|cost|security", text, re.IGNORECASE
    )
    if aspect:
        extracted["comparison_aspect"] = aspect.group(0)
    output_format = re.search(r"表格|报告|总结|table|report|summary", text, re.IGNORECASE)
    if output_format:
        extracted["output_format"] = output_format.group(0)
    return extracted


def _nonblank(values: dict[str, str]) -> dict[str, str]:
    return {str(key): str(value).strip() for key, value in values.items() if str(value).strip()}


__all__ = [
    "CompletenessAssessment",
    "assess_completeness",
    "max_rounds_for",
    "missing_fields",
    "question_for",
]
