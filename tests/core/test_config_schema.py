"""What the console may change, and whether it can tell the truth about it.

Two properties, and the second is the reason the module exists.

**The allowlist cannot rot.** A field renamed in `Settings` must not leave a dead
entry behind that silently stops being editable, so every alias is checked
against the model.

**Nothing secret-shaped is editable.** The registry is the whole surface a
console-holder can reach; a path, a key or a credential appearing in it is a
privilege escalation, not a configuration change. That is asserted by shape
rather than by listing today's fields, so a future addition has to defeat the
rule deliberately.

And the column the page exists for: which layer supplied each value. A value
pinned in the process environment outranks the configuration centre, so an
administrator editing it would see a successful save and no effect. `describe`
reports that as `editable_here=False` and the endpoint refuses the write.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.config_schema import EDITABLE, ConfigLayer, describe, validate_values

ALIASES = {field.alias for field in EDITABLE}
SETTINGS_ALIASES = {field.alias or name for name, field in Settings.model_fields.items()}

# Substrings that mark a value nobody should be able to change from a browser.
FORBIDDEN = ("KEY", "SECRET", "PASSWORD", "TOKEN", "PATH", "URL", "DSN", "CORS", "ORIGIN")


class _Documents:
    """Stands in for `RemoteDocuments` without touching a network."""

    def __init__(self, documents: dict[str, str]) -> None:
        self._documents = documents

    def all(self) -> dict[str, str]:
        return dict(self._documents)


def test_every_editable_alias_exists_on_settings():
    """A rename in Settings must not leave a dead entry that silently does nothing."""

    missing = sorted(ALIASES - SETTINGS_ALIASES)
    assert not missing, f"not fields on Settings: {missing}"


def test_the_registry_has_no_duplicates():
    assert len(ALIASES) == len(EDITABLE)


def test_nothing_secret_shaped_is_editable():
    """The registry is the whole reach of a console account."""

    offenders = sorted(alias for alias in ALIASES if any(word in alias for word in FORBIDDEN))
    assert not offenders, (
        f"these look like credentials, paths or endpoints: {offenders}. "
        "Editing one from a browser is a privilege escalation, not a configuration change."
    )


def test_every_field_says_what_it_does():
    """A console with unexplained switches gets used wrongly."""

    silent = sorted(field.alias for field in EDITABLE if len(field.summary) < 15)
    assert not silent, silent


def test_a_value_from_the_defaults_is_reported_as_default(monkeypatch):
    for field in EDITABLE:
        monkeypatch.delenv(field.alias, raising=False)
    rows = {row["alias"]: row for row in describe(Settings(), _Documents({}))}

    assert rows["TOP_K"]["layer"] == str(ConfigLayer.DEFAULT)
    assert rows["TOP_K"]["value"] == 4
    assert rows["TOP_K"]["editable_here"] is True


def test_a_value_pinned_in_the_environment_is_not_editable_here(monkeypatch):
    """The deployment's pin outranks the console, and the page has to say so."""

    monkeypatch.setenv("TOP_K", "11")
    rows = {row["alias"]: row for row in describe(Settings(), _Documents({}))}

    assert rows["TOP_K"]["layer"] == str(ConfigLayer.ENVIRONMENT)
    assert rows["TOP_K"]["value"] == 11
    assert rows["TOP_K"]["editable_here"] is False


def test_a_value_from_the_configuration_centre_is_labelled_as_such(monkeypatch):
    monkeypatch.delenv("TOP_K", raising=False)
    documents = _Documents({"querymind": "TOP_K=9\n"})
    rows = {row["alias"]: row for row in describe(Settings(), documents)}

    assert rows["TOP_K"]["layer"] == str(ConfigLayer.CONFIG_CENTRE)
    assert rows["TOP_K"]["editable_here"] is True


def test_the_layers_are_reported_in_the_precedence_settings_declares(monkeypatch):
    """Environment beats the centre, for the same key, in the same call."""

    monkeypatch.setenv("TOP_K", "11")
    documents = _Documents({"querymind": "TOP_K=9\n"})
    rows = {row["alias"]: row for row in describe(Settings(), documents)}

    assert rows["TOP_K"]["layer"] == str(ConfigLayer.ENVIRONMENT)


def test_validate_accepts_a_well_typed_change():
    assert validate_values({"TOP_K": "15"}) == {"TOP_K": "15"}


def test_validate_rejects_a_field_that_is_not_editable():
    with pytest.raises(ValueError, match="not editable"):
        validate_values({"APP_DB_PATH": "/tmp/anything"})


def test_validate_rejects_a_value_of_the_wrong_type():
    """Better here than at the next request, where nobody is looking."""

    with pytest.raises(ValueError, match="TOP_K"):
        validate_values({"TOP_K": "fifteen"})
