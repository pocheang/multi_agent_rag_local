"""Every administrative read of a user returns the same shape, from one query.

The projection below -- the stored columns plus `has_admin_approval_token`,
`is_online` and `is_online_10m`, which are derived -- was written out six times
in `user_manager.py`, five of them character for character identical. Nothing
checked that the six agreed, and `AdminUserSummary` defaults every derived field
to `False`, so a copy that lost a column would not have raised: that endpoint
would simply have reported an admin with an approval token as having none, and
an online user as offline. The response model cannot tell a missing key from a
false one.

So these tests do not assert that the SQL is shared. They assert what sharing it
is for: that each method returning the administrative shape returns *the same*
shape, with the derived columns actually derived. A future edit that reintroduces
one divergent copy fails here rather than at a reader's screen.

The last test pins something found by reading those six copies together: a credit
top-up answers from the row it changed rather than from a scan of every user.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.services.auth.user_manager import DEFAULT_CHAT_CREDITS, UserManager
from app.services.auth.utils import iso, now

# What an administrative read promises its callers. `AdminUserSummary` in
# app/api/schemas/http.py consumes exactly these; a key it does not receive
# silently takes the model's default.
_ADMIN_VIEW_KEYS = frozenset(
    {
        "user_id",
        "username",
        "role",
        "status",
        "created_by_user_id",
        "created_by_username",
        "admin_ticket_id",
        "has_admin_approval_token",
        "business_unit",
        "department",
        "user_type",
        "data_scope",
        "credit_balance",
        "is_online",
        "is_online_10m",
        "created_at",
    }
)

_USER_ID = "0f9c1e2a3b4d4f5a8c7b6e5d4c3b2a19"
_ADMIN_ID = "1a2b3c4d5e6f4a5b8c9d0e1f2a3b4c5d"


@pytest.fixture
def manager():
    # Deliberately not pytest's tmp_path, matching test_connector_persistence:
    # its basetemp root needs directory permissions not available on every
    # Windows checkout.
    root = Path(tempfile.mkdtemp(prefix="querymind-user-db-"))
    path = root / "auth.db"

    def connect() -> sqlite3.Connection:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    with connect() as conn:
        conn.execute(
            f"""
            CREATE TABLE users (
              user_id TEXT PRIMARY KEY,
              username TEXT NOT NULL UNIQUE COLLATE NOCASE,
              salt TEXT NOT NULL,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'viewer',
              status TEXT NOT NULL DEFAULT 'active',
              created_by_user_id TEXT,
              created_by_username TEXT,
              admin_ticket_id TEXT,
              admin_approval_token_hash TEXT,
              business_unit TEXT,
              department TEXT,
              user_type TEXT,
              data_scope TEXT,
              display_name TEXT,
              credit_balance INTEGER NOT NULL DEFAULT {DEFAULT_CHAT_CREDITS} CHECK(credit_balance >= 0),
              created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE auth_sessions (
              token TEXT PRIMARY KEY,
              user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
              username TEXT NOT NULL,
              issued_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              expires_at TEXT NOT NULL
            )
            """
        )
        created_at = iso(now())
        conn.execute(
            "INSERT INTO users(user_id, username, salt, password_hash, role, created_at) VALUES (?,?,?,?,?,?)",
            (_USER_ID, "alice", "s", "h", "viewer", created_at),
        )
        conn.execute(
            "INSERT INTO users(user_id, username, salt, password_hash, role, created_at) VALUES (?,?,?,?,?,?)",
            (_ADMIN_ID, "root", "s", "h", "admin", created_at),
        )

    try:
        yield UserManager(connect)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _mutations(manager: UserManager):
    """Every method whose contract is to return the administrative shape."""
    return {
        "update_user_role": lambda: manager.update_user_role(_USER_ID, "analyst"),
        "update_user_status": lambda: manager.update_user_status(_USER_ID, "active"),
        "update_user_admin_approval_token": lambda: manager.update_user_admin_approval_token(_USER_ID, "hash", "T-1"),
        "update_user_password": lambda: manager.update_user_password(_USER_ID, "Str0ng!Passw0rd"),
        "update_user_classification": lambda: manager.update_user_classification(_USER_ID, business_unit="research"),
        "add_user_credits": lambda: manager.add_user_credits(_USER_ID, 5),
    }


def test_every_administrative_read_returns_the_same_keys(manager):
    listed = manager.list_users()
    assert {row["user_id"] for row in listed} == {_USER_ID, _ADMIN_ID}
    assert set(listed[0]) == _ADMIN_VIEW_KEYS

    for name, call in _mutations(manager).items():
        row = call()
        assert row is not None, f"{name} returned None for an existing user"
        assert set(row) == _ADMIN_VIEW_KEYS, f"{name} returned a different shape"
        assert row["user_id"] == _USER_ID


def test_the_approval_token_is_reported_as_a_flag_and_never_as_its_hash(manager):
    # The column holds a SHA-256 of the token. The administrative view answers
    # whether one is set; the hash itself must not travel with it.
    before = manager.update_user_role(_USER_ID, "viewer")
    assert before["has_admin_approval_token"] == 0

    after = manager.update_user_admin_approval_token(_USER_ID, "a-token-hash", "TICKET-9")
    assert after["has_admin_approval_token"] == 1
    assert "admin_approval_token_hash" not in after
    assert "a-token-hash" not in str(after)
    assert after["admin_ticket_id"] == "TICKET-9"

    # Blank clears it, rather than storing an empty string that reads as "set".
    cleared = manager.update_user_admin_approval_token(_USER_ID, "   ")
    assert cleared["has_admin_approval_token"] == 0


def test_presence_is_derived_from_live_sessions_by_every_reader(manager):
    with manager.conn_factory() as conn:
        conn.execute(
            "INSERT INTO auth_sessions(token, user_id, username, issued_at, last_seen_at, expires_at) "
            "VALUES (?,?,?,?,?,?)",
            ("tok", _USER_ID, "alice", iso(now()), iso(now()), iso(now().replace(year=now().year + 1))),
        )

    listed = next(row for row in manager.list_users() if row["user_id"] == _USER_ID)
    assert listed["is_online"] == 1
    assert listed["is_online_10m"] == 1

    # The same live session, seen through a mutation's read-back.
    updated = manager.update_user_classification(_USER_ID, department="platform")
    assert updated["is_online"] == 1
    assert updated["is_online_10m"] == 1

    # update_user_password deletes the sessions, so its own read-back must show it.
    after_reset = manager.update_user_password(_USER_ID, "An0ther!Passw0rd")
    assert after_reset["is_online"] == 0
    assert after_reset["is_online_10m"] == 0


def test_a_missing_user_is_none_rather_than_a_partial_row(manager):
    absent = "ffffffffffffffffffffffffffffffff"
    assert manager.update_user_role(absent, "analyst") is None
    assert manager.update_user_status(absent, "active") is None
    assert manager.update_user_classification(absent, department="x") is None
    assert manager.update_user_admin_approval_token(absent, "h") is None
    assert manager.update_user_password(absent, "Str0ng!Passw0rd") is None
    assert manager.add_user_credits(absent, 1) is None


def test_a_credit_top_up_answers_from_the_row_it_changed(manager):
    # It used to return next(row for row in self.list_users() if ...) -- every user,
    # two joins and a second connection, to read back the one row just updated.
    start = next(row for row in manager.list_users() if row["user_id"] == _USER_ID)["credit_balance"]
    row = manager.add_user_credits(_USER_ID, 7)
    assert row["credit_balance"] == start + 7
    assert row["user_id"] == _USER_ID

    listed = next(r for r in manager.list_users() if r["user_id"] == _USER_ID)
    assert listed["credit_balance"] == row["credit_balance"]

    with pytest.raises(ValueError, match="administrator"):
        manager.add_user_credits(_ADMIN_ID, 1)
