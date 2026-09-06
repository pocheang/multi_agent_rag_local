"""A skipped chunk still occupies its position.

`split_documents_enhanced` was one function with three levels of nesting and a
cognitive complexity of 58 -- the highest in the project -- until 2026-09-06, when
it was split into `_split_document` / `_split_parent` / `_parent_id` /
`_neighbours`. The split was verified byte-for-byte against the old implementation
over a ten-document corpus, so these tests are not about that. They pin the two
properties that were hardest to see through the nesting and easiest to "tidy"
into a bug.

The first is that a blank chunk is *skipped but still counted*: `parent_index`,
`child_index` and the totals handed to `enhance_chunk_metadata` are positions in
the splitter's output, not in the kept subset. Renumbering them so they are
contiguous is the obvious-looking cleanup, and it silently changes what
"chunk 3 of 7" means to every consumer of that metadata.

The second is that `_neighbours` reads the *raw* neighbouring chunks while the
chunk being described is stripped. Those are different strings whenever a chunk
begins or ends on whitespace. Stripping both, for symmetry, would change the
context the metadata enhancer sees.
"""

from __future__ import annotations

import pytest

from app.ingestion.chunking import splitter as splitter_module
from app.ingestion.chunking.splitter import _neighbours, _parent_id, split_documents_enhanced


class Doc:
    """Stands in for a LangChain Document; the splitter reads only these two."""

    def __init__(self, page_content: str, metadata: dict | None = None):
        self.page_content = page_content
        self.metadata = metadata or {}


class _ScriptedSplitter:
    """Returns a fixed list, so a blank chunk can be put at a known position."""

    def __init__(self, pieces: list[str]):
        self._pieces = pieces

    def split_text(self, text: str) -> list[str]:  # noqa: ARG002 - the script is the point
        return list(self._pieces)


@pytest.fixture
def scripted(monkeypatch):
    """Drive both levels from one script, so indices are predictable."""

    def install(pieces: list[str]):
        monkeypatch.setattr(splitter_module, "_build_splitter", lambda **_: _ScriptedSplitter(pieces))

    return install


def test_a_blank_chunk_is_skipped_but_still_occupies_its_index(scripted):
    # Position 1 is blank. The chunks either side must keep indices 0 and 2, and
    # the total must stay 3 -- they describe the splitter's output, not the
    # survivors. Renumbering to 0 and 1 of 2 is the tempting, wrong cleanup.
    scripted(["first piece", "   ", "third piece"])
    children, parents = split_documents_enhanced(
        [Doc("anything", {"source": "/u/a/x.txt"})], enable_metadata_enhancement=False
    )

    assert [p["text"] for p in parents] == ["first piece", "third piece"]
    assert [p["metadata"]["parent_index"] for p in parents] == [0, 2]

    # Each surviving parent splits into the same three pieces, one of them blank.
    assert [c.metadata["child_index"] for c in children] == [0, 2, 0, 2]
    assert [c.page_content for c in children] == ["first piece", "third piece"] * 2


def test_every_child_carries_the_parent_it_came_from(scripted):
    scripted(["alpha", "beta"])
    children, parents = split_documents_enhanced(
        [Doc("anything", {"source": "/u/a/x.txt"})], enable_metadata_enhancement=False
    )

    parent_ids = [p["id"] for p in parents]
    assert len(parent_ids) == len(set(parent_ids)), "two parents shared an id"
    # Children are emitted parent by parent, each linked to the one it came from.
    assert [c.metadata["parent_id"] for c in children] == [parent_ids[0]] * 2 + [parent_ids[1]] * 2
    assert [c.metadata["parent_index"] for c in children] == [0, 0, 1, 1]


def test_the_totals_handed_to_the_enhancer_count_blanks_too(scripted, monkeypatch):
    seen: list[tuple[int, int, str | None, str | None]] = []

    def spy(text, metadata, index, total, previous, following):  # noqa: ARG001
        seen.append((index, total, previous, following))
        return metadata

    monkeypatch.setattr(splitter_module, "enhance_chunk_metadata", spy)
    scripted(["one ", "  ", " three"])
    split_documents_enhanced([Doc("anything", {"source": "/u/a/x.txt"})], enable_metadata_enhancement=True)

    # Two parents survive; each is described as position 0 and position 2 of 3.
    assert [(i, t) for i, t, _, _ in seen[:1]] == [(0, 3)]
    # Neighbours come from the raw list -- "one " keeps its trailing space and the
    # blank neighbour is passed through as it was, not as None.
    assert seen[0][2] is None
    assert seen[0][3] == "  "


def test_a_document_with_an_identity_gets_the_same_parent_id_every_time():
    # Re-ingesting an unchanged document must not create a second parent, so the
    # id is a hash of identity + position + text rather than a uuid.
    args = ("doc-1|v3", 0, 0, "the parent text")
    assert _parent_id(*args) == _parent_id(*args)
    assert _parent_id(*args).startswith("parent-")

    # Change any input and the id changes.
    assert _parent_id("doc-1|v4", 0, 0, "the parent text") != _parent_id(*args)
    assert _parent_id("doc-1|v3", 0, 1, "the parent text") != _parent_id(*args)
    assert _parent_id("doc-1|v3", 0, 0, "different text") != _parent_id(*args)

    # With no identity there is nothing to be stable against, and it says so.
    first = _parent_id("", 0, 0, "the parent text")
    assert first != _parent_id("", 0, 0, "the parent text")
    assert first.startswith("parent-0-0-")


def test_neighbours_are_none_at_the_edges_and_raw_in_the_middle():
    texts = [" a ", "b", " c "]
    assert _neighbours(texts, 0) == (None, "b")
    assert _neighbours(texts, 1) == (" a ", " c ")
    assert _neighbours(texts, 2) == ("b", None)
    assert _neighbours(["only"], 0) == (None, None)


def test_an_empty_document_produces_nothing_rather_than_an_empty_chunk():
    children, parents = split_documents_enhanced(
        [Doc(""), Doc("   \n\t "), Doc("real content", {"source": "/u/a/x.txt"})],
        enable_metadata_enhancement=False,
    )
    assert parents and all(p["text"].strip() for p in parents)
    assert children and all(c.page_content.strip() for c in children)
