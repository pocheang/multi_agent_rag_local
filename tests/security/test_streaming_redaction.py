"""A streamed answer must never show what the final answer would redact.

`output_filter` is the one stage with no degraded path, because skipping output
DLP is a hole rather than a degradation. Streaming tokens straight through is
that same hole spread over time: the user sees the secret and the redacted
version arrives afterwards.

The property under test is stronger than "the end result is clean": at no point
may the concatenation of what has been emitted contain something the final
redaction would have removed. These tests split secrets at every offset, because
a token boundary lands wherever the model happens to stop.
"""

from __future__ import annotations

import pytest

from app.privacy.streaming import StreamingRedactor, redact_final

_SECRETS = [
    "sk-abcdefghijklmnopqrstuvwxyz012345",
    "AKIAIOSFODNN7EXAMPLE",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "password = hunter2hunter2",
    "api_key: abcd1234efgh5678",
    "Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature",
    "contact me at alice@example.com",
    "the server is 192.168.1.42",
]


def _stream(text: str, split_at: int) -> str:
    """Feed `text` as two chunks split at `split_at`, return everything emitted."""
    redactor = StreamingRedactor()
    emitted = redactor.push(text[:split_at])
    emitted += redactor.push(text[split_at:])
    emitted += redactor.finish()
    return emitted


@pytest.mark.parametrize("secret", _SECRETS)
def test_no_split_point_ever_leaks_the_secret(secret):
    """The point of the exercise: a boundary lands wherever generation stops."""
    answer = f"Here is the detail you asked about: {secret} -- treat it carefully."
    expected = redact_final(answer)

    for split_at in range(len(answer) + 1):
        emitted = _stream(answer, split_at)
        assert emitted == expected, f"split at {split_at} produced {emitted!r}"


@pytest.mark.parametrize("secret", _SECRETS)
def test_a_secret_split_across_many_tiny_chunks_is_still_redacted(secret):
    """Token-sized chunks are the realistic case, not two halves."""
    answer = f"Prefix text. {secret} Suffix text that runs on for a while afterwards."
    redactor = StreamingRedactor()
    emitted = "".join(redactor.push(answer[index : index + 3]) for index in range(0, len(answer), 3))
    emitted += redactor.finish()

    assert emitted == redact_final(answer)


def test_nothing_is_emitted_before_the_margin_is_covered():
    """Early tokens are held back rather than guessed at."""
    redactor = StreamingRedactor()

    assert redactor.push("sk-abcdefghijklmnop") == ""


def test_the_stream_reassembles_into_the_final_answer():
    answer = "First sentence here. Second sentence follows it, and then a third one closes."
    redactor = StreamingRedactor()
    emitted = "".join(redactor.push(word + " ") for word in answer.split())
    emitted += redactor.finish()

    assert emitted.strip() == redact_final(answer).strip()


def test_clean_text_streams_through_unchanged():
    answer = "Revenue grew twelve percent in the fourth quarter, driven by renewals."
    redactor = StreamingRedactor()
    emitted = "".join(redactor.push(chunk) for chunk in (answer[:30], answer[30:]))
    emitted += redactor.finish()

    assert emitted == answer


def test_an_empty_stream_produces_nothing():
    redactor = StreamingRedactor()

    assert redactor.push("") == ""
    assert redactor.finish() == ""


def test_a_configured_custom_term_widens_the_margin(monkeypatch):
    """CUSTOM terms are arbitrary admin text, so the margin cannot be a constant."""
    from app.core.config import get_settings
    from app.privacy import streaming

    monkeypatch.setenv("OUTBOUND_REDACTION_CUSTOM_TERMS", "project " + ("x" * 200))
    get_settings.cache_clear()
    try:
        assert streaming._custom_term_margin() >= 200
    finally:
        get_settings.cache_clear()


# --- the property the patterns have to keep ---------------------------------


def test_every_whitespace_run_in_a_credential_pattern_is_bounded():
    """An unbounded `\\s*` means no finite look-back can prove a match is whole,
    which is what makes safe incremental redaction possible at all."""
    import re
    from pathlib import Path

    for module in ("app/services/answer_safety.py", "app/services/security/outbound_redaction.py"):
        source = Path(module).read_text(encoding="utf-8")
        # Only inside re.compile(...) lines; prose may say whatever it likes.
        for line in source.splitlines():
            if "re.compile(" not in line:
                continue
            assert not re.search(r"\\s[*+](?![{])", line), f"unbounded whitespace run in {module}: {line.strip()}"
