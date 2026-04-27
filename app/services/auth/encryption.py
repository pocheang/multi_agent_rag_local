import base64
import hashlib
import hmac
import secrets
from typing import Any

API_KEY_ENC_PREFIX = "enc:v1:"


def stream_xor(data: bytes, key: bytes, nonce: bytes) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(data, out[: len(data)]))


def encrypt_secret_text(plaintext: str, key: bytes) -> str:
    if not plaintext:
        return ""
    nonce = secrets.token_bytes(16)
    cipher = stream_xor(plaintext.encode("utf-8"), key, nonce)
    tag = hmac.new(key, nonce + cipher, hashlib.sha256).digest()[:16]
    token = base64.urlsafe_b64encode(nonce + tag + cipher).decode("ascii")
    return f"{API_KEY_ENC_PREFIX}{token}"


def decrypt_secret_text(value: str, key: bytes) -> str:
    text = str(value or "")
    if not text:
        return ""
    if not text.startswith(API_KEY_ENC_PREFIX):
        return text
    raw = text[len(API_KEY_ENC_PREFIX) :]
    decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
    if len(decoded) < 32:
        raise ValueError("invalid encrypted payload")
    nonce = decoded[:16]
    tag = decoded[16:32]
    cipher = decoded[32:]
    expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected):
        raise ValueError("encrypted payload integrity check failed")
    plain = stream_xor(cipher, key, nonce)
    return plain.decode("utf-8")


def encrypt_api_settings_payload(payload: dict[str, Any], key: bytes) -> dict[str, Any]:
    out = dict(payload)
    api_key = str(out.get("api_key", "") or "").strip()
    if not api_key:
        out["api_key"] = ""
        return out
    if api_key.startswith(API_KEY_ENC_PREFIX):
        return out
    out["api_key"] = encrypt_secret_text(api_key, key)
    return out


def decrypt_api_settings_payload(payload: dict[str, Any], key: bytes) -> dict[str, Any]:
    out = dict(payload)
    raw_key = str(out.get("api_key", "") or "")
    if not raw_key:
        out["api_key"] = ""
        return out
    try:
        out["api_key"] = decrypt_secret_text(raw_key, key)
    except Exception:
        out["api_key"] = ""
    return out
