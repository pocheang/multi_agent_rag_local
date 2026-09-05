"""The one place an image is cleared to leave this machine.

There are two live paths that base64 a user's image into a provider payload --
`app/ingestion/extraction/vision.py` (captioning) and
`app/ingestion/extraction/charts.py` (chart data extraction, reached from the PDF
loader) -- and before 2026-09-05 neither inspected the image. Both call
`redact_messages_for_provider`, which is why it looked covered: there *is* an
outbound control on those payloads, it is a text control, the image travels as a
base64 data URI, and it correctly leaves that URI byte-identical.

`ImageMaskingService` was already written, already tested and reachable from
nothing. Rather than call it from each site, both go through here, so "which
providers are external" and "what happens when the image cannot be inspected"
have one answer. `is_external_provider` supplies the first -- ollama is not in it,
and a local endpoint is inside the same boundary as the OCR that does the
masking.

Fail-closed has a cost, and it is the honest one: the detector is Tesseract, so a
machine that cannot look at an image may not send it.
"""

from __future__ import annotations

import hashlib

from app.privacy.image_masking import ImageMaskingService
from app.privacy.models import ImageInput
from app.services.security.outbound_redaction import is_external_provider

__all__ = ["bytes_for_external_provider"]


def bytes_for_external_provider(image_bytes: bytes, provider: str) -> tuple[bytes, str]:
    """Return the bytes this provider may see, and the reason when it may see none.

    A non-empty second element means **do not send** -- it is the masking status
    or reason, suitable for reporting, and the first element is empty.

    A local provider gets the original: masking is an egress control, and there is
    no egress. An external one gets a derivative with sensitive regions painted
    out -- or nothing at all, if the regions could not be found.
    """

    if not is_external_provider(provider):
        return image_bytes, ""

    result = ImageMaskingService().mask(
        ImageInput(
            image_id=hashlib.sha1(image_bytes).hexdigest()[:16],
            content=image_bytes,
            media_type="image/png",
            processing_target="external",
        )
    )
    if not result.safe_for_external or not result.content:
        return b"", result.reason or result.status
    return result.content, ""
