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
