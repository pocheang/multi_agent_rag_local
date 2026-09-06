"""A new user's reported chat credits are the credits actually stored.

`_create_user_record` returns `credit_balance: DEFAULT_CHAT_CREDITS` without
reading the row back, and its INSERT used to omit the column entirely -- so the
number a client saw came from the constant while the number in the database came
from the column default. That default was declared twice: a literal `10` in
`CREATE TABLE`, and `DEFAULT_CHAT_CREDITS` in the `ALTER TABLE` that upgrades an
older database. Three declarations, agreeing only because all three happened to
say ten.

Raising the constant would have split them: a fresh install would report the new
balance and store ten, an upgraded one would store the new balance, and the first
chat request would spend against a number nobody had been shown. Nothing would
have raised -- this is the "reports something other than what runs" failure, in
the ledger.

So the test does not assert the number is ten, which is the assertion that cannot
fail. It moves the constant and asserts the reported and stored values follow it
together. Run against the previous commit it fails, reporting 25 and storing 10.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.services.auth import auth_service as auth_service_module
from app.services.auth.auth_service import AuthDBService

_PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture
def service_factory():
    # Deliberately not pytest's tmp_path, matching test_connector_persistence:
    # its basetemp root needs directory permissions not available on every
    # Windows checkout.
    root = Path(tempfile.mkdtemp(prefix="querymind-credit-db-"))
    try:
        yield lambda name="auth.db": AuthDBService(db_path=root / name, token_ttl_hours=1)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _stored_balance(service: AuthDBService, user_id: str) -> int:
    conn = sqlite3.connect(service.db_path)
    try:
        row = conn.execute("SELECT credit_balance FROM users WHERE user_id=?", (user_id,)).fetchone()
    finally:
        conn.close()
    return int(row[0])


def test_reported_and_stored_balances_follow_the_same_constant(monkeypatch, service_factory):
    # 25 rather than the shipped 10, so a test that only ever sees the two agree
    # by coincidence cannot pass. The schema is built inside AuthDBService, after
    # the patch, which is the whole point: one constant reaches CREATE TABLE, the
    # INSERT and the returned dict.
    monkeypatch.setattr(auth_service_module, "DEFAULT_CHAT_CREDITS", 25)

    service = service_factory()
    created = service.create_user_with_role(username="alice", password=_PASSWORD, role="viewer")

    assert created["credit_balance"] == 25
    assert _stored_balance(service, created["user_id"]) == 25


def test_the_balance_survives_the_round_trip_through_login_and_the_admin_list(monkeypatch, service_factory):
    # Three readers of the same row -- the creation response, authenticate(), and
    # the administrative list -- must not disagree about what the user has to spend.
    monkeypatch.setattr(auth_service_module, "DEFAULT_CHAT_CREDITS", 25)

    service = service_factory()
    created = service.create_user_with_role(username="bob", password=_PASSWORD, role="viewer")

    authenticated = service.user_manager.authenticate("bob", _PASSWORD)
    listed = next(row for row in service.list_users() if row["user_id"] == created["user_id"])

    assert created["credit_balance"] == authenticated["credit_balance"] == listed["credit_balance"] == 25


def test_a_reserved_credit_is_spent_against_the_balance_that_was_reported(monkeypatch, service_factory):
    monkeypatch.setattr(auth_service_module, "DEFAULT_CHAT_CREDITS", 25)

    service = service_factory()
    created = service.create_user_with_role(username="carol", password=_PASSWORD, role="viewer")

    reserved = service.user_manager.reserve_chat_credit(created["user_id"])
    assert reserved["charged"] is True
    assert reserved["remaining"] == created["credit_balance"] - 1
