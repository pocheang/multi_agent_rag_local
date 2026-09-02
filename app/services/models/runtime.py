import hashlib
import json
import math
import os
import re
import time
from functools import lru_cache
from types import SimpleNamespace
from typing import Any

from app.core.config import get_settings
from app.domain.text import normalize_string
from app.services.models.catalog import provider_supports_embeddings
from app.services.models.config_store import get_global_model_settings
from app.services.runtime.request_context import get_request_api_settings, request_context
from app.services.security.network import validate_api_base_url_for_provider
from app.services.security.outbound_redaction import (
    is_external_provider,
    redact_messages_for_provider,
    redact_texts_for_provider,
)


def _norm_temp(temperature: float | None) -> float:
    return round(0.0 if temperature is None else float(temperature), 3)


def _normalize_runtime_temperature(provider: str, temperature: float | None) -> float:
    try:
        normalized = _norm_temp(temperature)
    except (TypeError, ValueError, OverflowError):
        normalized = 0.0
    if not math.isfinite(normalized):
        normalized = 0.0
    normalized = max(0.0, normalized)
    if normalize_string(provider, lowercase=True) == "custom":
        normalized = min(1.0, normalized)
    return normalized


def _normalize_backend(backend: str) -> str:
    b = normalize_string(backend, lowercase=True)
    if b in {"deepseek", "custom"}:
        return "openai"
    if b not in {"openai", "ollama", "anthropic", "local"}:
        raise ValueError(f"unsupported model backend: {backend}")
    return b


def _looks_like_claude_model(model: str) -> bool:
    return normalize_string(model, lowercase=True).startswith("claude-")


def _anthropic_relay_base_url(base_url: str) -> str:
    return re.sub(r"/v1/?$", "", str(base_url or "").strip().rstrip("/"), flags=re.IGNORECASE)


_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{2,}|[\u4e00-\u9fff]")


def _normalize_messages(messages: Any) -> list[tuple[str, str]]:
    """Normalize a LangChain-style ``.invoke()``/``.ainvoke()`` argument into
    ``(role, content)`` pairs. A bare string (the standard shorthand for a single
    human message, and what non-app-internal callers like SelfRAGEvaluator and
    QueryDecomposer pass) is treated as one human message rather than iterated
    character by character."""
    if isinstance(messages, str):
        return [("human", messages)]
    pairs: list[tuple[str, str]] = []
    for item in messages or []:
        if isinstance(item, tuple) and len(item) >= 2:
            pairs.append((str(item[0]).lower(), str(item[1] or "")))
        else:
            role = str(getattr(item, "type", getattr(item, "role", "")) or "").lower()
            content = str(getattr(item, "content", item) or "")
            pairs.append((role, content))
    return pairs


class LocalHashEmbeddings:
    """Deterministic local embeddings for offline/dev RAG smoke use."""

    def __init__(self, dimensions: int = 384):
        self.dimensions = int(dimensions)

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        tokens = _TOKEN_RE.findall(str(text or "").lower())
        if not tokens:
            tokens = [str(text or "")[:64] or "empty"]
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8", errors="ignore"), digest_size=16).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = -1.0 if digest[4] & 1 else 1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class LocalEvidenceChatModel:
    """Small offline response model that keeps the app usable without Ollama/API keys."""

    def __init__(self, model: str = "local-evidence", temperature: float = 0.0, max_tokens: int = 0):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _message_text(self, messages) -> tuple[str, str]:
        system_parts: list[str] = []
        human_parts: list[str] = []
        for role, content in _normalize_messages(messages):
            if role in {"system", "ai", "assistant"}:
                system_parts.append(content)
            else:
                human_parts.append(content)
        return "\n".join(system_parts), "\n".join(human_parts)

    def _route_json(self, question: str) -> str:
        q = str(question or "").lower()
        route = "hybrid" if any(x in q for x in ["关系", "依赖", "graph", "relation", "路径"]) else "vector"
        skill = "answer_with_citations"
        if any(x in q for x in ["pdf", "文档", "文件", "image", "图片"]):
            skill = "pdf_text_reader"
        if any(x in q for x in ["安全", "漏洞", "攻击", "防护", "security", "risk"]):
            skill = "cyber_defense_hardening"
        return f'{{"route":"{route}","reason":"local_rule_router","skill":"{skill}"}}'

    # A section ends where the next *named* section begins.
    # `_build_prompt_with_language` writes exactly these labels, so they are
    # listed rather than guessed at.
    #
    # Two earlier versions got this wrong in opposite directions. The original
    # terminated only on labels ending in `上下文:`, so the last section ran to
    # the end of the prompt and swallowed the answer template -- the model's own
    # instructions came back as part of the answer. Replacing that with 'a short
    # line ending in a colon' then cut the section at every piece of evidence,
    # because `[E2] document=https:` reaches a colon within a few characters, so
    # only the first excerpt survived and the rest of the retrieved evidence was
    # silently discarded -- one paragraph and one reference for a four-source
    # answer.
    _SECTION_LABELS = (
        "技能",
        "用户问题",
        "记忆上下文",
        "向量检索上下文",
        "图谱上下文",
        "联网补充上下文",
        "答案模板指导",
    )
    _SECTION_END = re.compile("\n\n(?=(?:" + "|".join(_SECTION_LABELS) + ")[^\n]{0,40}?[:：])")

    def _extract_section(self, text: str, label: str) -> str:
        match = re.search(rf"{re.escape(label)}[:：]\n", text)
        if match is None:
            return ""
        rest = text[match.end() :]
        end = self._SECTION_END.search(rest)
        return rest[: end.start()].strip() if end else rest.strip()

    @staticmethod
    def _cited_excerpts(blocks: list[str]) -> list[tuple[str, str]]:
        """Pair each evidence marker with its text, dropping the header line.

        `ContextBuilder._render_item` writes `[E1] document=…; source=…; layer=…;
        retriever=…` above each excerpt. That header is addressing metadata for
        the pipeline, not prose, and echoing it into the answer is what produced
        `1. [E1] document=https://… layer=web; retriever=web <content>`.
        """
        found: list[tuple[str, str]] = []
        for block in blocks:
            for match in re.finditer(r"\[(E\d+)\][^\n]*\n(.*?)(?=\n\[E\d+\]|\Z)", block, flags=re.DOTALL):
                body = re.sub(r"\s+", " ", match.group(2)).strip()
                if body:
                    found.append((match.group(1), body))
        return found

    @staticmethod
    def _lead_sentence(text: str, limit: int = 300) -> str:
        """One sentence where the excerpt offers one, otherwise a clean cut.

        Cutting mid-word reads as corruption rather than as a quotation, so the
        fallback backs up to the last space.
        """
        for match in re.finditer(r"[.。!！?？](?:\s|$)", text):
            if match.end() >= 40:
                return text[: match.end()].strip()
        if len(text) <= limit:
            return text
        cut = text.rfind(" ", 0, limit)
        return text[: cut if cut > 40 else limit].rstrip() + "…"

    def _answer(self, payload: str) -> str:
        """Compose an extractive answer that reads like an answer.

        This backend cannot reason, so every sentence it emits is somebody
        else's, and its whole job is to attribute them correctly. What it must
        *not* do is narrate itself: the previous version opened with "基于当前本地
        检索结果，我对「…」的回答如下", numbered the raw context blocks, echoed the
        `[E1] document=…; layer=…; retriever=…` header of each, and closed with a
        paragraph about configuring Ollama. None of that is an answer, and the
        addressing metadata is not even prose.

        It also emitted no `[E{k}]` markers of its own, so `output_filter` had
        nothing to renumber into the reader-facing `[1]` and the reference list
        it appends pointed at citations the text never made.
        """
        question = self._extract_section(payload, "用户问题")
        blocks = [
            block
            for block in (
                self._extract_section(payload, "向量检索上下文"),
                self._extract_section(payload, "图谱上下文"),
                self._extract_section(payload, "联网补充上下文"),
            )
            if block and block != "无"
        ]
        excerpts = self._cited_excerpts(blocks)
        if not excerpts:
            return (
                "当前没有检索到可以支撑回答的证据。可以先上传 PDF、图片、Markdown 或 TXT 文档，或开启联网检索后再提问。"
            )

        # Paragraphs, each carrying the marker for the excerpt it came from --
        # the shape `output_filter` renumbers and the shape a reader expects.
        # No lead-in, no trailer: a note about which backend produced this
        # belongs in the trace, not in every answer.
        del question
        paragraphs = [f"{self._lead_sentence(body)} [{marker}]" for marker, body in excerpts[:4]]
        return "\n\n".join(paragraphs)

    def invoke(self, messages):
        system_text, human_text = self._message_text(messages)
        if "route planner" in system_text.lower() or "output json only" in system_text.lower():
            return SimpleNamespace(content=self._route_json(human_text))
        if "知识图谱抽取器" in system_text:
            return SimpleNamespace(content="[]")
        if "答案质检" in system_text:
            return SimpleNamespace(
                content='{"is_correct":true,"issues":[],"improved_answer":"","analysis":"local_review_skipped"}'
            )
        if "query decomposition expert" in human_text.lower():
            return SimpleNamespace(content=self._decomposition_echo(human_text))
        return SimpleNamespace(content=self._answer(human_text))

    def _decomposition_echo(self, prompt_text: str) -> str:
        """This offline backend can't actually decompose a query; echo it back as a
        single sub-query so callers (QueryDecomposer) fall back to the original
        question instead of receiving unrelated placeholder text as a "sub-query"."""
        match = re.search(r"Query:\s*(.+)", prompt_text)
        query = match.group(1).strip() if match else prompt_text.strip()
        return f"1. {query}"

    async def ainvoke(self, messages):
        """Async form of invoke(); this backend is pure local computation (no I/O),
        so no actual awaiting is needed, only interface parity with the other
        chat model wrappers below that callers rely on for `.ainvoke()`."""
        return self.invoke(messages)

    def stream(self, messages):
        """Stream response with simulated typing effect for better UX."""
        import time

        full_content = self.invoke(messages).content

        # Split into chunks for simulated streaming
        # Simulate realistic token-by-token generation
        words = full_content.split()
        buffer = []

        for i, word in enumerate(words):
            buffer.append(word)

            # Yield every 3-5 words to simulate chunk generation
            if len(buffer) >= 3 or i == len(words) - 1:
                chunk_text = " ".join(buffer)
                if i < len(words) - 1:
                    chunk_text += " "
                yield SimpleNamespace(content=chunk_text)
                buffer = []

                # Small delay to simulate network/generation latency
                time.sleep(0.05)  # 50ms between chunks


class AnthropicRelayChatModel:
    """Direct Anthropic Messages client for Claude relay gateways.

    Some relays return JSON that is valid enough for normal clients but trips
    LangChain/SDK Pydantic parsing with errors such as ``str.model_dump``. This
    lightweight adapter keeps the app on the Anthropic wire protocol and parses
    response content defensively.
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout_seconds: float = 30.0,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.temperature = temperature
        self.max_tokens = max(1, int(max_tokens or 2048))
        self.timeout_seconds = float(timeout_seconds)

    def _message_payload(self, messages) -> dict:
        system_parts: list[str] = []
        out_messages: list[dict[str, str]] = []
        for role, content in _normalize_messages(messages):
            if role == "system":
                if content:
                    system_parts.append(content)
                continue
            mapped_role = "assistant" if role in {"ai", "assistant"} else "user"
            if content:
                out_messages.append({"role": mapped_role, "content": content})

        system_text = "\n".join(system_parts).strip()
        if not out_messages:
            out_messages.append({"role": "user", "content": system_text or "Reply with OK."})
            system_text = ""

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": out_messages,
        }
        if system_text:
            payload["system"] = system_text
        return payload

    def _endpoint(self) -> str:
        return f"{self.base_url}/v1/messages"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _extract_content(self, data) -> str:
        if isinstance(data, str):
            return data
        if not isinstance(data, dict):
            return str(data or "")

        content = data.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    text = block.get("text")
                    if text is None and isinstance(block.get("content"), str):
                        text = block.get("content")
                    if text is not None:
                        parts.append(str(text))
            if parts:
                return "".join(parts)

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and message.get("content") is not None:
                    return str(message.get("content") or "")
                if first.get("text") is not None:
                    return str(first.get("text") or "")

        if isinstance(data.get("completion"), str):
            return str(data.get("completion") or "")
        return json.dumps(data, ensure_ascii=False)

    def invoke(self, messages):
        import httpx

        response = httpx.post(
            self._endpoint(),
            headers=self._headers(),
            json=self._message_payload(messages),
            timeout=self.timeout_seconds,
        )
        try:
            data = response.json()
        except ValueError:
            data = response.text
        if response.status_code >= 400:
            detail = self._extract_content(data).strip() or response.text.strip()
            raise RuntimeError(f"Anthropic relay request failed ({response.status_code}): {detail[:240]}")
        return SimpleNamespace(content=self._extract_content(data))

    async def ainvoke(self, messages):
        import httpx

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self._endpoint(),
                headers=self._headers(),
                json=self._message_payload(messages),
            )
        try:
            data = response.json()
        except ValueError:
            data = response.text
        if response.status_code >= 400:
            detail = self._extract_content(data).strip() or response.text.strip()
            raise RuntimeError(f"Anthropic relay request failed ({response.status_code}): {detail[:240]}")
        return SimpleNamespace(content=self._extract_content(data))

    def stream(self, messages):
        yield self.invoke(messages)


class OutboundRedactedChatModel:
    """Proxy that redacts prompt content before external model calls."""

    def __init__(self, inner, *, provider: str):
        self._inner = inner
        self.provider = str(provider or "").strip().lower()

    def invoke(self, messages):
        return self._inner.invoke(redact_messages_for_provider(messages, provider=self.provider))

    async def ainvoke(self, messages):
        payload = redact_messages_for_provider(messages, provider=self.provider)
        if hasattr(self._inner, "ainvoke"):
            return await self._inner.ainvoke(payload)
        return self._inner.invoke(payload)

    def stream(self, messages):
        payload = redact_messages_for_provider(messages, provider=self.provider)
        yield from self._inner.stream(payload)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


class OutboundRedactedEmbeddings:
    """Proxy that redacts embedding input text before external model calls."""

    def __init__(self, inner, *, provider: str):
        self._inner = inner
        self.provider = str(provider or "").strip().lower()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed_documents(
            redact_texts_for_provider(list(texts or []), provider=self.provider, for_embeddings=True)
        )

    def embed_query(self, text: str) -> list[float]:
        safe_text = redact_texts_for_provider([str(text or "")], provider=self.provider, for_embeddings=True)[0]
        return self._inner.embed_query(safe_text)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


def _wrap_chat_model_for_provider(model, *, provider: str):
    if is_external_provider(provider):
        return OutboundRedactedChatModel(model, provider=provider)
    return model


def _wrap_embedding_model_for_provider(model, *, provider: str):
    if is_external_provider(provider):
        return OutboundRedactedEmbeddings(model, provider=provider)
    return model


def _request_chat_override() -> dict:
    raw = get_request_api_settings() or {}
    provider = str(raw.get("provider", "") or "").strip().lower()
    model = str(raw.get("model", "") or "").strip()
    if not provider or not model:
        return {}
    if provider not in {"local", "openai", "anthropic", "deepseek", "ollama", "custom"}:
        return {}
    base_url = str(raw.get("base_url", "") or "").strip()
    if base_url:
        base_url = validate_api_base_url_for_provider(base_url, provider=provider)
    backend = _normalize_backend(provider)
    if provider == "custom" and _looks_like_claude_model(model):
        backend = "anthropic"
        base_url = _anthropic_relay_base_url(base_url)
    return {
        "provider": provider,
        "backend": backend,
        "model": model,
        "api_key": str(raw.get("api_key", "") or "").strip(),
        "base_url": base_url,
        "temperature": raw.get("temperature", None),
        "max_tokens": raw.get("max_tokens", None),
    }


def _global_chat_override() -> dict:
    raw = get_global_model_settings()
    if not bool(raw.get("enabled", False)):
        return {}
    provider = str(raw.get("provider", "") or "").strip().lower()
    model = str(raw.get("chat_model", "") or "").strip()
    if not provider or not model:
        return {}
    backend = _normalize_backend(provider)
    if provider == "custom" and _looks_like_claude_model(model):
        backend = "anthropic"
    return {
        "provider": provider,
        "backend": backend,
        "model": model,
        "api_key": str(raw.get("api_key", "") or "").strip(),
        "base_url": _anthropic_relay_base_url(str(raw.get("base_url", "") or "").strip())
        if backend == "anthropic"
        else str(raw.get("base_url", "") or "").strip(),
        "temperature": raw.get("temperature", None),
        "max_tokens": raw.get("max_tokens", None),
    }


def _global_reasoning_override() -> dict:
    raw = get_global_model_settings()
    if not bool(raw.get("enabled", False)):
        return {}
    provider = str(raw.get("provider", "") or "").strip().lower()
    model = str(raw.get("reasoning_model", "") or raw.get("chat_model", "") or "").strip()
    if not provider or not model:
        return {}
    backend = _normalize_backend(provider)
    if provider == "custom" and _looks_like_claude_model(model):
        backend = "anthropic"
    return {
        "provider": provider,
        "backend": backend,
        "model": model,
        "api_key": str(raw.get("api_key", "") or "").strip(),
        "base_url": _anthropic_relay_base_url(str(raw.get("base_url", "") or "").strip())
        if backend == "anthropic"
        else str(raw.get("base_url", "") or "").strip(),
        "temperature": raw.get("temperature", None),
        "max_tokens": raw.get("max_tokens", None),
    }


def _global_embedding_override() -> dict:
    raw = get_global_model_settings()
    if not bool(raw.get("enabled", False)):
        return {}
    provider = str(raw.get("provider", "") or "").strip().lower()
    model = str(raw.get("embedding_model", "") or "").strip()
    if not provider or not model or not provider_supports_embeddings(provider):
        return {}
    return {
        "provider": provider,
        "model": model,
        "api_key": str(raw.get("api_key", "") or "").strip(),
        "base_url": str(raw.get("base_url", "") or "").strip(),
    }


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _local_backend_forced() -> bool:
    """Let a process-scoped local backend override persisted admin settings."""
    return str(os.getenv("MODEL_BACKEND", "") or "").strip().lower() == "local"


@lru_cache(maxsize=16)
def _build_chat_model_cached(
    provider: str,
    backend: str,
    temperature: float,
    openai_model: str,
    openai_api_key: str,
    openai_base_url: str,
    ollama_model: str,
    ollama_base_url: str,
    anthropic_model: str,
    anthropic_api_key: str,
    anthropic_base_url: str,
    max_tokens: int,
    request_timeout_seconds: float = 60.0,
):
    if backend == "local":
        return LocalEvidenceChatModel(model="local-evidence", temperature=temperature, max_tokens=max_tokens)

    if backend == "openai":
        from langchain_openai import ChatOpenAI

        kwargs = {
            "model": openai_model,
            "temperature": temperature,
            "streaming": True,  # Enable real-time streaming
            # Without this the HTTP call has no ceiling. The orchestration stage
            # timeout unblocks the event loop but cannot cancel the pool thread
            # running a blocking invoke(), so a hung provider connection pinned a
            # worker for the life of the process.
            "timeout": request_timeout_seconds,
        }
        if openai_api_key:
            kwargs["api_key"] = openai_api_key
        if openai_base_url:
            kwargs["base_url"] = openai_base_url
        if max_tokens > 0:
            kwargs["max_tokens"] = max_tokens
        return _wrap_chat_model_for_provider(ChatOpenAI(**kwargs), provider=provider)

    if backend == "anthropic":
        if anthropic_base_url:
            return _wrap_chat_model_for_provider(
                AnthropicRelayChatModel(
                    model=anthropic_model,
                    api_key=anthropic_api_key,
                    base_url=anthropic_base_url,
                    temperature=temperature,
                    max_tokens=max_tokens if max_tokens > 0 else 2048,
                    streaming=True,  # Enable real-time streaming
                ),
                provider=provider,
            )

        from langchain_anthropic import ChatAnthropic

        kwargs = {
            "model": anthropic_model,
            "temperature": temperature,
            "streaming": True,  # Enable real-time streaming
            "timeout": request_timeout_seconds,  # see the OpenAI branch
        }
        if anthropic_api_key:
            kwargs["api_key"] = anthropic_api_key
        if anthropic_base_url:
            kwargs["base_url"] = anthropic_base_url
        if max_tokens > 0:
            kwargs["max_tokens"] = max_tokens
        return _wrap_chat_model_for_provider(ChatAnthropic(**kwargs), provider=provider)

    from langchain_ollama import ChatOllama

    kwargs = {
        "model": ollama_model,
        "base_url": ollama_base_url,
        "temperature": temperature,
        "streaming": True,  # Enable real-time streaming
        # ChatOllama takes no `timeout` of its own; this is the only way to bound
        # the request. Without it a hung local server pins a pool thread for the
        # life of the process, exactly as the hosted clients used to.
        "client_kwargs": {"timeout": request_timeout_seconds},
    }
    if max_tokens > 0:
        kwargs["num_predict"] = max_tokens
    return ChatOllama(**kwargs)


@lru_cache(maxsize=4)
def _build_embedding_model_cached(
    provider: str,
    backend: str,
    openai_model: str,
    openai_api_key: str,
    openai_base_url: str,
    ollama_model: str,
    ollama_base_url: str,
):
    if backend == "local":
        return LocalHashEmbeddings()

    if backend == "openai":
        from langchain_openai import OpenAIEmbeddings

        kwargs = {"model": openai_model}
        if openai_api_key:
            kwargs["api_key"] = openai_api_key
        if openai_base_url:
            kwargs["base_url"] = openai_base_url
        return _wrap_embedding_model_for_provider(OpenAIEmbeddings(**kwargs), provider=provider)

    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(
        model=ollama_model,
        base_url=ollama_base_url,
    )


def get_chat_model(temperature: float | None = None):
    settings = get_settings()
    # Priority: Global admin settings (when enabled) > User settings > Environment variables
    global_override = {} if _local_backend_forced() else _global_chat_override()
    user_override = _request_chat_override()
    override = global_override or user_override
    if override:
        provider = str(override["provider"])
        backend = _normalize_backend(str(override.get("backend") or provider))
        effective_temperature = temperature if temperature is not None else override.get("temperature")
        model = str(override["model"])
        api_key = str(override.get("api_key", "") or "")
        base_url = str(override.get("base_url", "") or "")
        return _build_chat_model_cached(
            provider=provider,
            backend=backend,
            temperature=_normalize_runtime_temperature(provider, effective_temperature),
            openai_model=model if backend == "openai" else settings.openai_chat_model,
            openai_api_key=api_key if backend == "openai" else str(settings.openai_api_key or ""),
            openai_base_url=base_url if backend == "openai" else str(settings.openai_base_url or ""),
            ollama_model=model if backend == "ollama" else settings.ollama_chat_model,
            ollama_base_url=base_url if backend == "ollama" else settings.ollama_base_url,
            anthropic_model=model if backend == "anthropic" else settings.anthropic_chat_model,
            anthropic_api_key=api_key if backend == "anthropic" else str(settings.anthropic_api_key or ""),
            anthropic_base_url=base_url if backend == "anthropic" else "",
            max_tokens=_safe_int(override.get("max_tokens"), 0),
            request_timeout_seconds=float(settings.llm_request_timeout_seconds),
        )
    return _build_chat_model_cached(
        provider=str(settings.model_backend or ""),
        backend=_normalize_backend(settings.model_backend),
        temperature=_normalize_runtime_temperature(str(settings.model_backend or ""), temperature),
        openai_model=settings.openai_chat_model,
        openai_api_key=str(settings.openai_api_key or ""),
        openai_base_url=str(settings.openai_base_url or ""),
        ollama_model=settings.ollama_chat_model,
        ollama_base_url=settings.ollama_base_url,
        anthropic_model=settings.anthropic_chat_model,
        anthropic_api_key=str(settings.anthropic_api_key or ""),
        anthropic_base_url="",
        max_tokens=0,
        request_timeout_seconds=float(settings.llm_request_timeout_seconds),
    )


def get_embedding_model():
    settings = get_settings()
    override = {} if _local_backend_forced() else _global_embedding_override()
    if override:
        provider = str(override["provider"])
        backend = _normalize_backend(provider)
        return _build_embedding_model_cached(
            provider=provider,
            backend=backend,
            openai_model=str(override["model"]) if backend == "openai" else settings.openai_embed_model,
            openai_api_key=str(override.get("api_key", "") or "")
            if backend == "openai"
            else str(settings.openai_api_key or ""),
            openai_base_url=str(override.get("base_url", "") or "")
            if backend == "openai"
            else str(settings.openai_base_url or ""),
            ollama_model=str(override["model"]) if backend == "ollama" else settings.ollama_embed_model,
            ollama_base_url=str(override.get("base_url", "") or "")
            if backend == "ollama"
            else settings.ollama_base_url,
        )
    return _build_embedding_model_cached(
        provider=str(settings.model_backend or ""),
        backend=_normalize_backend(settings.model_backend),
        openai_model=settings.openai_embed_model,
        openai_api_key=str(settings.openai_api_key or ""),
        openai_base_url=str(settings.openai_base_url or ""),
        ollama_model=settings.ollama_embed_model,
        ollama_base_url=settings.ollama_base_url,
    )


def get_reasoning_model(temperature: float | None = None):
    settings = get_settings()
    # Priority: Global admin settings (when enabled) > User settings > Environment variables
    global_override = {} if _local_backend_forced() else _global_reasoning_override()
    user_override = _request_chat_override()
    override = global_override or user_override
    if override:
        provider = str(override["provider"])
        backend = _normalize_backend(str(override.get("backend") or provider))
        effective_temperature = temperature if temperature is not None else override.get("temperature")
        model = str(override["model"])
        api_key = str(override.get("api_key", "") or "")
        base_url = str(override.get("base_url", "") or "")
        return _build_chat_model_cached(
            provider=provider,
            backend=backend,
            temperature=_normalize_runtime_temperature(provider, effective_temperature),
            openai_model=model
            if backend == "openai"
            else (settings.openai_reasoning_model or settings.openai_chat_model),
            openai_api_key=api_key if backend == "openai" else str(settings.openai_api_key or ""),
            openai_base_url=base_url if backend == "openai" else str(settings.openai_base_url or ""),
            ollama_model=model
            if backend == "ollama"
            else (settings.ollama_reasoning_model or settings.ollama_chat_model),
            ollama_base_url=base_url if backend == "ollama" else settings.ollama_base_url,
            anthropic_model=model
            if backend == "anthropic"
            else (settings.anthropic_reasoning_model or settings.anthropic_chat_model),
            anthropic_api_key=api_key if backend == "anthropic" else str(settings.anthropic_api_key or ""),
            anthropic_base_url=base_url if backend == "anthropic" else "",
            max_tokens=_safe_int(override.get("max_tokens"), 0),
            request_timeout_seconds=float(settings.llm_request_timeout_seconds),
        )
    backend = _normalize_backend(settings.reasoning_model_backend or settings.model_backend)
    return _build_chat_model_cached(
        provider=str(settings.reasoning_model_backend or settings.model_backend or ""),
        backend=backend,
        temperature=_normalize_runtime_temperature(
            str(settings.reasoning_model_backend or settings.model_backend or ""), temperature
        ),
        openai_model=(settings.openai_reasoning_model or settings.openai_chat_model),
        openai_api_key=str(settings.openai_api_key or ""),
        openai_base_url=str(settings.openai_base_url or ""),
        ollama_model=(settings.ollama_reasoning_model or settings.ollama_chat_model),
        ollama_base_url=settings.ollama_base_url,
        anthropic_model=(settings.anthropic_reasoning_model or settings.anthropic_chat_model),
        anthropic_api_key=str(settings.anthropic_api_key or ""),
        anthropic_base_url="",
        max_tokens=0,
        request_timeout_seconds=float(settings.llm_request_timeout_seconds),
    )


def probe_chat_model_configuration(api_settings: dict, *, success_message: str) -> dict[str, object]:
    """Run the settings connectivity probe within the usual request runtime scope."""
    provider = str(api_settings["provider"])
    model_name = str(api_settings["model"])
    started = time.perf_counter()
    try:
        with request_context(timeout_ms=12000, overload_mode=False, api_settings=api_settings):
            model = get_chat_model(temperature=float(api_settings["temperature"]))
            probe_result = model.invoke(
                [("system", "You are a connectivity probe. Reply with exactly OK."), ("human", "Reply with OK.")]
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        preview = str(getattr(probe_result, "content", probe_result) or "").strip().replace("\n", " ")
        if len(preview) > 180:
            preview = preview[:177] + "..."
        return {
            "ok": True,
            "reachable": True,
            "provider": provider,
            "model": model_name,
            "latency_ms": latency_ms,
            "message": success_message,
            "preview": preview,
        }
    except Exception as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        reason = str(error) or type(error).__name__
        if len(reason) > 240:
            reason = reason[:237] + "..."
        return {
            "ok": False,
            "reachable": False,
            "provider": provider,
            "model": model_name,
            "latency_ms": latency_ms,
            "message": reason,
            "preview": "",
        }


def clear_model_caches() -> None:
    _build_chat_model_cached.cache_clear()
    _build_embedding_model_cached.cache_clear()
