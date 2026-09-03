"""The audit log's vocabulary, in one place.

These names are written at some seventy call sites across ``app/api`` and read
back by string comparison in two other places: the operations counters in
``app/services/runtime/runtime_ops.py`` and the admin console's action filter.
Three lists that had to agree with nothing checking that they did -- and unlike
the permission vocabulary next door, a divergence here fails *silently*: a
counter that matches no row reports zero and a filter that matches no row
reports "no results", neither of which looks like a defect to anyone.

``StrEnum``, so members are strings and no call site changes behaviour.  What
changes is that a name that does not exist is an ``AttributeError`` at import
rather than a metric that quietly reads nothing.
"""

from __future__ import annotations

from enum import StrEnum


class AuditAction(StrEnum):
    """Every action name the application writes to the audit log."""

    # Authentication and account lifecycle
    AUTH_REGISTER = "auth.register"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_CHANGE_PASSWORD = "auth.change_password"
    AUTH_GOOGLE_LOGIN = "auth.google_login"
    AUTH_GOOGLE_REGISTER = "auth.google_register"
    AUTH_GOOGLE_CALLBACK = "auth.google_callback"
    AUTH_ACCESS_DENIED = "auth.access_denied"
    AUTH_PERMISSION_DENIED = "auth.permission_denied"
    PROFILE_UPDATED = "profile.updated"
    API_KEY_DECRYPTION_FAILED = "api_key.decryption_failed"
    API_KEY_DECRYPTION_ERROR = "api_key.decryption_error"

    # Sessions, messages and memory
    SESSION_CREATE = "session.create"
    SESSION_RENAME = "session.rename"
    SESSION_PIN = "session.pin"
    SESSION_DELETE = "session.delete"
    MESSAGE_UPDATE = "message.update"
    MESSAGE_DELETE = "message.delete"
    MEMORY_LONG_DELETE = "memory.long.delete"

    # Documents and uploads
    UPLOAD_CREATE = "upload.create"
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_REINDEX = "document.reindex"
    DOCUMENT_DELETE = "document.delete"

    # Query admission -- written only when a query is refused
    QUERY_LOAD_GUARD = "query.load_guard"
    QUERY_CREDIT_RESERVE = "query.credit_reserve"
    QUERY_SOURCE_SCOPE = "query.source_scope"

    # Prompt library
    PROMPT_CHECK = "prompt.check"
    PROMPT_CREATE = "prompt.create"
    PROMPT_UPDATE = "prompt.update"
    PROMPT_DELETE = "prompt.delete"
    PROMPT_VERSION_APPROVE = "prompt.version.approve"
    PROMPT_VERSION_ROLLBACK = "prompt.version.rollback"

    # Administration
    ADMIN_USER_CREATE_ADMIN = "admin.user.create_admin"
    ADMIN_USER_ROLE_UPDATE = "admin.user.role_update"
    ADMIN_USER_STATUS_UPDATE = "admin.user.status_update"
    ADMIN_USER_CLASSIFICATION_UPDATE = "admin.user.classification_update"
    ADMIN_USER_CREDITS_ADD = "admin.user.credits_add"
    ADMIN_USER_RESET_PASSWORD = "admin.user.reset_password"
    ADMIN_USER_RESET_APPROVAL_TOKEN = "admin.user.reset_approval_token"
    ADMIN_CONFIG_SAVE = "admin.config.save"
    ADMIN_CONFIG_RELOAD = "admin.config.reload"
    ADMIN_MODEL_SETTINGS_SAVE = "admin.model_settings.save"
    ADMIN_MODEL_SETTINGS_TEST = "admin.model_settings.test"
    ADMIN_LOGGING_SET_LEVEL = "admin.logging.set_level"
    ADMIN_LOGGING_RESET = "admin.logging.reset"
    ADMIN_OPS_BENCHMARK_RUN = "admin.ops.benchmark.run"
    ADMIN_OPS_REPLAY_RUN = "admin.ops.replay.run"
    ADMIN_OPS_AUTOTUNE = "admin.ops.autotune"
    USER_API_SETTINGS_TEST = "user.api_settings.test"


__all__ = ["AuditAction"]
