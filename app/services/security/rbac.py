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
        # Viewers can manage their own content (sessions, messages, prompts, documents)
        "query:run",
        "session:read",
        "session:create",
        "session:delete",           # Added: can delete own sessions
        "session:update",           # Added: can update own sessions (rename, pin)
        "session:lock_strategy",    # Added: can lock strategy
        "message:read",
        "message:edit",             # Added: can edit own messages
        "message:delete",           # Added: can delete own messages
        "prompt:read",
        "prompt:create",            # Added: can create prompts
        "prompt:edit",              # Added: can edit own prompts
        "prompt:delete",            # Added: can delete own prompts
        "prompt:manage",
        "document:read",
        "document:manage_own",
        "document:delete_own",      # Added: can delete own documents
        "document:reindex_own",     # Added: can reindex own documents
        "upload:create",
    },
}


def can(action: str, user: dict[str, Any]) -> bool:
    role = str(user.get("role", "viewer")).lower()
    if role not in _ROLE_ACTIONS:
        return False
    allowed = _ROLE_ACTIONS[role]
    return "*" in allowed or action in allowed





