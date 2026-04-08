import json
import re
from typing import Any

from app.core.models import get_reasoning_model
from app.services.input_normalizer import normalize_user_question

_JSON_OBJ_RE = re.compile(r"\{.*\}", flags=re.DOTALL)
_DANGEROUS_RE = re.compile(
    r"(rm\s+-rf|del\s+/[sqf]|format\s+[a-z]:|powershell\s+-enc|curl\s+[^\\n]*\|\s*(bash|sh))",
    flags=re.IGNORECASE,
)


def _extract_json(text: str) -> dict[str, Any] | None:
    m = _JSON_OBJ_RE.search(text or "")
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _contains_any(text: str, words: list[str]) -> bool:
    low = (text or "").lower()
    return any(w.lower() in low for w in words)


def check_and_enhance_prompt(title: str, content: str, use_reasoning: bool = True) -> dict[str, Any]:
    t = normalize_user_question(title or "未命名模板")
    c = normalize_user_question(content or "")
    issues: list[str] = []
    suggestions: list[str] = []

    if len(c) < 60:
        issues.append("Prompt 过短，语义约束不足。")
        suggestions.append("补充目标、上下文、约束和输出格式。")

    if not _contains_any(c, ["目标", "任务", "objective", "task"]):
        issues.append("缺少任务目标描述。")
        suggestions.append("增加“任务目标”段，明确要完成什么。")
    if not _contains_any(c, ["上下文", "背景", "context"]):
        issues.append("缺少上下文/背景。")
        suggestions.append("增加“上下文”段，指定输入来源和范围。")
    if not _contains_any(c, ["约束", "限制", "不要", "must", "constraint"]):
        issues.append("缺少约束条件。")
        suggestions.append("增加“约束”段，明确禁用项与边界。")
    if not _contains_any(c, ["输出格式", "格式", "json", "markdown", "结构"]):
        issues.append("缺少输出格式规范。")
        suggestions.append("增加“输出格式”段，例如固定标题或 JSON 结构。")

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
                t = normalize_user_question(str(data.get("title", t)))
                enhanced = normalize_user_question(str(data.get("content", enhanced)))
                llm_issues = [str(x) for x in (data.get("issues", []) or []) if str(x).strip()]
                llm_suggestions = [str(x) for x in (data.get("suggestions", []) or []) if str(x).strip()]
                if llm_issues:
                    issues = llm_issues
                if llm_suggestions:
                    suggestions = llm_suggestions
        except Exception:
            # 推理模型不可用时保持规则增强结果
            pass

    return {"title": t, "content": enhanced, "issues": issues, "suggestions": suggestions}
