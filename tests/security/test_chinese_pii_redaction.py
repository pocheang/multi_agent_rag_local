"""China-specific identifiers must be redacted, and labelled as what they are.

Until 2026-09-04 this repository had no China-specific PII pattern at all, in a
product whose stated reason for existing is that it works in Chinese. Three of
the four commonest identifiers were caught anyway, by accident: a resident ID
card, a bank card and a mainland mobile number are all long runs of digits, so
the generic `PHONE` rule swallowed them.

Accidental coverage is still coverage, and none of these tests would have failed
on the leak. What did fail was everything built on the label. `PrivacyFinding`
carries the kind, `filter_output` returns the counts, and both said PHONE -- so
a privacy report described something that had not happened, and a passport
number (eight digits, one short of the generic rule's minimum) was reported as
nothing at all.

The ordering test is the load-bearing one. Patterns are applied in sequence and
the first to match owns the span, so a specific rule placed after the generic
one is indistinguishable from not having written it.
"""

from __future__ import annotations

import pytest

from app.agents.rag.web import _sanitize_query
from app.privacy.text import INPUT_KINDS, OUTPUT_KINDS, inspect_text
from app.services.security.outbound_redaction import _BASE_PATTERNS


def _kinds(text: str) -> dict[str, int]:
    return {finding.kind: finding.count for finding in inspect_text(text).findings}


# --- the identifiers, and what they must be called ------------------------


@pytest.mark.parametrize(
    ("kind", "sample"),
    [
        ("ID_CARD_CN", "身份证号是 110101199003072316"),
        ("MOBILE_CN", "手机 13812345678"),
        ("BANK_CARD", "卡号 6222021234567890123"),
        ("PASSPORT_CN", "护照 E12345678"),
        ("USCC_CN", "统一社会信用代码 91310000MA1FL0000X"),
    ],
)
def test_the_identifier_is_redacted_under_its_own_kind(kind: str, sample: str) -> None:
    found = _kinds(sample)
    assert kind in found, f"expected {kind}, got {found or 'nothing'}"
    assert inspect_text(sample).text != sample
    assert f"<{kind}_1>" in inspect_text(sample).text


def test_a_passport_number_was_invisible_to_the_generic_rule() -> None:
    """Eight digits: one short of what `PHONE` requires, so it used to pass."""
    assert "PASSPORT_CN" in _kinds("护照 E12345678")


@pytest.mark.parametrize(
    ("sample", "expected"),
    [
        ("110101199003072316", "ID_CARD_CN"),
        ("13812345678", "MOBILE_CN"),
        ("6222021234567890123", "BANK_CARD"),
    ],
)
def test_a_specific_rule_beats_the_generic_digit_run(sample: str, expected: str) -> None:
    """Put PHONE ahead of these in _BASE_PATTERNS and this is what breaks."""
    found = _kinds(sample)
    assert found == {expected: 1}, f"{sample} was reported as {found}"


def test_a_western_phone_number_is_still_a_phone() -> None:
    assert _kinds("call +1 415 555 0132") == {"PHONE": 1}


# --- IPv6 -----------------------------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "2001:db8::8a2e:370:7334",
        "2001:db8::1",
        "::1",
    ],
)
def test_ipv6_is_redacted_as_an_address(address: str) -> None:
    assert _kinds(f"host {address}") == {"IP": 1}


# --- the structural trap --------------------------------------------------


def test_every_pattern_kind_is_reachable() -> None:
    """A kind missing from PII_KINDS is filtered out and its pattern never runs.

    `redact_sensitive_text` skips any kind outside `allowed_kinds`, so adding a
    pattern to outbound_redaction.py without adding its kind to app/privacy/text.py
    produces a rule that compiles, reads correctly, and matches nothing.
    """
    declared = {kind for kind, _ in _BASE_PATTERNS}
    unreachable = declared - set(INPUT_KINDS)
    assert not unreachable, f"pattern kinds that can never run on input: {sorted(unreachable)}"


def test_url_is_the_only_kind_deliberately_absent_from_output() -> None:
    """An answer keeps its links; everything else redacted on the way in is
    redacted on the way out too. Stated here so a change to either set is a
    decision rather than a drift."""
    assert set(INPUT_KINDS) - set(OUTPUT_KINDS) == {"URL"}


# --- the web boundary uses the shared definition --------------------------


@pytest.mark.parametrize(
    "sample",
    [
        "13812345678",
        "sk-proj-abcdefghijklmnopqrst",
        "Bearer abcdefgh12345678",
        "https://intranet.corp/quarterly",
        "110101199003072316",
        "2001:db8::1",
    ],
)
def test_the_web_query_is_redacted_by_the_shared_patterns(sample: str) -> None:
    """These six all survived the hand-written pattern set this replaced.

    It never leaked -- `privacy_permission` had already redacted the question by
    the time the web retriever saw it -- but a second boundary that only appears
    to be guarded is worse than an unguarded one, because weakening the layer
    that does the work shows up here as nothing at all.
    """
    assert _sanitize_query(sample) != sample


def test_the_web_query_matches_the_shared_redactor_exactly() -> None:
    question = "对比 13812345678 和 110101199003072316 的记录，见 https://intranet.corp/x"
    assert _sanitize_query(question) == inspect_text(question, kinds=INPUT_KINDS).text


def test_an_ordinary_question_reaches_the_search_engine_intact() -> None:
    question = "什么是 reciprocal rank fusion，和 BM25 有什么区别"
    assert _sanitize_query(question) == question


# --- and nothing ordinary is swept up -------------------------------------


@pytest.mark.parametrize(
    "sample",
    [
        "QueryMind v0.6.2.1 released",
        "commit ae0cc56b8f2d4e1a9c3b5d7e0f1a2b3c4d5e6f70",
        "AUTHENTICATION_REQUIRED_ERROR",
        "请对比这两份报告的结论差异",
        "listening on 8000, size 1048576 bytes",
        "see [E1] and [E12] for details",
        "scores: 0.85 0.92 0.78",
    ],
)
def test_ordinary_text_is_left_alone(sample: str) -> None:
    assert not _kinds(sample), f"false positive on {sample!r}: {_kinds(sample)}"


# --- what an adversarial pass actually found ------------------------------
#
# The first false-positive check for this change was worthless: it reused inputs
# already known to pass, so it could only ever report zero. Rebuilt to stress the
# new patterns specifically, it found three defects in them, and every case below
# is one of those rather than something imagined.


@pytest.mark.parametrize("sample", ["见文档 E20260904", "版本 H20250101", "报告 G19991231"])
def test_a_date_coded_document_id_is_not_a_passport(sample: str) -> None:
    """`[EGDSPH]` plus eight digits is also how a dated document id is written."""
    assert not _kinds(sample), f"{sample!r} was redacted as {_kinds(sample)}"


@pytest.mark.parametrize(
    "sample",
    [
        "耗时 12:34:56",
        "网卡 a1:b2:c3:d4:e5:f6",
        'd = {"a":1, "b":2}',
        "key: value",
        "x[1:2:3]",
        "2026-09-04 12:34:56.789 INFO",
    ],
)
def test_colons_alone_are_not_an_ipv6_address(sample: str) -> None:
    assert "IP" not in _kinds(sample), f"{sample!r} was read as an address"


def test_an_eighteen_digit_number_is_not_a_company_registration() -> None:
    """The credit-code alphabet includes digits, so USCC_CN placed before
    BANK_CARD claimed every 18-digit order number as a company."""
    assert _kinds("订单 123456789012345678") == {"BANK_CARD": 1}


def test_a_credit_code_ending_in_a_checksum_letter_is_not_a_bank_card() -> None:
    """The mirror of the case above: `(?!\\d)` is satisfied by a letter, so the
    digits-only rule took the seventeen leading digits and left the `Q`."""
    assert _kinds("公司 91110108551385095Q") == {"USCC_CN": 1}
    assert _kinds("公司 91310000MA1FL0000X") == {"USCC_CN": 1}


def test_eleven_digits_are_only_a_mobile_number_with_a_real_prefix() -> None:
    assert _kinds("编号 10012345678") == {"PHONE": 1}
    assert _kinds("手机 13912345678") == {"MOBILE_CN": 1}
