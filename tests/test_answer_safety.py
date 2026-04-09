from app.services.answer_safety import sanitize_answer


def test_answer_safety_redacts_secret_like_tokens():
    text = "token=sk-ABCDEF1234567890 and AKIAABCDEFGHIJKLMNOP"
    out, report = sanitize_answer(text)
    assert "[REDACTED]" in out
    assert report["redactions"] >= 1
