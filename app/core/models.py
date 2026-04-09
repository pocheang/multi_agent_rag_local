from functools import lru_cache

from app.core.config import get_settings


def _norm_temp(temperature: float | None) -> float:
    return round(0.0 if temperature is None else float(temperature), 3)


def _normalize_backend(backend: str) -> str:
    b = str(backend or "").strip().lower()
    if b not in {"openai", "ollama"}:
        raise ValueError(f"unsupported model backend: {backend}")
    return b


@lru_cache(maxsize=16)
def _build_chat_model_cached(
    backend: str,
    temperature: float,
    openai_model: str,
    openai_api_key: str,
    openai_base_url: str,
    ollama_model: str,
    ollama_base_url: str,
):
    if backend == "openai":
        from langchain_openai import ChatOpenAI

        kwargs = {"model": openai_model, "temperature": temperature}
        if openai_api_key:
            kwargs["api_key"] = openai_api_key
        if openai_base_url:
            kwargs["base_url"] = openai_base_url
        return ChatOpenAI(**kwargs)

    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=ollama_model,
        base_url=ollama_base_url,
        temperature=temperature,
    )


@lru_cache(maxsize=4)
def _build_embedding_model_cached(
    backend: str,
    openai_model: str,
    openai_api_key: str,
    openai_base_url: str,
    ollama_model: str,
    ollama_base_url: str,
):
    if backend == "openai":
        from langchain_openai import OpenAIEmbeddings

        kwargs = {"model": openai_model}
        if openai_api_key:
            kwargs["api_key"] = openai_api_key
        if openai_base_url:
            kwargs["base_url"] = openai_base_url
        return OpenAIEmbeddings(**kwargs)

    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(
        model=ollama_model,
        base_url=ollama_base_url,
    )


def get_chat_model(temperature: float | None = None):
    settings = get_settings()
    return _build_chat_model_cached(
        backend=_normalize_backend(settings.model_backend),
        temperature=_norm_temp(temperature),
        openai_model=settings.openai_chat_model,
        openai_api_key=str(settings.openai_api_key or ""),
        openai_base_url=str(settings.openai_base_url or ""),
        ollama_model=settings.ollama_chat_model,
        ollama_base_url=settings.ollama_base_url,
    )


def get_embedding_model():
    settings = get_settings()
    return _build_embedding_model_cached(
        backend=_normalize_backend(settings.model_backend),
        openai_model=settings.openai_embed_model,
        openai_api_key=str(settings.openai_api_key or ""),
        openai_base_url=str(settings.openai_base_url or ""),
        ollama_model=settings.ollama_embed_model,
        ollama_base_url=settings.ollama_base_url,
    )


def get_reasoning_model(temperature: float | None = None):
    settings = get_settings()
    backend = _normalize_backend(settings.reasoning_model_backend or settings.model_backend)
    return _build_chat_model_cached(
        backend=backend,
        temperature=_norm_temp(temperature),
        openai_model=(settings.openai_reasoning_model or settings.openai_chat_model),
        openai_api_key=str(settings.openai_api_key or ""),
        openai_base_url=str(settings.openai_base_url or ""),
        ollama_model=(settings.ollama_reasoning_model or settings.ollama_chat_model),
        ollama_base_url=settings.ollama_base_url,
    )


def clear_model_caches() -> None:
    _build_chat_model_cached.cache_clear()
    _build_embedding_model_cached.cache_clear()
