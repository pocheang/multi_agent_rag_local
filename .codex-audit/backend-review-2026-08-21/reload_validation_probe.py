import os
import tempfile
from pathlib import Path


with tempfile.TemporaryDirectory(prefix="querymind-config-") as raw:
    root = Path(raw)
    os.environ.update(
        {
            "APP_ENV": "development",
            "APP_DB_PATH": str(root / "app.db"),
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
            "RESPONSE_SIGNING_ENABLED": "true",
            "RESPONSE_SIGNING_KEYS": "",
            "RESPONSE_SIGNING_SECRET": "",
        }
    )

    from app.core.config import get_settings, reload_settings

    get_settings.cache_clear()
    old_settings = get_settings()
    os.environ["APP_ENV"] = "production"
    try:
        reload_settings()
    except RuntimeError as exc:
        assert str(exc) == "response signing is enabled but no active signing key is configured"
    else:
        raise AssertionError("invalid production settings unexpectedly replaced the cache")
    assert get_settings() is old_settings
    print("failed_reload_preserved_settings=ok")
