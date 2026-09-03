"""When two pieces of evidence are the same piece of evidence.

Deduplication decides what the synthesizer sees, and it had no test. The rule is
in two halves: anything carrying an artifact identifier is identified by that,
and anything that does not falls back to its own canonicalized text -- so the
same passage retrieved twice by two retrievers collapses to one item that
records both.

The key is `(kind, payload)` and the two kinds never collide, which matters more
than it looks: a content key and a provenance key are computed from different
things, so nothing but the kind stops them meeting in the same dictionary.
"""

from __future__ import annotations

from app.domain.contracts import EvidenceItem
from app.knowledge.deduplication import deduplicate_evidence, evidence_dedup_key


def _item(**overrides) -> EvidenceItem:
    fields = {
        "content": "the quarterly result",
        "source": "report.pdf",
        "document_id": "doc-1",
        "retriever": "vector",
    }
    fields.update(overrides)
    return EvidenceItem(**fields)


def test_an_artifact_identifier_is_what_identifies_the_item() -> None:
    """Two retrievals of one chunk are one chunk, whatever their text looks like."""

    first = _item(chunk_id="c-1", content="the quarterly result")
    second = _item(chunk_id="c-1", content="THE   quarterly   result", retriever="bm25")

    assert evidence_dedup_key(first) == evidence_dedup_key(second)


def test_different_chunks_of_one_document_stay_separate() -> None:
    assert evidence_dedup_key(_item(chunk_id="c-1")) != evidence_dedup_key(_item(chunk_id="c-2"))


def test_a_version_is_part_of_the_identity() -> None:
    assert evidence_dedup_key(_item(chunk_id="c-1", version=1)) != evidence_dedup_key(_item(chunk_id="c-1", version=2))


def test_without_an_identifier_the_text_decides_and_ignores_case_and_spacing() -> None:
    first = _item(content="Total revenue  grew")
    second = _item(content="total   revenue grew\n")

    assert evidence_dedup_key(first) == evidence_dedup_key(second)


def test_the_same_text_from_two_sources_is_two_pieces_of_evidence() -> None:
    assert evidence_dedup_key(_item(source="a.pdf")) != evidence_dedup_key(_item(source="b.pdf"))


def test_the_two_kinds_of_key_are_shaped_alike_and_cannot_collide() -> None:
    """Both are `(kind, payload)`, and the kind is what keeps them apart."""

    provenance = evidence_dedup_key(_item(chunk_id="c-1"))
    content = evidence_dedup_key(_item())

    assert len(provenance) == len(content) == 2
    assert provenance[0] != content[0]
    assert provenance != content


def test_the_higher_scoring_copy_wins_and_both_retrievers_are_recorded() -> None:
    items = [
        _item(chunk_id="c-1", score=0.4, retriever="vector"),
        _item(chunk_id="c-1", score=0.9, retriever="bm25"),
    ]

    (survivor,) = deduplicate_evidence(items)

    assert survivor.score == 0.9
    assert survivor.retriever == "bm25+vector"  # sorted, so the label is stable


def test_results_come_back_best_first_and_an_unscored_item_sorts_last() -> None:
    items = [_item(chunk_id="c-1", score=0.5), _item(chunk_id="c-2"), _item(chunk_id="c-3", score=0.8)]

    scores = [item.score for item in deduplicate_evidence(items)]

    assert scores == [0.8, 0.5, None]


def test_a_retriever_label_that_is_already_compound_is_split_and_merged() -> None:
    items = [_item(chunk_id="c-1", retriever="vector+graph"), _item(chunk_id="c-1", retriever="bm25")]

    (survivor,) = deduplicate_evidence(items)

    assert survivor.retriever == "bm25+graph+vector"
