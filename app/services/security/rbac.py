"""What each role may do, and the vocabulary both sides of that question use.

The permission strings were literals in two places that had to agree without
anything checking that they did: granted here, and checked at a hundred-odd call
sites across `app/api/`. A divergence fails *closed* -- the check simply never
matches -- so a role would quietly lose a capability and the only symptom would
be a 403 nobody could explain.

`Permission` is a `StrEnum`, so a member is a string: call sites can keep passing
it to `_require_permission`, comparisons still work, and nothing about the
runtime behaviour changes. What changes is that a typo is now an AttributeError
at import rather than a denial at request time, and that "which permissions
exist?" has an answer.

`tests/security/test_permission_vocabulary.py` keeps the two sides honest,
including the seven grants nothing currently checks -- see UNCHECKED_GRANTS.
"""

from enum import StrEnum
from typing import Any


class Permission(StrEnum):
    """Every permission this application recognises."""

    # Admin. Not granted to any role below: `admin` holds "*".
    ADMIN_OPS_MANAGE = "admin:ops_manage"
    ADMIN_USER_MANAGE = "admin:user_manage"
    ADMIN_AUDIT_READ = "admin:audit_read"

    QUERY_RUN = "query:run"
    UPLOAD_CREATE = "upload:create"

    SESSION_READ = "session:read"
    SESSION_CREATE = "session:create"
    SESSION_UPDATE = "session:update"
    SESSION_DELETE = "session:delete"
    SESSION_LOCK_STRATEGY = "session:lock_strategy"
    SESSION_MANAGE = "session:manage"  # legacy, see UNCHECKED_GRANTS

    MESSAGE_READ = "message:read"
    MESSAGE_EDIT = "message:edit"
    MESSAGE_DELETE = "message:delete"
    MESSAGE_MANAGE = "message:manage"  # legacy, see UNCHECKED_GRANTS

    PROMPT_READ = "prompt:read"
    PROMPT_CREATE = "prompt:create"
    PROMPT_EDIT = "prompt:edit"
    PROMPT_DELETE = "prompt:delete"
    PROMPT_MANAGE = "prompt:manage"  # legacy, see UNCHECKED_GRANTS

    DOCUMENT_READ = "document:read"
    DOCUMENT_MANAGE_OWN = "document:manage_own"
    DOCUMENT_DELETE_OWN = "document:delete_own"  # see UNCHECKED_GRANTS
    DOCUMENT_REINDEX_OWN = "document:reindex_own"  # see UNCHECKED_GRANTS


ALL_ROLES: str = "*"

_CONTENT_AUTHOR: set[str] = {
    Permission.QUERY_RUN,
    Permission.UPLOAD_CREATE,
    Permission.SESSION_READ,
    Permission.SESSION_CREATE,
    Permission.SESSION_DELETE,
    Permission.SESSION_LOCK_STRATEGY,
    Permission.MESSAGE_READ,
    Permission.MESSAGE_EDIT,
    Permission.MESSAGE_DELETE,
    Permission.PROMPT_READ,
    Permission.PROMPT_CREATE,
    Permission.PROMPT_EDIT,
    Permission.PROMPT_DELETE,
    Permission.PROMPT_MANAGE,
    Permission.DOCUMENT_READ,
    Permission.DOCUMENT_MANAGE_OWN,
    Permission.DOCUMENT_DELETE_OWN,
    Permission.DOCUMENT_REINDEX_OWN,
}

_ROLE_ACTIONS: dict[str, set[str]] = {
    "admin": {ALL_ROLES},
    # Analysts and viewers differ by two permissions and nothing else. They were
    # written out separately, which is why the difference was hard to see:
    # analysts may `session:manage` and `message:manage` (both legacy aliases),
    # viewers may `session:update`.
    "analyst": _CONTENT_AUTHOR | {Permission.SESSION_MANAGE, Permission.MESSAGE_MANAGE},
    "viewer": _CONTENT_AUTHOR | {Permission.SESSION_UPDATE},
}

# Granted to a role and asked for by nothing. Listed rather than removed: three
# are documented backward-compatibility aliases, and the other four look like
# grants that were added before -- or instead of -- the check that would use
# them. Removing a grant is a behaviour change for whoever relies on it; the
# test pins the list so the set cannot grow without somebody noticing.
UNCHECKED_GRANTS: frozenset[str] = frozenset(
    {
        Permission.SESSION_MANAGE,
        Permission.MESSAGE_MANAGE,
        Permission.PROMPT_MANAGE,
        Permission.MESSAGE_READ,
        Permission.SESSION_LOCK_STRATEGY,
        Permission.DOCUMENT_DELETE_OWN,
        Permission.DOCUMENT_REINDEX_OWN,
    }
)

# Checked at a call site and granted to no role but admin, which holds "*".
ADMIN_ONLY: frozenset[str] = frozenset(
    {
        Permission.ADMIN_OPS_MANAGE,
        Permission.ADMIN_USER_MANAGE,
        Permission.ADMIN_AUDIT_READ,
    }
)


def can(action: str, user: dict[str, Any]) -> bool:
    role = str(user.get("role", "viewer")).lower()
    if role not in _ROLE_ACTIONS:
        return False
    allowed = _ROLE_ACTIONS[role]
    return ALL_ROLES in allowed or action in allowed
