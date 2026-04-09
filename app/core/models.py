from app.core.config import get_settings


def get_chat_model(temperature: float | None = None):
    settings = get_settings()
    temp = 0 if temperature is None else float(temperature)
    if settings.model_backend.lower() == "openai":
        from langchain_openai import ChatOpenAI

        kwargs = {"model": settings.openai_chat_model, "temperature": temp}
        if settings.openai_api_key:
            kwargs["api_key"] = settings.openai_api_key
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return ChatOpenAI(**kwargs)

    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.ollama_chat_model,
        base_url=settings.ollama_base_url,
        temperature=temp,
    )


def get_embedding_model():
    settings = get_settings()
    if settings.model_backend.lower() == "openai":
        from langchain_openai import OpenAIEmbeddings

        kwargs = {"model": settings.openai_embed_model}
        if settings.openai_api_key:
            kwargs["api_key"] = settings.openai_api_key
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return OpenAIEmbeddings(**kwargs)

    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


def get_reasoning_model(temperature: float | None = None):
    settings = get_settings()
    temp = 0 if temperature is None else float(temperature)
    backend = (settings.reasoning_model_backend or settings.model_backend).lower()
    if backend == "openai":
        from langchain_openai import ChatOpenAI

        kwargs = {"model": settings.openai_reasoning_model or settings.openai_chat_model, "temperature": temp}
        if settings.openai_api_key:
            kwargs["api_key"] = settings.openai_api_key
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return ChatOpenAI(**kwargs)

    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.ollama_reasoning_model or settings.ollama_chat_model,
        base_url=settings.ollama_base_url,
        temperature=temp,
    )
