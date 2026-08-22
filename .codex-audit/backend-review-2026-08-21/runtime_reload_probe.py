import os
import tempfile
import gc
from pathlib import Path


with tempfile.TemporaryDirectory(prefix="querymind-runtime-") as raw:
    root = Path(raw)
    os.environ.update(
        {
            "APP_ENV": "development",
            "APP_DB_PATH": str(root / "app.db"),
            "DATABASE_URL": f"sqlite:///{root / 'querymind.db'}",
            "SESSIONS_DIR": str(root / "sessions"),
            "UPLOADS_DIR": str(root / "uploads"),
            "DATA_DIR": str(root / "docs"),
            "CHROMA_PERSIST_DIR": str(root / "chroma"),
            "CORPUS_STORE_PATH": str(root / "chunks" / "chunks.jsonl"),
            "PARENT_STORE_PATH": str(root / "chunks" / "parents.jsonl"),
            "USERS_FILE": str(root / "security" / "users.json"),
            "AUTH_SESSIONS_FILE": str(root / "security" / "auth_sessions.json"),
            "HISTORY_SQLITE_PATH": str(root / "history.db"),
            "HISTORY_COLD_DIR": str(root / "sessions_cold"),
            "AUTO_INGEST_ENABLED": "false",
            "SHADOW_QUEUE_WORKERS": "1",
        }
    )

    from app.api import dependencies
    from app.core.config import Settings

    old = dependencies.get_query_runtime()
    old_ids = {
        id(old),
        id(old.query_guard),
        id(old.query_result_cache),
        id(old.quota_guard),
        id(old.shadow_queue),
    }
    new = dependencies.reload_query_runtime(Settings())
    try:
        new_ids = {
            id(new),
            id(new.query_guard),
            id(new.query_result_cache),
            id(new.quota_guard),
            id(new.shadow_queue),
        }
        assert dependencies.get_query_runtime() is new
        assert old_ids.isdisjoint(new_ids)
        assert new.shadow_queue.stats()["workers"] == 1
        assert dependencies.query_guard is new.query_guard
        assert dependencies.query_result_cache is new.query_result_cache
        print("runtime_reload=ok")
        print("new_workers=1")
    finally:
        dependencies.get_query_runtime().shadow_queue.stop(timeout=2.0)
        gc.collect()
