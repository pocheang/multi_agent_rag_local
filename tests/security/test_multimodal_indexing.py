"""Images become retrievable evidence, and only to the person who uploaded them.

The `multimodal` knowledge source has always been selectable -- any question
mentioning a diagram or a chart picks it -- and it always returned nothing,
because nothing ever wrote the collection it reads. Ingestion writes it now.

Which makes the owner metadata the point of this file rather than a detail. An
image is indexed into its own Chroma collection, outside the corpus the store's
`similarity_search` guards, so the two checks that keep one tenant out of
another's documents have to be reproduced here deliberately: the query is scoped
by tenant and by source or document, *and* by the owner metadata written at index
time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from app.domain.knowledge import AccessScope
from app.retrievers.multimodal_retriever import _scope_filter
from app.services.documents import ingest as ingest_module


@dataclass
class _Image:
    image_id: str
    page: int = 1
    filename: str = "figure-1.png"
    data: bytes = b"not-really-an-image"
    ocr_text: str = ""
    description: str = ""


@dataclass
class _Parsed:
    images: tuple[_Image, ...] = ()


@dataclass
class _Indexed:
    calls: list[Any] = field(default_factory=list)


@pytest.fixture
def indexer(monkeypatch: pytest.MonkeyPatch) -> _Indexed:
    """Capture what would be written, without standing up a vector store."""

    recorded = _Indexed()

    class _FakeProcessor:
        def index_image(self, image, collection_name: str = "image_descriptions") -> None:
            recorded.calls.append(image)

    monkeypatch.setattr("app.services.multimodal.image_processor.ImageProcessor", _FakeProcessor)
    return recorded


CANONICAL = {
    "source": "/uploads/alice/report.pdf",
    "document_id": "doc-1",
    "tenant_id": "acme",
    "owner_user_id": "alice",
    "visibility": "private",
    "version": 2,
}


def test_an_image_that_was_read_is_indexed_with_its_owner(indexer: _Indexed) -> None:
    parsed = _Parsed(images=(_Image("img-1", description="an architecture diagram of the ingest path"),))

    count = ingest_module._index_images(parsed, {"img-1": "artifact://img-1"}, CANONICAL)

    assert count == 1
    (written,) = indexer.calls
    assert written.owner_user_id == "alice"
    assert written.visibility == "private"
    assert written.tenant_id == "acme"
    assert written.artifact_uri == "artifact://img-1"
    assert "architecture diagram" in written.description


def test_ocr_text_is_used_when_the_loader_gave_no_description(indexer: _Indexed) -> None:
    parsed = _Parsed(images=(_Image("img-1", ocr_text="Q3 revenue by region"),))

    assert ingest_module._index_images(parsed, {}, CANONICAL) == 1
    assert "Q3 revenue by region" in indexer.calls[0].description


def test_an_image_nobody_could_read_is_not_indexed(indexer: _Indexed, monkeypatch: pytest.MonkeyPatch) -> None:
    """Indexing the reason -- "Tesseract executable not found" -- would make the
    diagnostic itself retrievable, which is worse than the image being absent."""

    class _Doc:
        page_content = "[image_meta] format=png\n[image_ocr_error]\nTesseract executable not found"

    monkeypatch.setattr("app.ingestion.extraction.ocr.ocr_image_bytes", lambda *a, **k: [_Doc()])

    assert ingest_module._index_images(_Parsed(images=(_Image("img-1"),)), {}, CANONICAL) == 0
    assert indexer.calls == []


def test_ocr_runs_for_an_image_the_loader_left_bare(indexer: _Indexed, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Path] = []

    class _Doc:
        page_content = "[image_meta] format=png; size=800x600.\nDeployment topology, three services"

    def fake_ocr(data: bytes, source: Path, page: int | None = None, **_kwargs):
        seen.append(source)
        return [_Doc()]

    monkeypatch.setattr("app.ingestion.extraction.ocr.ocr_image_bytes", fake_ocr)

    assert ingest_module._index_images(_Parsed(images=(_Image("img-1"),)), {}, CANONICAL) == 1
    assert seen == [Path("/uploads/alice/report.pdf")]
    assert "Deployment topology" in indexer.calls[0].description


def test_a_document_with_no_images_writes_nothing(indexer: _Indexed) -> None:
    assert ingest_module._index_images(_Parsed(), {}, CANONICAL) == 0
    assert indexer.calls == []


def test_an_indexing_failure_costs_that_image_and_not_the_ingest(
    indexer: _Indexed, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Refusing:
        def index_image(self, image, collection_name: str = "image_descriptions") -> None:
            raise RuntimeError("collection is locked")

    monkeypatch.setattr("app.services.multimodal.image_processor.ImageProcessor", _Refusing)

    assert ingest_module._index_images(_Parsed(images=(_Image("img-1", description="a chart"),)), {}, CANONICAL) == 0


def _scope(**overrides) -> AccessScope:
    fields = {
        "tenant_id": "acme",
        "user_id": "alice",
        "role": "viewer",
        "permissions": frozenset(),
        "document_ids": frozenset(),
        "allowed_sources": frozenset({"/uploads/alice/report.pdf"}),
        "acl_tags": frozenset(),
        "allowed_fields": frozenset({"content", "source"}),
    }
    fields.update(overrides)
    return AccessScope(**fields)


def test_the_image_query_is_scoped_by_owner_as_well_as_by_source() -> None:
    """The same two independent checks `similarity_search` applies to the corpus."""

    where = _scope_filter(_scope())

    assert where is not None
    clauses = where["$and"]
    assert {"tenant_id": "acme"} in clauses
    assert any("source" in clause for clause in clauses)
    owner = [clause for clause in clauses if "$or" in clause]
    assert owner, f"no owner clause in {clauses}"
    assert {"owner_user_id": {"$eq": "alice"}} in owner[0]["$or"]


def test_a_tenant_identity_alone_searches_nothing() -> None:
    """Fail closed: knowing which tenant someone is in is not document access."""

    assert _scope_filter(_scope(allowed_sources=frozenset(), document_ids=frozenset())) is None


def test_the_text_modality_is_gone() -> None:
    """It queried a collection nothing creates, and text is the vector source's job."""

    import inspect

    from app.retrievers.multimodal_retriever import MultiModalRetriever

    assert not hasattr(MultiModalRetriever, "_retrieve_text")
    # The name survives in the comment explaining its absence; the query does not.
    source = inspect.getsource(MultiModalRetriever)
    assert 'get_collection(name="text_chunks")' not in source


@dataclass
class _Table:
    table_id: str = "tbl-1"
    page: int = 3
    markdown: str = "| Region | Q3 |\n| --- | --- |\n| APAC | 120 |\n| EMEA | 98 |"
    sheet: str | None = "Revenue"


@dataclass
class _ParsedWithTables:
    tables: tuple[_Table, ...] = ()
    images: tuple[_Image, ...] = ()


@pytest.fixture
def table_indexer(monkeypatch: pytest.MonkeyPatch) -> _Indexed:
    recorded = _Indexed()

    class _FakeExtractor:
        def index_table(self, table, collection_name: str = "table_summaries") -> None:
            recorded.calls.append(table)

    monkeypatch.setattr("app.services.multimodal.table_extractor.TableExtractor", _FakeExtractor)
    return recorded


def test_a_table_is_indexed_whole_with_its_header_and_its_owner(table_indexer: _Indexed) -> None:
    """The header is the part a size-split fragment loses."""

    count = ingest_module._index_tables(_ParsedWithTables(tables=(_Table(),)), CANONICAL)

    assert count == 1
    (written,) = table_indexer.calls
    assert written.headers == ["Region", "Q3"]
    assert written.rows == [["APAC", "120"], ["EMEA", "98"]]
    assert written.metadata["owner_user_id"] == "alice"
    assert written.metadata["visibility"] == "private"
    assert written.metadata["num_cols"] == 2


def test_a_table_that_parsed_to_nothing_is_not_indexed(table_indexer: _Indexed) -> None:
    assert ingest_module._index_tables(_ParsedWithTables(tables=(_Table(markdown="(no table)"),)), CANONICAL) == 0
    assert table_indexer.calls == []


def test_a_document_with_no_tables_writes_nothing(table_indexer: _Indexed) -> None:
    assert ingest_module._index_tables(_ParsedWithTables(), CANONICAL) == 0


def test_an_escaped_pipe_stays_inside_its_cell() -> None:
    headers, rows = ingest_module._table_from_markdown("| a \\| b | c |\n| --- | --- |\n| 1 | 2 |")

    assert headers == ["a | b", "c"]
    assert rows == [["1", "2"]]


def test_a_question_about_a_table_reaches_the_source_that_holds_whole_tables() -> None:
    """Indexing tables as units buys nothing if nothing selects the source."""

    from app.agents.knowledge.service import _VISUAL_QUERY_PATTERN, _matches

    for question in ("这个表格里第三行是什么", "what does the table say about revenue"):
        assert _matches(question.lower(), _VISUAL_QUERY_PATTERN), question
    assert not _matches("what was the total revenue", _VISUAL_QUERY_PATTERN)


@pytest.mark.parametrize(
    ("module", "call"),
    [
        ("app.services.multimodal.image_processor", "images"),
        ("app.services.multimodal.table_extractor", "tables"),
    ],
)
def test_indexing_degrades_when_the_optional_extra_is_absent(
    monkeypatch: pytest.MonkeyPatch, module: str, call: str
) -> None:
    """`multimodal` is an optional extra; ingesting a document is not optional.

    This is the third time a module-scope import of an optional package has
    reached a required path -- PyMuPDF twice, then pandas, which CI caught and
    this machine could not because it has all of them installed. Wrapping the
    import is the guard that does not need updating when the next one appears.
    """

    import sys

    # An entry of None makes `import module` raise, which is what a missing
    # dependency looks like from the caller's side.
    monkeypatch.setitem(sys.modules, module, None)

    if call == "images":
        assert (
            ingest_module._index_images(_Parsed(images=(_Image("img-1", description="a chart"),)), {}, CANONICAL) == 0
        )
    else:
        assert ingest_module._index_tables(_ParsedWithTables(tables=(_Table(),)), CANONICAL) == 0
