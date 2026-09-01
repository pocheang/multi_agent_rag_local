"""Connectors and their credentials must outlive the process.

Both repositories were process-local dicts. That was survivable only while the
governed tool path could not execute anything: a restart silently emptied every
user's integrations, and a connector configured on one worker was invisible to
the next. Now that a chat request can actually disable a connector, "it exists"
has to mean something durable.

The pairing matters as much as either half. Credentials living in a dict while
metadata pointed at them by id meant a restart could leave a connector that
survived its own credential -- every call through it failing an owner check it
could never pass again.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.mcp.contracts import ConnectorCredential
from app.services.connectors.contracts import ConnectorMetadata
from app.services.connectors.metadata_repository import ConnectorMetadataRepository
from app.services.connectors.repository import CredentialRepository

_OWNER = "user-alice"


@pytest.fixture
def db_path():
    # Deliberately not pytest's tmp_path: its basetemp root needs directory
    # permissions that are not available on every Windows checkout.
    root = Path(tempfile.mkdtemp(prefix="querymind-connector-db-"))
    path = root / "app.db"
    # Both tables carry an ON DELETE CASCADE reference to users, so a connector
    # cannot outlive the account that owns it -- encrypted secrets least of all.
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (user_id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO users VALUES (?)", (_OWNER,))
    conn.commit()
    conn.close()
    try:
        yield path
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _metadata(connector_id: str = "slack", **overrides) -> ConnectorMetadata:
    return ConnectorMetadata(
        **{
            "connector_id": connector_id,
            "owner_id": _OWNER,
            "name": "Slack",
            "base_url": "https://slack.com/api",
            "allowed_hosts": frozenset({"slack.com"}),
            "credential_id": "cred-1",
            "credential_display": "••••abcd",
            **overrides,
        }
    )


def _credential(credential_id: str = "cred-1") -> ConnectorCredential:
    return ConnectorCredential(
        credential_id=credential_id,
        connector_id="slack",
        owner_id=_OWNER,
        encrypted_secret="ciphertext",
        display_value="••••abcd",
    )


# --- metadata ---------------------------------------------------------------


def test_a_connector_survives_a_new_repository_instance(db_path):
    """The restart case, as directly as a test can state it."""
    ConnectorMetadataRepository(db_path).create(_metadata())

    reopened = ConnectorMetadataRepository(db_path).get("slack", _OWNER)

    assert reopened is not None
    assert reopened.name == "Slack"
    assert reopened.allowed_hosts == frozenset({"slack.com"})
    assert str(reopened.base_url).startswith("https://slack.com")


def test_a_status_change_survives_too(db_path):
    repository = ConnectorMetadataRepository(db_path)
    repository.create(_metadata())
    repository.replace(_metadata().model_copy(update={"status": "disabled"}))

    assert ConnectorMetadataRepository(db_path).get("slack", _OWNER).status == "disabled"


def test_a_duplicate_is_refused_by_the_primary_key(db_path):
    """The dict version read, compared, then wrote under a lock, which only made
    the race single-process."""
    repository = ConnectorMetadataRepository(db_path)
    repository.create(_metadata())

    with pytest.raises(ValueError, match="already exists"):
        repository.create(_metadata())


def test_replacing_something_that_is_not_there_raises(db_path):
    with pytest.raises(KeyError):
        ConnectorMetadataRepository(db_path).replace(_metadata())


def test_one_owner_never_sees_another_owners_connector(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO users VALUES ('user-mallory')")
    conn.commit()
    conn.close()
    repository = ConnectorMetadataRepository(db_path)
    repository.create(_metadata())
    repository.create(_metadata(owner_id="user-mallory"))

    assert repository.get("slack", "user-mallory").owner_id == "user-mallory"
    assert [item.owner_id for item in repository.list_for_owner(_OWNER)] == [_OWNER]


def test_listing_is_ordered_so_the_ui_does_not_reshuffle(db_path):
    repository = ConnectorMetadataRepository(db_path)
    for connector_id in ("zendesk", "asana", "slack"):
        repository.create(_metadata(connector_id))

    assert [item.connector_id for item in repository.list_for_owner(_OWNER)] == ["asana", "slack", "zendesk"]


# --- credentials ------------------------------------------------------------


def test_a_credential_survives_a_new_repository_instance(db_path):
    CredentialRepository(db_path).save(_credential())

    reopened = CredentialRepository(db_path).get_for_owner("cred-1", _OWNER)

    assert reopened is not None
    assert reopened.encrypted_secret == "ciphertext"


def test_a_credential_is_not_readable_by_another_owner(db_path):
    CredentialRepository(db_path).save(_credential())

    assert CredentialRepository(db_path).get_for_owner("cred-1", "user-mallory") is None


def test_saving_the_same_credential_id_twice_updates_rather_than_fails(db_path):
    repository = CredentialRepository(db_path)
    repository.save(_credential())
    repository.save(_credential().model_copy(update={"encrypted_secret": "rotated"}))

    assert repository.get_for_owner("cred-1", _OWNER).encrypted_secret == "rotated"


# --- the two together -------------------------------------------------------


def test_deleting_a_user_takes_their_connectors_and_secrets_with_them(db_path):
    """Encrypted credentials outliving the account they belong to is the kind of
    residue an in-memory store hid by losing everything on restart."""
    ConnectorMetadataRepository(db_path).create(_metadata())
    CredentialRepository(db_path).save(_credential())

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM users WHERE user_id = ?", (_OWNER,))
    conn.commit()
    conn.close()

    assert ConnectorMetadataRepository(db_path).get("slack", _OWNER) is None
    assert CredentialRepository(db_path).get_for_owner("cred-1", _OWNER) is None
