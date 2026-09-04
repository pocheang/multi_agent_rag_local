"""An admin must be able to see what the model stack is actually doing.

Every other admin surface answers "what did I save". Three things make that a
different question from "what will the next question use", and all three are
silent:

* `MODEL_BACKEND=local` in the process environment discards the global override,
  so a saved OpenAI configuration can be stored and inert at once.
* The reranker and the NLI cross-encoder are loaded with `local_files_only=True`.
  A model that was never downloaded does not raise -- it returns None, and
  retrieval falls back to lexical scoring while validation falls back to a
  deterministic scorer. Both keep answering. From outside, degraded and healthy
  look the same.
* On the offline backend there is no language model at all, and the quality
  targets in CLAUDE.md describe a path that is not running.

`degraded` is the status worth having, so most of what is asserted here is that
each degraded state is actually reported. A view that could only ever say
"active" would be the same class of defect as a scanner whose checks match
nothing.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.models import effective as effective_module
from app.services.models.effective import effective_model_configuration


def _by_component(monkeypatch, **overrides):
    settings = get_settings().model_copy(update=overrides)
    monkeypatch.setattr(effective_module, "get_settings", lambda: settings)
    return {item.component: item for item in effective_model_configuration()}


@pytest.fixture(autouse=True)
def _no_optional_models(monkeypatch):
    """Neither optional model is loaded, which is the fresh-checkout state."""

    monkeypatch.setattr("app.retrievers.reranker._load_cross_encoder", lambda: None)
    monkeypatch.setattr("app.agents.validation.nli.load_nli_cross_encoder", lambda: None)
    monkeypatch.delenv("MODEL_BACKEND", raising=False)


def test_every_component_in_the_pipeline_is_reported():
    """The exact set, so a component added without a test here fails, and one
    quietly dropped fails too. Ordered the way a question moves through the
    system: an image is read and described at ingestion, then embedded, then
    retrieved and reranked, then answered and checked."""

    components = [item.component for item in effective_model_configuration()]

    assert components == ["ocr", "image_caption", "embedding", "reranker", "chat", "validation_nli"]


def test_a_reranker_whose_model_is_missing_is_degraded_not_active(monkeypatch):
    """The assertion that matters most: this state returns results and looks
    healthy, because `rerank_with_diagnostics` falls back to lexical scoring."""

    reranker = _by_component(monkeypatch, enable_reranker=True)["reranker"]

    assert reranker.status == "degraded"
    assert "lexical" in reranker.detail


def test_a_reranker_that_is_switched_off_is_disabled_not_degraded(monkeypatch):
    """Off on purpose and broken are different states; collapsing them would
    make the degraded signal meaningless."""

    reranker = _by_component(monkeypatch, enable_reranker=False)["reranker"]

    assert reranker.status == "disabled"


def test_a_present_reranker_is_active(monkeypatch):
    """The positive direction, so the degraded assertions cannot pass by the
    status being stuck."""

    monkeypatch.setattr("app.retrievers.reranker._load_cross_encoder", lambda: object())

    assert _by_component(monkeypatch, enable_reranker=True)["reranker"].status == "active"


def test_nli_without_its_model_is_degraded(monkeypatch):
    nli = _by_component(monkeypatch, cascade_enable_nli=True)["validation_nli"]

    assert nli.status == "degraded"
    assert "token overlap" in nli.detail


def test_a_present_nli_model_reports_the_language_limit(monkeypatch):
    """Active is not unqualified here: the configured model is English, so
    Chinese answers take the deterministic path even when it loads."""

    monkeypatch.setattr("app.agents.validation.nli.load_nli_cross_encoder", lambda: object())

    nli = _by_component(monkeypatch, cascade_enable_nli=True)["validation_nli"]

    assert nli.status == "active"
    assert "Chinese" in nli.detail


def test_the_offline_backend_is_degraded_for_chat_and_embedding(monkeypatch):
    """What a fresh checkout runs. Answers are assembled by a stand-in and
    embeddings are deterministic hashes -- neither is what the quality targets
    describe."""

    components = _by_component(monkeypatch, model_backend="local")

    assert components["chat"].status == "degraded"
    assert components["embedding"].status == "degraded"
    assert "offline" in components["chat"].detail


def test_a_configured_provider_is_active(monkeypatch):
    components = _by_component(monkeypatch, model_backend="openai", openai_chat_model="gpt-5.5")

    assert components["chat"].status == "active"
    assert components["chat"].configured == "gpt-5.5"


def test_an_environment_pin_is_reported_as_degraded_chat(monkeypatch):
    """The pin discards a saved provider config outright, so reporting the saved
    value alone would describe something that is not running."""

    monkeypatch.setenv("MODEL_BACKEND", "local")

    chat = _by_component(monkeypatch, model_backend="openai")["chat"]

    assert chat.status == "degraded"
    assert chat.source == "environment"


# --- the image path: OCR and captioning read together ------------------------


def test_captioning_off_says_what_that_costs(monkeypatch):
    """Off is a valid choice, but the consequence is not obvious: an image with
    no readable text is then not indexed at all."""

    caption = _by_component(monkeypatch, image_caption_enabled=False)["image_caption"]

    assert caption.status == "disabled"
    assert "not indexed" in caption.detail


def test_captioning_without_a_key_for_its_first_backend_is_degraded(monkeypatch):
    caption = _by_component(
        monkeypatch,
        image_caption_enabled=True,
        image_caption_backend="openai",
        openai_api_key="",
    )["image_caption"]

    assert caption.status == "degraded"
    assert "no API key" in caption.detail


def test_captioning_with_its_backend_configured_is_active(monkeypatch):
    caption = _by_component(
        monkeypatch,
        image_caption_enabled=True,
        image_caption_backend="ollama",
        ollama_vision_model="llava:7b",
    )["image_caption"]

    assert caption.status == "active"
    assert caption.configured == "llava:7b"


def test_the_backend_order_is_reported(monkeypatch):
    """`auto` follows MODEL_BACKEND and falls back, so which one is tried first
    is not something an operator can read off a single setting."""

    caption = _by_component(
        monkeypatch,
        image_caption_enabled=True,
        image_caption_backend="auto",
        model_backend="openai",
        openai_api_key="present",
    )["image_caption"]

    assert caption.metadata["order"] == "openai, ollama"


def test_missing_tesseract_is_reported_as_unavailable(monkeypatch):
    """The half that fails on a fresh machine, and the reason captioning matters."""

    monkeypatch.setattr("shutil.which", lambda _cmd: None)

    ocr = _by_component(monkeypatch)["ocr"]

    assert ocr.status == "unavailable"
    assert "captioning" in ocr.detail


def test_present_tesseract_is_active(monkeypatch):
    """The positive direction, so the assertion above cannot pass by the probe
    always failing."""

    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/tesseract")

    assert _by_component(monkeypatch)["ocr"].status == "active"
