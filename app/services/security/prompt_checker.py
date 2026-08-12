import json
import logging
import re
from typing import Any

from app.services.input_normalizer import normalize_user_question
from app.services.models.runtime import get_reasoning_model

logger = logging.getLogger(__name__)

_JSON_OBJ_RE = re.compile(r"\{.*\}", flags=re.DOTALL)
_DANGEROUS_RE = re.compile(
    r"(rm\s+-rf|del\s+/[sqf]|format\s+[a-z]:|powershell\s+-enc|curl\s+[^\n]*\|\s*(bash|sh)|"
    r"eval\s*\(|exec\s*\(|__import__|subprocess|os\.system|shell=True|"
    r"<script|javascript:|onerror=|onload=|onclick=)",
    flags=re.IGNORECASE,
)


def _sanitize_output(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"javascript:", "", text, flags=re.IGNORECASE)
    text = re.sub(r"on\w+\s*=", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
    return text.strip()


def _extract_json(text: str) -> dict[str, Any] | None:
    match = _JSON_OBJ_RE.search(text or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError) as error:
        logger.debug(f"Failed to extract JSON from text: {error}")
        return None


def _contains_any(text: str, words: list[str]) -> bool:
    low = (text or "").lower()
    return any(word.lower() in low for word in words)


def check_and_enhance_prompt(title: str, content: str, use_reasoning: bool = False) -> dict[str, Any]:
    t = _sanitize_output(normalize_user_question(title or "未命名模板"))
    c = _sanitize_output(normalize_user_question(content or ""))
    issues: list[str] = []
    suggestions: list[str] = []

    if len(c) < 60:
        issues.append("Prompt 过短，语义约束不足。")
        suggestions.append("补充目标、上下文、约束和输出格式。")
    if not _contains_any(c, ["目标", "任务", "objective", "task"]):
        issues.append("缺少任务目标描述。")
        suggestions.append("增加'任务目标'段，明确要完成什么。")
    if not _contains_any(c, ["上下文", "背景", "context"]):
        issues.append("缺少上下文/背景。")
        suggestions.append("增加'上下文'段，指定输入来源和范围。")
    if not _contains_any(c, ["约束", "限制", "不要", "must", "constraint"]):
        issues.append("缺少约束条件。")
        suggestions.append("增加'约束'段，明确禁用项与边界。")
    if not _contains_any(c, ["输出格式", "格式", "json", "markdown", "结构"]):
        issues.append("缺少输出格式规范。")
        suggestions.append("增加'输出格式'段，例如固定标题或 JSON 结构。")
    if _DANGEROUS_RE.search(c):
        issues.append("检测到潜在危险命令片段。")
        suggestions.append("删除可执行破坏命令，改为防御性说明。")

    enhanced = c
    if not issues:
        suggestions.append("结构完整，可直接使用。")
    else:
        enhanced = (
            f"{c}\n\n"
            "【补充建议结构】\n"
            "1) 任务目标：说明要解决的问题与成功标准。\n"
            "2) 上下文输入：列出可用信息来源与边界。\n"
            "3) 约束条件：禁止高风险输出、保持可验证。\n"
            "4) 输出格式：先结论后要点，附引用来源。"
        )

    if use_reasoning:
        try:
            model = get_reasoning_model()
            prompt = (
                "你是 Prompt 质检与补全助手。请在不改变用户意图的前提下，优化模板。"
                "要求：更清晰、更结构化、避免危险执行指令。"
                "只输出 JSON："
                '{"title":"...","content":"...","issues":["..."],"suggestions":["..."]}\n\n'
                f"标题:\n{t}\n\n内容:\n{enhanced}\n"
            )
            result = model.invoke([("system", "请严格输出 JSON"), ("human", prompt)])
            text = result.content if hasattr(result, "content") else str(result)
            data = _extract_json(text)
            if data:
                t = _sanitize_output(normalize_user_question(str(data.get("title", t))))
                enhanced = _sanitize_output(normalize_user_question(str(data.get("content", enhanced))))
                llm_issues = [_sanitize_output(str(item)) for item in (data.get("issues", []) or []) if str(item).strip()]
                llm_suggestions = [
                    _sanitize_output(str(item)) for item in (data.get("suggestions", []) or []) if str(item).strip()
                ]
                if llm_issues:
                    issues = llm_issues
                if llm_suggestions:
                    suggestions = llm_suggestions
        except (RuntimeError, ValueError) as error:
            logger.debug(f"LLM prompt enhancement failed: {error}")

    return {
        "title": _sanitize_output(t),
        "content": _sanitize_output(enhanced),
        "issues": [_sanitize_output(str(item)) for item in issues],
        "suggestions": [_sanitize_output(str(item)) for item in suggestions],
    }
