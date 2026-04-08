from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from app.services import index_manager


def _dummy_settings(base_dir: Path):
    uploads = base_dir / "uploads"
    docs = base_dir / "docs"
    uploads.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(uploads_path=uploads, docs_path=docs)


def _make_tmp_dir(prefix: str) -> Path:
    path = Path("tests/.tmp") / f"{prefix}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_list_indexed_files_keeps_same_filename_as_separate_sources(monkeypatch):
    base_dir = _make_tmp_dir("index-manager-list")
    settings = _dummy_settings(base_dir)
    source_a = str(settings.docs_path / "readme.md")
    source_b = str(settings.uploads_path / "readme.md")
    Path(source_a).write_text("a", encoding="utf-8")
    Path(source_b).write_text("b", encoding="utf-8")

    records = [
        {"id": "1", "text": "doc-a", "metadata": {"source": source_a, "page": 1}},
        {"id": "2", "text": "doc-b", "metadata": {"source": source_b, "page": 2}},
    ]
    monkeypatch.setattr(index_manager, "read_corpus_records", lambda: records)
    monkeypatch.setattr(index_manager, "get_settings", lambda: settings)

    items = index_manager.list_indexed_files()

    readme_items = [x for x in items if x["filename"] == "readme.md"]
    assert len(readme_items) == 2
    assert sorted([x["source"] for x in readme_items]) == sorted([source_a, source_b])


def test_delete_file_index_requires_source_when_filename_is_ambiguous(monkeypatch):
    base_dir = _make_tmp_dir("index-manager-delete")
    settings = _dummy_settings(base_dir)
    source_a = str(settings.docs_path / "same.md")
    source_b = str(settings.uploads_path / "same.md")
    records = [
        {"id": "1", "text": "a", "metadata": {"source": source_a}},
        {"id": "2", "text": "b", "metadata": {"source": source_b}},
    ]

    monkeypatch.setattr(index_manager, "read_corpus_records", lambda: records)
    monkeypatch.setattr(index_manager, "get_settings", lambda: settings)
    monkeypatch.setattr(index_manager, "write_corpus_records", lambda _rows: None)
    monkeypatch.setattr(index_manager, "_delete_vector_documents", lambda _ids: None)
    monkeypatch.setattr(index_manager, "_delete_parent_records", lambda filename, source=None: 0)
    monkeypatch.setattr(index_manager, "_reset_bm25", lambda: None)
    monkeypatch.setattr(index_manager, "_delete_triplets_by_sources", lambda _sources: 0)

    with pytest.raises(ValueError):
        index_manager.delete_file_index("same.md")

    result = index_manager.delete_file_index("same.md", source=source_a)
    assert result["chunks_removed"] == 1
    assert result["vector_ids_removed"] == 1
