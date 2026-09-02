"""The answer safety scan must honour its settings flag.

sanitize_answer returned {"enabled": True} unconditionally and never read
ANSWER_SAFETY_SCAN_ENABLED, so the flag was inert and the report lied whenever
an operator believed they had turned the scan off.
"""

from __future__ import annotations

from app.services import answer_safety


def test_openai_style_key_is_redacted():
    text, meta = answer_safety.sanitize_answer("key is sk-abcdefghijklmnop1234")
    assert "sk-abcdefghijklmnop1234" not in text
    assert meta == {"enabled": True, "redactions": 1}


def test_aws_key_and_private_key_header_are_redacted():
    text, meta = answer_safety.sanitize_answer("AKIAIOSFODNN7EXAMPLE and -----BEGIN RSA KEY----- and password=hunter22")
    assert "AKIAIOSFODNN7EXAMPLE" not in text
    assert "BEGIN RSA KEY" not in text
    assert "hunter22" not in text
    assert meta["redactions"] == 3


def test_clean_text_is_untouched():
    text, meta = answer_safety.sanitize_answer("Paris is the capital of France [E1].")
    assert text == "Paris is the capital of France [E1]."
    assert meta == {"enabled": True, "redactions": 0}


def test_scan_can_be_disabled(monkeypatch):
    class _Settings:
        answer_safety_scan_enabled = False

    monkeypatch.setattr(answer_safety, "get_settings", lambda: _Settings())
    original = "key is sk-abcdefghijklmnop1234"
    text, meta = answer_safety.sanitize_answer(original)
    assert text == original
    assert meta == {"enabled": False, "redactions": 0}


def test_empty_input_is_safe():
    assert answer_safety.sanitize_answer("") == ("", {"enabled": True, "redactions": 0})
    assert answer_safety.sanitize_answer(None) == ("", {"enabled": True, "redactions": 0})
