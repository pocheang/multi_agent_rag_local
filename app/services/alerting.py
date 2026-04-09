from __future__ import annotations

from datetime import datetime, timezone
import json
import threading
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

_LOCK = threading.Lock()
_LAST_SENT: dict[str, float] = {}


def emit_alert(event_type: str, payload: dict[str, Any]) -> bool:
    settings = get_settings()
    if not bool(getattr(settings, "alerting_enabled", False)):
        return False
    url = str(getattr(settings, "alert_webhook_url", "") or "").strip()
    if not url:
        return False
    if not _is_webhook_allowed(url):
        return False

    now = time.time()
    interval = max(1, int(getattr(settings, "alert_min_interval_seconds", 60) or 60))
    with _LOCK:
        last = float(_LAST_SENT.get(event_type, 0.0) or 0.0)
        if (now - last) < interval:
            return False

    body = {
        "event_type": event_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
        with _LOCK:
            _LAST_SENT[event_type] = now
        return True
    except Exception:
        # keep silent to avoid cascading failures
        return False


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    import hashlib
    import hmac

    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def resolve_signing_secret() -> tuple[str | None, str | None]:
    settings = get_settings()
    active_kid = str(getattr(settings, "response_signing_active_kid", "v1") or "v1").strip() or "v1"
    raw_keys = str(getattr(settings, "response_signing_keys", "") or "").strip()
    if raw_keys:
        pairs = [x.strip() for x in raw_keys.split(";") if x.strip()]
        mapping: dict[str, str] = {}
        for p in pairs:
            if ":" not in p:
                continue
            kid, secret = p.split(":", 1)
            k = kid.strip()
            s = secret.strip()
            if k and s:
                mapping[k] = s
        if active_kid in mapping:
            return active_kid, mapping[active_kid]
    legacy_secret = str(getattr(settings, "response_signing_secret", "") or "").strip()
    if legacy_secret:
        return active_kid, legacy_secret
    return None, None


def _is_webhook_allowed(url: str) -> bool:
    settings = get_settings()
    allow = [x.strip().lower() for x in str(getattr(settings, "alert_webhook_allowlist", "") or "").split(",") if x.strip()]
    if not allow:
        return True
    host = str(urlparse(url).hostname or "").strip().lower()
    if not host:
        return False
    for domain in allow:
        if host == domain or host.endswith(f".{domain}"):
            return True
    return False
