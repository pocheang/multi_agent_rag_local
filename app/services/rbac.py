from typing import Any


_ROLE_ACTIONS: dict[str, set[str]] = {
    "admin": {
        "*",
    },
    "analyst": {
        "query:run",
        "session:manage",
        "message:manage",
        "prompt:manage",
        "document:read",
        "document:manage_own",
        "upload:create",
    },
    "viewer": {
        "query:run",
        "session:manage",
        "message:manage",
        "prompt:manage",
        "document:read",
        "document:manage_own",
        "upload:create",
    },
}


def can(action: str, user: dict[str, Any]) -> bool:
    role = str(user.get("role", "viewer")).lower()
    if role not in _ROLE_ACTIONS:
        return False
    allowed = _ROLE_ACTIONS[role]
    return "*" in allowed or action in allowed
