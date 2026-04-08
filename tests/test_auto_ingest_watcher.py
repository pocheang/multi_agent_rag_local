from pathlib import Path
from types import SimpleNamespace
import uuid

from app.services.auto_ingest_watcher import AutoIngestWatcher


def _make_tmp_dir(prefix: str) -> Path:
    path = Path("tests/.tmp") / f"{prefix}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _dummy_settings(base: Path, enabled: bool = True):
    docs = base / "docs"
    uploads = base / "uploads"
    docs.mkdir(parents=True, exist_ok=True)
    uploads.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        docs_path=docs,
        uploads_path=uploads,
        auto_ingest_enabled=enabled,
        auto_ingest_interval_seconds=0.1,
        auto_ingest_watch_docs=True,
        auto_ingest_watch_uploads=False,
        auto_ingest_recursive=True,
    )


def test_auto_ingest_requires_stable_signature_before_ingest():
    base = _make_tmp_dir("auto-ingest-stable")
    settings = _dummy_settings(base)
    target = settings.docs_path / "a.md"
    target.write_text("hello", encoding="utf-8")

    ingested: list[list[Path]] = []

    def _ingest(paths, reset_vector_store=False):
        ingested.append(paths)
        return {"loaded_documents": 1, "chunks_indexed": 1, "triplets_written": 0}

    watcher = AutoIngestWatcher(settings=settings, ingest_fn=_ingest, delete_index_fn=lambda *args, **kwargs: {"ok": True})

    first = watcher.scan_once()
    second = watcher.scan_once()

    assert first["ready"] == 0
    assert second["ready"] == 1
    assert second["ingested"] == 1
    assert len(ingested) == 1
    assert ingested[0][0].name == "a.md"


def test_auto_ingest_reingests_after_file_change():
    base = _make_tmp_dir("auto-ingest-change")
    settings = _dummy_settings(base)
    target = settings.docs_path / "a.md"
    target.write_text("v1", encoding="utf-8")

    ingested: list[list[Path]] = []

    def _ingest(paths, reset_vector_store=False):
        ingested.append(paths)
        return {"loaded_documents": 1, "chunks_indexed": 1, "triplets_written": 0}

    watcher = AutoIngestWatcher(settings=settings, ingest_fn=_ingest, delete_index_fn=lambda *args, **kwargs: {"ok": True})

    watcher.scan_once()
    watcher.scan_once()

    target.write_text("v2", encoding="utf-8")
    watcher.scan_once()
    watcher.scan_once()

    assert len(ingested) == 2


def test_auto_ingest_disabled_no_work():
    base = _make_tmp_dir("auto-ingest-disabled")
    settings = _dummy_settings(base, enabled=False)
    target = settings.docs_path / "a.md"
    target.write_text("hello", encoding="utf-8")

    calls = {"ingest": 0}

    def _ingest(paths, reset_vector_store=False):
        calls["ingest"] += 1
        return {"loaded_documents": 1, "chunks_indexed": 1, "triplets_written": 0}

    watcher = AutoIngestWatcher(settings=settings, ingest_fn=_ingest, delete_index_fn=lambda *args, **kwargs: {"ok": True})
    result = watcher.scan_once()

    assert result == {"discovered": 0, "ready": 0, "ingested": 0}
    assert calls["ingest"] == 0
