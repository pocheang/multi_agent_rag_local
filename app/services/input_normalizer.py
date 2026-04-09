import re
import unicodedata


_MULTI_PUNCT_RE = re.compile(r"[!?！？。．\.]{3,}")
_SPACE_RE = re.compile(r"[ \u3000\t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_MULTI_REPEAT_CHAR_RE = re.compile(r"(.)\1{5,}")

_ACTION_INTENT_RE = re.compile(
    r"(执行|运行|帮我执行|直接执行|一键|下载并运行|run\s+this|execute|powershell|bash|shell|cmd)",
    flags=re.IGNORECASE,
)
_DANGEROUS_COMMAND_RE = re.compile(
    r"(rm\s+-rf|del\s+/[sqf]|format\s+[a-z]:|shutdown\s+/s|"
    r"invoke-expression|iex\s*\(|powershell\s+-enc|cmd\.exe|"
    r"curl\s+[^\\n]*\|\s*(bash|sh)|wget\s+[^\\n]*\|\s*(bash|sh)|"
    r"reg\s+add\b|bcdedit\b|vssadmin\s+delete\s+shadows)",
    flags=re.IGNORECASE,
)
_PROMPT_INJECTION_RE = re.compile(
    r"(ignore\s+(all\s+)?previous\s+instructions|"
    r"reveal\s+system\s+prompt|"
    r"you\s+are\s+now\s+developer|"
    r"忽略(之前|以上|所有)?(系统|开发者)?指令|"
    r"输出(系统|开发者)提示词|"
    r"越狱提示词|"
    r"绕过安全策略)",
    flags=re.IGNORECASE,
)
_INCOMPLETE_REFER_RE = re.compile(
    r"(这个|那个|上面|前面|如下|这里|它|他|她|该项|这个问题|那个问题)",
    flags=re.IGNORECASE,
)
_SHORT_TOKEN_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9_]+")


def normalize_user_question(question: str) -> str:
    text = unicodedata.normalize("NFKC", str(question or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    chars: list[str] = []
    for ch in text:
        if ch in ("\n", "\t"):
            chars.append(ch)
            continue
        if unicodedata.category(ch).startswith("C"):
            continue
        chars.append(ch)
    text = "".join(chars)

    lines = [_SPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    text = _MULTI_REPEAT_CHAR_RE.sub(lambda m: m.group(1) * 3, text)
    text = _MULTI_PUNCT_RE.sub(lambda m: m.group(0)[:2], text).strip()

    if not text:
        raise ValueError("question is empty after normalization")
    return text


def validate_user_question_security(question: str) -> None:
    text = str(question or "")
    danger = _DANGEROUS_COMMAND_RE.search(text)
    injection = _PROMPT_INJECTION_RE.search(text)
    action_intent = _ACTION_INTENT_RE.search(text)

    if danger and action_intent:
        raise ValueError(f"question blocked: potentially dangerous instruction '{danger.group(0)}'")
    if injection:
        raise ValueError("question blocked: prompt-injection like instruction detected")


def normalize_and_validate_user_question(question: str) -> str:
    normalized = normalize_user_question(question)
    validate_user_question_security(normalized)
    return normalized


def enhance_user_question_for_completion(question: str) -> str:
    """
    Improve short/underspecified user questions so downstream agents can
    reason with clearer constraints while preserving the original intent text.
    """
    text = normalize_user_question(question)
    tokens = _SHORT_TOKEN_RE.findall(text)
    too_short = len(text) <= 12 or (len(text) <= 24 and len(tokens) <= 3)
    has_refer = bool(_INCOMPLETE_REFER_RE.search(text))
    likely_incomplete = too_short or has_refer
    if not likely_incomplete:
        return text

    return (
        f"{text}\n\n"
        "[补全提示]\n"
        "- 优先按用户当前这条最新提问作答，不要被更早轮次覆盖。\n"
        "- 用户提问可能信息不完整，请先结合当前会话上下文补全语义。\n"
        "- 若仍缺少关键条件，请先列出缺失信息，再在明确假设下给出可执行建议。\n"
        "- 回答需包含：结论、执行步骤、风险点。"
    )
