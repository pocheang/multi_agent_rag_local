from typing import Any

_ROLE_ACTIONS: dict[str, set[str]] = {
    "admin": {
        "*",  # Admin has all permissions
    },
    "analyst": {
        # Analysts can create and manage content
        "query:run",
        "session:read",
        "session:create",
        "session:delete",
        "session:manage",  # Backward compatibility
        "session:lock_strategy",
        "message:read",
        "message:edit",
        "message:delete",
        "message:manage",  # Backward compatibility
        "prompt:read",
        "prompt:create",
        "prompt:edit",
        "prompt:delete",
        "prompt:manage",  # Backward compatibility
        "document:read",
        "document:manage_own",
        "document:delete_own",
        "document:reindex_own",
        "upload:create",
    },
    "viewer": {
        # Viewers can work with their own lightweight content and settings.
        "query:run",
        "session:read",
        "session:create",
        "message:read",
        "prompt:read",
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





