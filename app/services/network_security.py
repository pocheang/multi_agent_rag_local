from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import get_settings

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class OutboundURLValidationError(ValueError):
    """Raised when user-provided outbound base_url is unsafe."""


def _csv_hosts(raw: str) -> list[str]:
    return [x.strip().lower() for x in str(raw or "").split(",") if x.strip()]


def _host_allowlisted(host: str, allowlist: list[str]) -> bool:
    host_lc = str(host or "").strip().lower()
    if not host_lc or not allowlist:
        return False
    for item in allowlist:
        if host_lc == item or host_lc.endswith(f".{item}"):
            return True
    return False


def _parse_ip_literal(host: str) -> IPAddress | None:
    text = str(host or "").strip()
    if not text:
        return None
    # Strip IPv6 zone id if present (e.g. fe80::1%lo0).
    text = text.split("%", 1)[0]
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def _is_blocked_ip(addr: IPAddress) -> bool:
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _resolve_host_ips(host: str, port: int, *, enabled: bool) -> list[IPAddress]:
    if not enabled:
        return []
    try:
        rows = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return []
    resolved: list[ipaddress._BaseAddress] = []
    for row in rows:
        sockaddr = row[4]
        if not sockaddr:
            continue
        ip_text = str(sockaddr[0] or "").strip()
        if not ip_text:
            continue
        parsed = _parse_ip_literal(ip_text)
        if parsed is not None:
            resolved.append(parsed)
    return resolved


def validate_api_base_url_for_provider(base_url: str, *, provider: str) -> str:
    settings = get_settings()
    normalized = str(base_url or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    scheme = str(parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise OutboundURLValidationError("base_url must use http or https")
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        raise OutboundURLValidationError("base_url host is required")

    allowlist = _csv_hosts(str(getattr(settings, "api_base_url_allowlist", "") or ""))
    if _host_allowlisted(host, allowlist):
        return normalized

    provider_lc = str(provider or "").strip().lower()
    allow_private = bool(getattr(settings, "api_base_url_allow_private", False))
    if provider_lc == "ollama":
        # Local Ollama deployment is an explicit in-host use case.
        allow_private = True
    if allow_private:
        return normalized

    if host in {"localhost", "localhost.localdomain"}:
        raise OutboundURLValidationError("base_url host is blocked by network boundary policy")

    literal_ip = _parse_ip_literal(host)
    if literal_ip is not None and _is_blocked_ip(literal_ip):
        raise OutboundURLValidationError("base_url resolves to blocked private/loopback/link-local address")

    port = int(parsed.port or (443 if scheme == "https" else 80))
    dns_check = bool(getattr(settings, "api_base_url_dns_check", True))
    resolved_ips = _resolve_host_ips(host, port, enabled=dns_check)
    if resolved_ips and all(_is_blocked_ip(x) for x in resolved_ips):
        raise OutboundURLValidationError("base_url DNS resolution includes only blocked private/loopback/link-local addresses")

    return normalized
