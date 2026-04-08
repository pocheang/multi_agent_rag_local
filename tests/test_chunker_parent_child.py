from types import SimpleNamespace

from app.ingestion import chunker


class _Doc:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


def test_split_documents_returns_child_chunks_and_parent_records(monkeypatch):
    monkeypatch.setattr(
        chunker,
        "get_settings",
        lambda: SimpleNamespace(
            parent_chunk_size=120,
            parent_chunk_overlap=20,
            child_chunk_size=60,
            child_chunk_overlap=10,
        ),
    )
    text = ("这是第一段。这里有一些信息。\n\n这是第二段。这里有更多信息。 " * 10).strip()
    docs = [_Doc(page_content=text, metadata={"source": "demo.md"})]

    children, parents = chunker.split_documents(docs)

    assert children
    assert parents
    parent_ids = {p["id"] for p in parents}
    for child in children:
        assert child.metadata.get("parent_id") in parent_ids
        assert child.metadata.get("source") == "demo.md"
