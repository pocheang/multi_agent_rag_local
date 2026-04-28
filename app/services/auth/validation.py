def validate_username(username: str) -> str:
    value = (username or "").strip()
    if len(value) < 3 or len(value) > 32:
        raise ValueError("username length must be 3-32")
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if any(ch not in allowed for ch in value):
        raise ValueError("username contains unsupported characters")
    return value


def validate_password(password: str) -> str:
    value = password or ""
    if len(value) < 12:
        raise ValueError("password must be at least 12 characters")
    if len(value) > 128:
        raise ValueError("password must not exceed 128 characters")
    if not any(ch.islower() for ch in value):
        raise ValueError("password must include lowercase letters")
    if not any(ch.isupper() for ch in value):
        raise ValueError("password must include uppercase letters")
    if not any(ch.isdigit() for ch in value):
        raise ValueError("password must include digits")
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(ch in special_chars for ch in value):
        raise ValueError("password must include special characters")
    return value


def validate_role(role: str) -> str:
    value = (role or "").strip().lower()
    if value not in {"admin", "analyst", "viewer"}:
        raise ValueError("unsupported role")
    return value


def validate_status(status: str) -> str:
    value = (status or "").strip().lower()
    if value not in {"active", "disabled"}:
        raise ValueError("unsupported status")
    return value


def normalize_classification_value(value: str | None, max_len: int = 64) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > max_len:
        raise ValueError(f"classification field too long (max {max_len})")
    return text
