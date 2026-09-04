"""What the model stack is *actually* doing, as opposed to what is stored.

Every other admin surface answers "what did I save". This one answers "what will
the next question use", and the two come apart in ways that are individually
documented and collectively invisible:

* `MODEL_BACKEND=local` in the process environment discards the global override
  entirely (`_local_backend_forced`), so a saved OpenAI configuration can be
  stored and inert at once.
* A user's personal API settings are used when no global override is enabled, so
  "the configured model" is not one value for the whole deployment.
* The reranker and the NLI cross-encoder are both loaded with
  `local_files_only=True`. A model that was never downloaded does not raise --
  it returns `None`, and retrieval quietly falls back to lexical scoring while
  validation quietly falls back to a deterministic one. Nothing in the product
  said so, and a degraded stage looks exactly like a healthy one from outside.

So each component reports a status rather than a value alone. `degraded` is the
state worth having: configured, running, and not doing what its name implies.

**Probing loads the optional models.** Both loaders are cached for the life of
the process and both are local-only, so the cost is paid once and is the same
cost the first real query would pay -- but it is a cost, and it is why this lives
behind an admin endpoint rather than on a health check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.core.config import get_settings

ComponentStatus = Literal["active", "degraded", "disabled", "unavailable"]


@dataclass(frozen=True)
class EffectiveComponent:
    """One model in the stack, and whether it is doing its job."""

    component: str
    status: ComponentStatus
    configured: str
    detail: str
    source: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


def _chat() -> EffectiveComponent:
    from app.services.models.config_store import get_global_model_settings
    from app.services.models.runtime import _local_backend_forced, _normalize_backend

    settings = get_settings()
    stored = get_global_model_settings()
    enabled = bool(stored.get("enabled", False))

    if _local_backend_forced():
        return EffectiveComponent(
            component="chat",
            status="degraded",
            configured=str(stored.get("chat_model") or settings.openai_chat_model),
            source="environment",
            detail=(
                "MODEL_BACKEND=local is pinned in the process environment, so every answer "
                "comes from the offline stand-in and any saved provider settings are ignored."
            ),
        )
    if enabled and stored.get("provider") and stored.get("chat_model"):
        return EffectiveComponent(
            component="chat",
            status="active",
            configured=str(stored["chat_model"]),
            source="admin global override",
            detail="The global override is on, so it applies to every user, including those with personal settings.",
            metadata={"provider": str(stored["provider"])},
        )

    backend = _normalize_backend(settings.model_backend)
    if backend == "local":
        return EffectiveComponent(
            component="chat",
            status="degraded",
            configured="local",
            source="MODEL_BACKEND",
            detail=(
                "No provider is configured, so answers are assembled by the offline stand-in "
                "rather than a language model. Router accuracy and answer quality targets do "
                "not describe this path."
            ),
        )
    model = {
        "openai": settings.openai_chat_model,
        "anthropic": settings.anthropic_chat_model,
        "ollama": settings.ollama_chat_model,
    }.get(backend, "")
    return EffectiveComponent(
        component="chat",
        status="active",
        configured=str(model or backend),
        source="MODEL_BACKEND",
        detail="Users with personal API settings use their own; no global override is enabled.",
        metadata={"provider": backend},
    )


def _embedding() -> EffectiveComponent:
    from app.services.models.runtime import _normalize_backend

    settings = get_settings()
    backend = _normalize_backend(settings.model_backend)
    if backend == "local":
        return EffectiveComponent(
            component="embedding",
            status="degraded",
            configured="local hash embeddings",
            source="MODEL_BACKEND",
            detail=(
                "Deterministic hash embeddings, not a semantic model: vector search will "
                "match on little more than exact overlap."
            ),
        )
    model = settings.openai_embed_model if backend == "openai" else settings.ollama_embed_model
    return EffectiveComponent(
        component="embedding",
        status="active",
        configured=str(model),
        source="MODEL_BACKEND",
        detail="Chunks are embedded with this model; changing it requires a reindex.",
        metadata={"provider": backend},
    )


def _reranker() -> EffectiveComponent:
    from app.retrievers.reranker import _load_cross_encoder

    settings = get_settings()
    name = str(settings.reranker_model_name)
    if not settings.enable_reranker:
        return EffectiveComponent(
            component="reranker",
            status="disabled",
            configured=name,
            source="ENABLE_RERANKER",
            detail="Fused results are truncated to the top N without reranking.",
        )
    if _load_cross_encoder() is None:
        return EffectiveComponent(
            component="reranker",
            status="degraded",
            configured=name,
            source="RERANKER_MODEL_NAME",
            detail=(
                f"Reranking is on but '{name}' is not available locally, so retrieval falls back "
                "to lexical scoring. Download the model or turn reranking off; leaving it here "
                "reports a cross-encoder that never runs."
            ),
        )
    return EffectiveComponent(
        component="reranker",
        status="active",
        configured=name,
        source="RERANKER_MODEL_NAME",
        detail="Fused results are reordered by the cross-encoder.",
    )


def _nli() -> EffectiveComponent:
    from app.agents.validation.nli import load_nli_cross_encoder

    settings = get_settings()
    name = str(settings.nli_model_name)
    if not settings.cascade_enable_nli:
        return EffectiveComponent(
            component="validation_nli",
            status="disabled",
            configured=name,
            source="CASCADE_ENABLE_NLI",
            detail="Answers are not checked sentence by sentence for entailment.",
        )
    if load_nli_cross_encoder() is None:
        return EffectiveComponent(
            component="validation_nli",
            status="degraded",
            configured=name,
            source="NLI_MODEL_NAME",
            detail=(
                f"'{name}' is not available locally, so entailment is scored by token overlap "
                "instead. That is a real check, but a weaker one than the name suggests."
            ),
        )
    return EffectiveComponent(
        component="validation_nli",
        status="active",
        configured=name,
        source="NLI_MODEL_NAME",
        detail=(
            "The cross-encoder scores predominantly-Latin answers; Chinese answers take the "
            "deterministic path, because this model is English."
        ),
    )


def _vision_backends(settings) -> list[str]:
    """The order `describe_image_with_vision` will try, mirrored here.

    Mirrored rather than imported because that function needs image bytes: the
    order is a property of the configuration and is worth reporting before any
    image exists.
    """

    backend = str(getattr(settings, "image_caption_backend", "auto") or "auto").lower()
    if backend in {"openai", "ollama"}:
        return [backend]
    preferred = str(settings.model_backend or "local").lower()
    if preferred in {"openai", "anthropic", "deepseek", "custom"}:
        return ["openai", "ollama"]
    return ["ollama", "openai"]


def _vision() -> EffectiveComponent:
    """Image captioning: configuration readiness, not liveness.

    Deliberately makes no network call. The other components here probe a local
    file, which is bounded; reaching a vision endpoint is not, and an admin page
    that can hang on a misconfigured base URL is worse than one that reports what
    it can check. So this answers "could this work" -- switched on, a backend
    chosen, a credential present -- and leaves "does it work" to ingestion.
    """

    settings = get_settings()
    if not getattr(settings, "image_caption_enabled", False):
        return EffectiveComponent(
            component="image_caption",
            status="disabled",
            configured="",
            source="IMAGE_CAPTION_ENABLED",
            detail=(
                "Images are indexed from OCR text alone, so a photo or diagram with no "
                "readable text is not indexed at all."
            ),
        )

    order = _vision_backends(settings)
    first = order[0]
    model = settings.openai_vision_model if first == "openai" else settings.ollama_vision_model
    if first == "openai" and not str(settings.openai_api_key or "").strip():
        alternative = "; ollama is tried next" if "ollama" in order[1:] else ""
        return EffectiveComponent(
            component="image_caption",
            status="degraded",
            configured=str(model or ""),
            source="IMAGE_CAPTION_BACKEND",
            detail=f"Captioning is on and the OpenAI backend has no API key{alternative}.",
            metadata={"order": ", ".join(order)},
        )
    return EffectiveComponent(
        component="image_caption",
        status="active",
        configured=str(model or first),
        source="IMAGE_CAPTION_BACKEND",
        detail=(
            "Images are described during ingestion. This is configuration readiness -- "
            "whether the endpoint answers is only known once an image is ingested."
        ),
        metadata={"order": ", ".join(order)},
    )


def _ocr() -> EffectiveComponent:
    """Tesseract: importable, and a binary the process can actually find.

    The other half of image indexing, and the half that fails on a fresh machine.
    Its absence is the reason captioning matters, so the two read together.
    """

    import shutil

    settings = get_settings()
    command = str(getattr(settings, "tesseract_cmd", "") or "") or "tesseract"
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return EffectiveComponent(
            component="ocr",
            status="unavailable",
            configured=command,
            source="pytesseract",
            detail="pytesseract is not installed, so no text is read out of images.",
        )
    if shutil.which(command) is None:
        return EffectiveComponent(
            component="ocr",
            status="unavailable",
            configured=command,
            source="TESSERACT_CMD",
            detail=(
                f"pytesseract is installed but '{command}' is not on PATH, so OCR reads nothing. "
                "Images are still searchable if captioning is on."
            ),
        )
    return EffectiveComponent(
        component="ocr",
        status="active",
        configured=command,
        source="TESSERACT_CMD",
        detail="Text is read out of images during ingestion.",
    )


def effective_model_configuration() -> list[EffectiveComponent]:
    """Report every model in the stack, degraded ones included.

    Ordered the way the pipeline uses them, not by importance -- an operator
    reading top to bottom follows a question through the system.
    """

    return [_ocr(), _vision(), _embedding(), _reranker(), _chat(), _nli()]


__all__ = ["ComponentStatus", "EffectiveComponent", "effective_model_configuration"]
