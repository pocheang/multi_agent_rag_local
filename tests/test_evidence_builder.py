"""Unit tests for evidence builder refactoring."""

import pytest

from app.agents.rag.evidence_builder import (
    EvidenceItemBuilder,
    bundle_from_bm25_records,
    bundle_from_legacy_payload,
    bundle_from_vector_matches,
)
from app.domain.contracts import EvidenceItem


def test_evidence_builder_from_legacy_citation():
    """Test building from legacy citation format."""
    builder = EvidenceItemBuilder("web")
    citation = {
        "content": "Test content",
        "source": "test.pdf",
        "document_id": "doc123",
        "metadata": {"page": 5, "score": 0.95},
    }

    item = builder.from_legacy_citation(citation)

    assert item is not None
    assert item.content == "Test content"
    assert item.source == "test.pdf"
    assert item.document_id == "doc123"
    assert item.page == 5
    assert item.retriever == "web"
    assert item.score == 0.95


def test_evidence_builder_from_vector_match():
    """Test building from vector retriever format."""
    builder = EvidenceItemBuilder("vector")

    class MockDocument:
        def __init__(self):
            self.page_content = "Vector content"
            self.metadata = {"source": "vec.pdf", "document_id": "vec123", "page": 3}

    match = (MockDocument(), 0.87)
    item = builder.from_vector_match(match)

    assert item is not None
    assert item.content == "Vector content"
    assert item.source == "vec.pdf"
    assert item.document_id == "vec123"
    assert item.page == 3
    assert item.retriever == "vector"
    assert item.score == 0.87


def test_evidence_builder_from_bm25_record():
    """Test building from BM25 retriever format."""
    builder = EvidenceItemBuilder("bm25")
    record = {
        "text": "BM25 content",
        "source": "bm25.pdf",
        "id": "bm25123",
        "metadata": {"page": 2},
        "bm25_score": 0.73,
    }

    item = builder.from_bm25_record(record)

    assert item is not None
    assert item.content == "BM25 content"
    assert item.source == "bm25.pdf"
    assert item.document_id == "bm25123"
    assert item.page == 2
    assert item.retriever == "bm25"
    assert item.score == 0.73


def test_evidence_builder_missing_required_fields():
    """Test that missing required fields return None."""
    builder = EvidenceItemBuilder("test")

    # Missing content
    assert builder.from_legacy_citation({"source": "test.pdf", "document_id": "123"}) is None

    # Missing source
    assert builder.from_legacy_citation({"content": "text", "document_id": "123"}) is None

    # Missing document_id (and no source fallback)
    assert builder.from_legacy_citation({"content": "text"}) is None


def test_evidence_builder_field_name_fallback():
    """Test that alternative field names work."""
    builder = EvidenceItemBuilder("test")

    # 'url' instead of 'source'
    citation = {"content": "text", "url": "test.pdf", "doc_id": "123"}
    item = builder.from_legacy_citation(citation)
    assert item is not None
    assert item.source == "test.pdf"

    # 'snippet' instead of 'content'
    citation = {"snippet": "text", "source": "test.pdf", "id": "123"}
    item = builder.from_legacy_citation(citation)
    assert item is not None
    assert item.content == "text"


def test_bundle_from_legacy_payload_citations():
    """Test bundle construction from citations."""
    payload = {
        "citations": [
            {"content": "text1", "source": "doc1.pdf", "document_id": "1", "metadata": {"score": 0.9}},
            {"content": "text2", "source": "doc2.pdf", "document_id": "2", "metadata": {"score": 0.8}},
        ]
    }

    bundle = bundle_from_legacy_payload(payload, "web")

    assert len(bundle.items) == 2
    assert bundle.items[0].content == "text1"
    assert bundle.items[1].content == "text2"


def test_bundle_from_legacy_payload_graph_fallback():
    """Test graph fallback when no citations."""
    payload = {
        "context": "Graph context text",
        "graph_signal_score": 0.85,
    }

    bundle = bundle_from_legacy_payload(payload, "graph", fallback_document_id="graph:query")

    assert len(bundle.items) == 1
    assert bundle.items[0].content == "Graph context text"
    assert bundle.items[0].source == "knowledge_graph"
    assert bundle.items[0].document_id == "graph:query"
    assert bundle.items[0].score == 0.85


def test_bundle_from_legacy_payload_error():
    """Test that error in payload raises exception."""
    from app.agents.rag.service import RetrieverSoftFailure

    payload = {"error": "Retrieval failed"}

    with pytest.raises(RetrieverSoftFailure, match="Retrieval failed"):
        bundle_from_legacy_payload(payload, "test")


def test_bundle_from_vector_matches():
    """Test bundle from vector matches."""
    class MockDoc:
        def __init__(self, content, source, doc_id):
            self.page_content = content
            self.metadata = {"source": source, "document_id": doc_id}

    matches = [
        (MockDoc("content1", "doc1.pdf", "1"), 0.9),
        (MockDoc("content2", "doc2.pdf", "2"), 0.8),
    ]

    bundle = bundle_from_vector_matches(matches)

    assert len(bundle.items) == 2
    assert all(item.retriever == "vector" for item in bundle.items)


def test_bundle_from_bm25_records():
    """Test bundle from BM25 records."""
    records = [
        {"text": "content1", "source": "doc1.pdf", "id": "1", "bm25_score": 0.7},
        {"text": "content2", "source": "doc2.pdf", "id": "2", "bm25_score": 0.6},
    ]

    bundle = bundle_from_bm25_records(records)

    assert len(bundle.items) == 2
    assert all(item.retriever == "bm25" for item in bundle.items)


def test_normalize_score_clamping():
    """Test that scores are clamped to [0.0, 1.0]."""
    builder = EvidenceItemBuilder("test")

    assert builder._normalize_score(1.5) == 1.0
    assert builder._normalize_score(-0.5) == 0.0
    assert builder._normalize_score(0.5) == 0.5
    assert builder._normalize_score(None) is None


def test_normalize_page_validation():
    """Test that page numbers are validated."""
    builder = EvidenceItemBuilder("test")

    assert builder._normalize_page(5) == 5
    assert builder._normalize_page(0) is None  # Page must be > 0
    assert builder._normalize_page(-1) is None
    assert builder._normalize_page("invalid") is None
    assert builder._normalize_page(None) is None
