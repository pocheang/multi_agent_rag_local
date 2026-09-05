"""A user's image must be inspected before it leaves this machine.

`ImageMaskingService` (`app/privacy/image_masking.py`) finds sensitive text
regions with local OCR, paints them out, and **fails closed**: asked for an
"external" derivative it cannot produce, it returns `safe_for_external=False`
and no content. It works, it is tested, and until 2026-09-05 nothing on any live
path called it. Its two entry points were `ImageProcessor._masked_bytes` -- whose
own docstring says "Fail closed so OCR and every external VLM consume only a safe
derivative", on a class ingestion constructs but calls exactly one *other* method
on -- and `PrivacyService.mask_images`, which has no callers either.

Meanwhile `describe_image_with_vision` base64'd the image as uploaded and posted
it to OpenAI. It does call `redact_messages_for_provider`, which is why this was
easy to miss: there *is* an outbound control on that payload, it is simply the
wrong kind. It redacts text, the image travels as a base64 data URI, and it
correctly leaves that URI byte-identical -- pinned below, because "the redactor
runs here" is exactly the reasoning that made the gap invisible.

`IMAGE_CAPTION_ENABLED` defaults false, so this was latent rather than shipping.
It stopped being latent when the switch became editable from the admin page.
"""

from __future__ import annotations

import base64
import io
import json
from types import SimpleNamespace

import pytest

from app.ingestion.extraction import vision as vision_module
from app.privacy import image_egress as egress_module
from app.privacy.image_masking import ImageMaskingService, ImageMaskingUnavailable
from app.privacy.models import SensitiveRegion


def _png(colour: str = "white") -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (120, 60), colour).save(buffer, format="PNG")
    return buffer.getvalue()


class _FoundSomething:
    """A detector that reports one sensitive region, so masking really redraws."""

    def detect(self, image):
        return (SensitiveRegion(x=5, y=5, width=40, height=20, kind="ID_CARD_CN"),)


class _CannotLook:
    """Tesseract missing -- the fresh-machine state, and the fail-closed case."""

    def detect(self, image):
        raise ImageMaskingUnavailable("local OCR detector is unavailable")


class _Nothing:
    def detect(self, image):
        return ()


@pytest.fixture
def sent(monkeypatch):
    """Capture what actually goes over the wire, per backend."""

    calls: list[tuple[str, dict]] = []

    class _Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{"message": {"content": "a description"}}],
                "message": {"content": "a description"},
            }

    class _Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def post(self, url, **kwargs):
            calls.append((url, kwargs.get("json") or {}))
            return _Response()

    monkeypatch.setattr(vision_module, "httpx", SimpleNamespace(Client=_Client))
    return calls


def _settings(**overrides):
    base = {
        "image_caption_enabled": True,
        "image_caption_backend": "openai",
        "openai_api_key": "test-key",
        "openai_base_url": "https://api.openai.com",
        "openai_vision_model": "gpt-4o",
        "openai_chat_model": "gpt-5.5",
        "ollama_vision_model": "llava:7b",
        "ollama_base_url": "http://localhost:11434",
        "model_backend": "openai",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _use_detector(monkeypatch, detector):
    """Patch the shared helper, not each caller.

    `app/privacy/image_egress.py` is the one place that decides what an external
    provider may see, which is the property being tested -- a per-call-site fake
    would pass while a second send path went uncovered, and that is exactly what
    happened: `charts.py` was found this way.
    """

    monkeypatch.setattr(egress_module, "ImageMaskingService", lambda: ImageMaskingService(detector=detector))


def _image_bytes_in(payload: dict) -> bytes:
    """The image as the provider received it."""

    for part in payload["messages"][1]["content"]:
        if part.get("type") == "image_url":
            return base64.b64decode(part["image_url"]["url"].split("base64,", 1)[1])
    raise AssertionError("no image in the payload")


def test_an_external_backend_never_sees_the_original_bytes(monkeypatch, sent):
    """The assertion that would have caught it."""

    _use_detector(monkeypatch, _FoundSomething())
    original = _png()

    result = vision_module.describe_image_with_vision(original, _settings())

    assert result["status"] == "ok"
    assert len(sent) == 1
    assert _image_bytes_in(sent[0][1]) != original


def test_an_image_with_nothing_sensitive_is_sent_unchanged(monkeypatch, sent):
    """Masking is not a blanket re-encode; the negative direction keeps the
    assertion above from passing because *everything* is altered."""

    _use_detector(monkeypatch, _Nothing())
    original = _png()

    vision_module.describe_image_with_vision(original, _settings())

    assert _image_bytes_in(sent[0][1]) == original


def test_an_image_that_cannot_be_inspected_is_not_sent(monkeypatch, sent):
    """Fail closed. Not being able to look at an image is a reason to keep it,
    not a reason to send it and hope."""

    _use_detector(monkeypatch, _CannotLook())

    result = vision_module.describe_image_with_vision(_png(), _settings())

    assert sent == [], "the image was posted despite masking being unavailable"
    assert result["status"] == "image_masking_blocked"
    assert result["caption"] == ""


def test_the_auto_order_degrades_to_the_local_backend(monkeypatch, sent):
    """What keeps fail-closed from silently removing captioning on a machine
    without Tesseract -- which is the machine captioning exists for."""

    _use_detector(monkeypatch, _CannotLook())

    result = vision_module.describe_image_with_vision(_png(), _settings(image_caption_backend="auto"))

    assert result["status"] == "ok"
    assert len(sent) == 1
    assert "11434" in sent[0][0], "expected the local backend to have answered"


def test_a_local_backend_is_not_masked(monkeypatch, sent):
    """`is_external_provider` draws this line and excludes ollama; reusing it
    rather than writing a second list is the point. A local endpoint is inside
    the same boundary as the OCR that would do the masking."""

    _use_detector(monkeypatch, _FoundSomething())
    original = _png()

    vision_module.describe_image_with_vision(original, _settings(image_caption_backend="ollama"))

    payload = sent[0][1]
    assert base64.b64decode(payload["messages"][1]["images"][0]) == original


def test_the_text_redactor_is_not_a_control_over_image_content():
    """Why the gap was invisible: an outbound redactor *does* run on this
    payload. It is a text control, the image is a base64 data URI, and it leaves
    that URI byte-identical -- correctly. Pinned so nobody reasons from its
    presence to the image being covered."""

    from app.services.security.outbound_redaction import redact_messages_for_provider

    encoded = base64.b64encode(_png()).decode("ascii")
    messages = [
        {"role": "system", "content": "describe"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "please describe"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
            ],
        },
    ]

    redacted = redact_messages_for_provider(json.loads(json.dumps(messages)), provider="openai")

    assert redacted[1]["content"][1]["image_url"]["url"].endswith(encoded)


# --- the guard that would have found the second path ----------------------


def test_every_module_that_sends_an_image_clears_it_first():
    """The assertion that caught `charts.py`.

    The first version of this fix covered `vision.py` and stopped there, and the
    PDF loader's chart extractor -- `dispatch.py` -> `extract_charts_from_pdf` ->
    `extract_chart_data_with_vision` -> OpenAI or Anthropic -- was still posting
    raw image bytes. A boundary that only appears to be guarded is worse than an
    unguarded one, so the property is checked over the whole tree rather than
    asserted about the one module somebody remembered.

    Both defaults are off (`IMAGE_CAPTION_ENABLED`, `PDF_ENABLE_CHART_EXTRACTION`),
    which is why neither showed up as an incident, and is not a reason to leave
    either uncovered.
    """

    from pathlib import Path

    _PAYLOAD_MARKERS = ("image_url", '"type": "image"', '"images"')
    offenders = []

    for path in Path("app").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "b64encode" not in source:
            continue
        if not any(marker in source for marker in _PAYLOAD_MARKERS):
            continue
        if "bytes_for_external_provider" not in source:
            offenders.append(str(path))

    assert not offenders, f"these base64 an image into a provider payload without clearing it first: {offenders}"


def test_the_guard_above_is_actually_looking_at_something():
    """A scan that matches nothing reports PASS just as readily as one that
    matches everything -- the lesson this repository records for its
    sensitive-content gate. Two modules send images today."""

    from pathlib import Path

    senders = [
        path
        for path in Path("app").rglob("*.py")
        if "b64encode" in path.read_text(encoding="utf-8")
        and "bytes_for_external_provider" in path.read_text(encoding="utf-8")
    ]

    assert len(senders) >= 2, f"expected both send paths to be covered, found {senders}"
