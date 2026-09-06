from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.models.catalog import provider_supports_embeddings


def is_under_path(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved_root = root.resolve()
    except (OSError, RuntimeError):
        return False
    return resolved == resolved_root or resolved_root in resolved.parents


def hash_secret(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def embedding_settings_signature(settings_data: dict[str, Any]) -> str:
    provider = str(settings_data.get("provider", "") or "").strip().lower()
    embedding_provider = provider
    embedding_model = str(settings_data.get("embedding_model", "") or "").strip()
    base_url = str(settings_data.get("base_url", "") or "").strip().rstrip("/")
    enabled = bool(settings_data.get("enabled", False))
    if provider and not provider_supports_embeddings(provider):
        embedding_provider = ""
        embedding_model = ""
        base_url = ""
    payload = {
        "enabled": enabled,
        "provider": embedding_provider,
        "base_url": base_url,
        "embedding_model": embedding_model,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
