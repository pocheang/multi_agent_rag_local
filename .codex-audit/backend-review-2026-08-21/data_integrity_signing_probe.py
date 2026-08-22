import gc
import sqlite3
import tempfile
from pathlib import Path

from app.core.config import Settings, resolve_response_signing_secret, validate_security_settings
from app.services.prompts.store import PromptStore


with tempfile.TemporaryDirectory(prefix="querymind-data-") as raw:
    db_path = Path(raw) / "prompts.db"
    store = PromptStore(db_path=db_path)
    created = store.create_prompt("user-1", "title", "content")
    prompt_id = str(created["prompt_id"])
    assert store.update_prompt("user-1", prompt_id, "title-2", "content-2") is not None
    assert len(store.list_versions("user-1", prompt_id)) == 2
    assert store.delete_prompt("user-1", prompt_id) is True
    assert store.delete_prompt("user-1", prompt_id) is False

    conn = sqlite3.connect(db_path)
    try:
        templates = conn.execute(
            "SELECT COUNT(*) FROM prompt_templates WHERE user_id=? AND prompt_id=?",
            ("user-1", prompt_id),
        ).fetchone()[0]
        versions = conn.execute(
            "SELECT COUNT(*) FROM prompt_template_versions WHERE user_id=? AND prompt_id=?",
            ("user-1", prompt_id),
        ).fetchone()[0]
    finally:
        conn.close()
    assert templates == 0
    assert versions == 0

    dev = Settings(
        APP_ENV="development",
        RESPONSE_SIGNING_ENABLED=True,
        RESPONSE_SIGNING_KEYS="",
        RESPONSE_SIGNING_SECRET="",
    )
    validate_security_settings(dev)

    prod = Settings(
        APP_ENV="production",
        RESPONSE_SIGNING_ENABLED=True,
        RESPONSE_SIGNING_KEYS="",
        RESPONSE_SIGNING_SECRET="",
    )
    try:
        validate_security_settings(prod)
    except RuntimeError as exc:
        assert str(exc) == "response signing is enabled but no active signing key is configured"
    else:
        raise AssertionError("production signing validation did not fail closed")

    signed = Settings(
        APP_ENV="production",
        RESPONSE_SIGNING_ENABLED=True,
        RESPONSE_SIGNING_ACTIVE_KID="v2",
        RESPONSE_SIGNING_KEYS="v1:old-secret;v2:active-secret",
    )
    validate_security_settings(signed)
    assert resolve_response_signing_secret(signed) == ("v2", "active-secret")

    print("prompt_templates=0")
    print("prompt_versions=0")
    print("signing_validation=ok")
    del store
    gc.collect()
