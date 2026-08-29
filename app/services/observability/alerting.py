from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings, resolve_response_signing_secret

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_LAST_SENT: dict[str, float] = {}


def _rate_limit_ok(key: str) -> bool:
    """Shared per-key cooldown so repeated triggers don't spam a channel."""
    settings = get_settings()
    now = time.time()
    interval = max(1, int(getattr(settings, "alert_min_interval_seconds", 60) or 60))
    with _LOCK:
        last = float(_LAST_SENT.get(key, 0.0) or 0.0)
        if (now - last) < interval:
            return False
        _LAST_SENT[key] = now
        return True


def emit_alert(event_type: str, payload: dict[str, Any]) -> bool:
    settings = get_settings()
    if not bool(getattr(settings, "alerting_enabled", False)):
        return False
    url = str(getattr(settings, "alert_webhook_url", "") or "").strip()
    if not url:
        return False
    if not _is_webhook_allowed(url):
        return False
    if not _rate_limit_ok(f"webhook:{event_type}"):
        return False

    body = {
        "event_type": event_type,
        "created_at": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
        return True
    except (httpx.HTTPError, httpx.TimeoutException, httpx.RequestError) as e:
        # keep silent to avoid cascading failures
        logger.debug(f"Webhook notification failed: {e}")
        return False
    except Exception as e:
        # Catch unexpected errors to avoid cascading failures
        logger.warning(f"Unexpected error in webhook notification: {e}")
        return False


def send_slack_alert(event_type: str, text: str) -> bool:
    """POST a Slack-formatted message to ``settings.alert_slack_webhook_url``."""
    settings = get_settings()
    if not bool(getattr(settings, "alerting_enabled", False)):
        return False
    url = str(getattr(settings, "alert_slack_webhook_url", "") or "").strip()
    if not url:
        return False
    if not _is_webhook_allowed(url):
        return False
    if not _rate_limit_ok(f"slack:{event_type}"):
        return False

    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(url, json={"text": text})
            resp.raise_for_status()
        return True
    except (httpx.HTTPError, httpx.TimeoutException, httpx.RequestError) as e:
        logger.debug(f"Slack notification failed: {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error in Slack notification: {e}")
        return False


def send_email_alert(event_type: str, subject: str, body: str) -> bool:
    """Send a plaintext email via the configured SMTP server."""
    settings = get_settings()
    if not bool(getattr(settings, "alerting_enabled", False)):
        return False
    host = str(getattr(settings, "alert_email_smtp_host", "") or "").strip()
    from_addr = str(getattr(settings, "alert_email_from", "") or "").strip()
    to_addrs = [a.strip() for a in str(getattr(settings, "alert_email_to", "") or "").split(",") if a.strip()]
    if not host or not from_addr or not to_addrs:
        return False
    if not _rate_limit_ok(f"email:{event_type}"):
        return False

    try:
        import smtplib
        from email.message import EmailMessage

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = from_addr
        message["To"] = ", ".join(to_addrs)
        message.set_content(body)

        port = int(getattr(settings, "alert_email_smtp_port", 587) or 587)
        username = str(getattr(settings, "alert_email_smtp_username", "") or "")
        password = str(getattr(settings, "alert_email_smtp_password", "") or "")
        use_tls = bool(getattr(settings, "alert_email_use_tls", True))

        with smtplib.SMTP(host, port, timeout=5.0) as client:
            if use_tls:
                client.starttls()
            if username:
                client.login(username, password)
            client.send_message(message)
        return True
    except Exception as e:
        # keep silent to avoid cascading failures, matching emit_alert's contract
        logger.warning(f"Email notification failed: {e}")
        return False


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    import hashlib
    import hmac

    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def resolve_signing_secret() -> tuple[str | None, str | None]:
    return resolve_response_signing_secret(get_settings())


def _is_webhook_allowed(url: str) -> bool:
    settings = get_settings()
    allow = [
        x.strip().lower() for x in str(getattr(settings, "alert_webhook_allowlist", "") or "").split(",") if x.strip()
    ]
    if not allow:
        return True
    host = str(urlparse(url).hostname or "").strip().lower()
    if not host:
        return False
    for domain in allow:
        if host == domain or host.endswith(f".{domain}"):
            return True
    return False
