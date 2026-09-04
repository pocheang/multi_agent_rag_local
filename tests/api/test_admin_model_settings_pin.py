"""The model settings page must say whether its settings are in effect.

A deployment can pin the offline backend with `MODEL_BACKEND=local` as a real
environment variable, and `get_chat_model` then discards the global override
outright (`_local_backend_forced`). Before this, `GET /admin/model-settings`
returned only the stored values -- so an admin could fill in an OpenAI key and
model, get a success response, see the values echoed back, and have an audit row
saying the save succeeded, while every answer still came from
`LocalEvidenceChatModel`.

That is the failure this codebase keeps finding in its own surfaces: a page
reporting something other than what runs. `GET /api/advanced-rag/config` had it,
the ops grounding SLO had it, and the audit-action filter had it.

Note what is *not* done here. The configuration page next door refuses a write to
a value the environment pins, because that write would go to a layer the process
does not read. This write persists correctly and takes effect the moment the pin
is removed, so refusing it would block legitimate preparation. It is accepted and
reported inert instead.
"""

from __future__ import annotations

import pytest

from app.api.dependencies import _admin_model_settings_view

_STORED = {
    "enabled": True,
    "provider": "openai",
    # Deliberately not shaped like a real key. This test needs a non-empty
    # string to prove the view masks it, not a credential shape -- and
    # scripts/check_sensitive.py correctly refuses one that has the shape.
    "api_key": "placeholder-credential-value",
    "base_url": "",
    "chat_model": "gpt-5.5",
    "reasoning_model": "",
    "embedding_model": "text-embedding-3-small",
    "temperature": 0.7,
    "max_tokens": 2048,
}


@pytest.fixture
def pinned(monkeypatch):
    monkeypatch.setenv("MODEL_BACKEND", "local")


@pytest.fixture
def unpinned(monkeypatch):
    monkeypatch.delenv("MODEL_BACKEND", raising=False)


def test_a_pinned_environment_is_reported(pinned: None):
    """The assertion that would have caught it."""

    view = _admin_model_settings_view(_STORED).settings

    assert view.environment_pinned is True
    assert "MODEL_BACKEND" in view.pinned_reason


def test_an_unpinned_environment_reports_nothing(unpinned: None):
    """The negative direction, so the test above cannot pass by the flag being
    stuck on."""

    view = _admin_model_settings_view(_STORED).settings

    assert view.environment_pinned is False
    assert view.pinned_reason == ""


def test_the_stored_settings_are_still_returned_when_pinned(pinned: None):
    """Pinned means inert, not lost. The values persist and take effect when the
    pin is removed, which is why the write is accepted rather than refused."""

    view = _admin_model_settings_view(_STORED).settings

    assert view.provider == "openai"
    assert view.chat_model == "gpt-5.5"
    assert view.enabled is True


def test_the_api_key_is_never_returned(pinned: None):
    """Unchanged by this, and worth pinning next to it: the view masks."""

    view = _admin_model_settings_view(_STORED).settings

    assert "placeholder-credential-value" not in view.model_dump_json()
    assert view.api_key_masked


def test_the_enabled_flag_describes_what_it_actually_does():
    """`get_chat_model` resolves `global_override or user_override`, so an enabled
    global config wins over a user's own settings -- their key stops being used.

    The description used to say it applied "to users without personal overrides",
    which is the opposite, and an admin ticking that box on that promise would
    silently move every user's traffic onto the org's account.
    """

    from app.api.schemas import AdminModelSettings

    description = AdminModelSettings.model_fields["enabled"].description or ""

    assert "without personal overrides" not in description
    assert "overriding" in description.lower()
