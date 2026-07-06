import hashlib
import json
import math
import re
from functools import lru_cache
from types import SimpleNamespace

from app.api.utils.string_utils import normalize_string
from app.core.config import get_settings
from app.services.model_catalog import provider_supports_embeddings
from app.services.model_config_store import get_global_model_settings
from app.services.network_security import validate_api_base_url_for_provider
from app.services.outbound_redaction import (
    is_external_provider,
    redact_messages_for_provider,
    redact_texts_for_provider,
)
from app.services.request_context import get_request_api_settings


def _norm_temp(temperature: float | None) -> float:
    return round(0.0 if temperature is None else float(temperature), 3)


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
        for item in messages or []:
            if isinstance(item, tuple) and len(item) >= 2:
                role = str(item[0]).lower()
                content = str(item[1] or "")
            else:
                role = str(getattr(item, "type", getattr(item, "role", "")) or "").lower()
                content = str(getattr(item, "content", item) or "")
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

    def _extract_section(self, text: str, label: str) -> str:
        pattern = rf"{re.escape(label)}:\n(.*?)(?:\n\n[A-Za-z\u4e00-\u9fff]+上下文:|\n\n联网补充上下文:|\Z)"
        match = re.search(pattern, text, flags=re.DOTALL)
        return (match.group(1).strip() if match else "").strip()

    def _answer(self, payload: str) -> str:
        question = self._extract_section(payload, "用户问题") or payload.splitlines()[0:1][0] if payload else ""
        vector_context = self._extract_section(payload, "向量检索上下文")
        graph_context = self._extract_section(payload, "图谱上下文")
        web_context = self._extract_section(payload, "联网补充上下文")
        evidence = [x for x in [vector_context, graph_context, web_context] if x and x != "无"]
        if not evidence:
            return (
                "当前本地知识库没有检索到足够证据。你可以先上传 PDF、图片、Markdown 或 TXT 文档，"
                "系统会写入 Chroma 向量库、BM25 语料和 Neo4j 图谱后再回答。"
            )
        snippets: list[str] = []
        for block in evidence:
            clean = re.sub(r"\s+", " ", block).strip()
            if clean:
                snippets.append(clean[:360])
            if len(snippets) >= 4:
                break
        lines = [
            f"基于当前本地检索结果，我对“{question}”的回答如下：",
            "",
        ]
        for i, item in enumerate(snippets, 1):
            lines.append(f"{i}. {item}")
        lines.extend(
            [
                "",
                "说明：当前使用 local 离线后端，会优先做证据摘录和基础归纳；配置 Ollama/OpenAI 后可获得更强的生成与推理能力。",
            ]
        )
        return "\n".join(lines)

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
        return SimpleNamespace(content=self._answer(human_text))

    def stream(self, messages):
        yield SimpleNamespace(content=self.invoke(messages).content)


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
        for item in messages or []:
            if isinstance(item, tuple) and len(item) >= 2:
                role = str(item[0]).lower()
                content = str(item[1] or "")
            else:
                role = str(getattr(item, "type", getattr(item, "role", "")) or "").lower()
                content = str(getattr(item, "content", item) or "")
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
    if provider == "custom" and _looks_like_claude_model(model):
        provider = "anthropic"
        base_url = _anthropic_relay_base_url(base_url)
    return {
        "provider": provider,
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
    if provider == "custom" and _looks_like_claude_model(model):
        provider = "anthropic"
    return {
        "provider": provider,
        "model": model,
        "api_key": str(raw.get("api_key", "") or "").strip(),
        "base_url": _anthropic_relay_base_url(str(raw.get("base_url", "") or "").strip())
        if provider == "anthropic"
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
    if provider == "custom" and _looks_like_claude_model(model):
        provider = "anthropic"
    return {
        "provider": provider,
        "model": model,
        "api_key": str(raw.get("api_key", "") or "").strip(),
        "base_url": _anthropic_relay_base_url(str(raw.get("base_url", "") or "").strip())
        if provider == "anthropic"
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
):
    if backend == "local":
        return LocalEvidenceChatModel(model="local-evidence", temperature=temperature, max_tokens=max_tokens)

    if backend == "openai":
        from langchain_openai import ChatOpenAI

        kwargs = {"model": openai_model, "temperature": temperature}
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
                ),
                provider=provider,
            )

        from langchain_anthropic import ChatAnthropic

        kwargs = {"model": anthropic_model, "temperature": temperature}
        if anthropic_api_key:
            kwargs["api_key"] = anthropic_api_key
        if anthropic_base_url:
            kwargs["base_url"] = anthropic_base_url
        if max_tokens > 0:
            kwargs["max_tokens"] = max_tokens
        return _wrap_chat_model_for_provider(ChatAnthropic(**kwargs), provider=provider)

    from langchain_ollama import ChatOllama

    kwargs = dict(
        model=ollama_model,
        base_url=ollama_base_url,
        temperature=temperature,
    )
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
    global_override = _global_chat_override()
    user_override = _request_chat_override()
    override = global_override or user_override
    if override:
        provider = str(override["provider"])
        backend = _normalize_backend(provider)
        effective_temperature = temperature if temperature is not None else override.get("temperature")
        model = str(override["model"])
        api_key = str(override.get("api_key", "") or "")
        base_url = str(override.get("base_url", "") or "")
        return _build_chat_model_cached(
            provider=provider,
            backend=backend,
            temperature=_norm_temp(effective_temperature),
            openai_model=model if backend == "openai" else settings.openai_chat_model,
            openai_api_key=api_key if backend == "openai" else str(settings.openai_api_key or ""),
            openai_base_url=base_url if backend == "openai" else str(settings.openai_base_url or ""),
            ollama_model=model if backend == "ollama" else settings.ollama_chat_model,
            ollama_base_url=base_url if backend == "ollama" else settings.ollama_base_url,
            anthropic_model=model if backend == "anthropic" else settings.anthropic_chat_model,
            anthropic_api_key=api_key if backend == "anthropic" else str(settings.anthropic_api_key or ""),
            anthropic_base_url=base_url if backend == "anthropic" else "",
            max_tokens=_safe_int(override.get("max_tokens"), 0),
        )
    return _build_chat_model_cached(
        provider=str(settings.model_backend or ""),
        backend=_normalize_backend(settings.model_backend),
        temperature=_norm_temp(temperature),
        openai_model=settings.openai_chat_model,
        openai_api_key=str(settings.openai_api_key or ""),
        openai_base_url=str(settings.openai_base_url or ""),
        ollama_model=settings.ollama_chat_model,
        ollama_base_url=settings.ollama_base_url,
        anthropic_model=settings.anthropic_chat_model,
        anthropic_api_key=str(settings.anthropic_api_key or ""),
        anthropic_base_url="",
        max_tokens=0,
    )


def get_embedding_model():
    settings = get_settings()
    override = _global_embedding_override()
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
    global_override = _global_reasoning_override()
    user_override = _request_chat_override()
    override = global_override or user_override
    if override:
        provider = str(override["provider"])
        backend = _normalize_backend(provider)
        effective_temperature = temperature if temperature is not None else override.get("temperature")
        model = str(override["model"])
        api_key = str(override.get("api_key", "") or "")
        base_url = str(override.get("base_url", "") or "")
        return _build_chat_model_cached(
            provider=provider,
            backend=backend,
            temperature=_norm_temp(effective_temperature),
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
        )
    backend = _normalize_backend(settings.reasoning_model_backend or settings.model_backend)
    return _build_chat_model_cached(
        provider=str(settings.reasoning_model_backend or settings.model_backend or ""),
        backend=backend,
        temperature=_norm_temp(temperature),
        openai_model=(settings.openai_reasoning_model or settings.openai_chat_model),
        openai_api_key=str(settings.openai_api_key or ""),
        openai_base_url=str(settings.openai_base_url or ""),
        ollama_model=(settings.ollama_reasoning_model or settings.ollama_chat_model),
        ollama_base_url=settings.ollama_base_url,
        anthropic_model=(settings.anthropic_reasoning_model or settings.anthropic_chat_model),
        anthropic_api_key=str(settings.anthropic_api_key or ""),
        anthropic_base_url="",
        max_tokens=0,
    )


def clear_model_caches() -> None:
    _build_chat_model_cached.cache_clear()
    _build_embedding_model_cached.cache_clear()
