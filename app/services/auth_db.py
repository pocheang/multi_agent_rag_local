"""Backward-compatible import path for the canonical SQLite auth service.

The implementation lives in ``app.services.auth.auth_service``.  This module
must remain importable because API helpers and administrative scripts still
use the historical ``app.services.auth_db`` path.
"""

from app.services.auth.auth_service import AuthDBService

__all__ = ["AuthDBService"]
