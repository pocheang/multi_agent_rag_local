"""The configuration centre is a settings source, and it cannot break startup.

Two properties matter more than the plumbing:

1. **Precedence.** Declared once, by source order in
   `Settings.settings_customise_sources`. The real process environment sits
   above the remote values so a deployment keeps one way to pin something the
   console cannot move -- `MODEL_BACKEND=local` already relies on that.

2. **Degradation.** `get_settings()` is on the path to everything, so an
   unreachable configuration centre must cost values, never a start. Remote,
   then the snapshot from the last good fetch, then nothing at all.

The third test here pins a trap rather than a behaviour: a source returning
field-name keys is *silently* ignored, because `Settings` validates by alias and
`extra="ignore"` drops what does not match. There is no error to notice, so the
only thing standing between a future backend and configuration that quietly
stops applying is a test that says which shape is correct.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from app.core import remote_config
from app.core.config import Settings
from app.core.remote_config import (
    RemoteConfigSettings,
    RemoteSettingsSource,
    parse_properties,
    watch_remote_config,
)

DOCUMENT = "ENABLE_CALIBRATION=true\nTOP_K=17\n"


def _config(**overrides) -> RemoteConfigSettings:
    base = {
        "enabled": True,
        "server_addr": "nacos.test:8848",
        "namespace": "test",
        "group": "DEFAULT_GROUP",
        "data_ids": ("querymind",),
        "username": "",
        "password": "",
        "timeout_ms": 3000,
    }
    base.update(overrides)
    return RemoteConfigSettings(**base)


class FakeClient:
    """A configuration centre that answers, or refuses to."""

    def __init__(self, documents: dict[str, str] | None = None, error: Exception | None = None) -> None:
        self.documents = documents or {}
        self.error = error
        self.fetches: list[str] = []
        self.watched: list[tuple[str, str]] = []

    def fetch(self, group: str, data_id: str) -> str | None:
        self.fetches.append(data_id)
        if self.error is not None:
            raise self.error
        return self.documents.get(data_id)

    def watch(self, group: str, data_id: str, callback: Callable[[], None]) -> None:
        self.watched.append((group, data_id))


def _probe(source: PydanticBaseSettingsSource | None) -> type[Settings]:
    """A Settings subclass with one source swapped for the one under test."""

    class Probe(Settings):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls,
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        ):
            middle = () if source is None else (source,)
            return (init_settings, env_settings, *middle, dotenv_settings, file_secret_settings)

    return Probe


@pytest.fixture(autouse=True)
def _snapshot_in_tmp(monkeypatch):
    """Never write a snapshot into the repository during a test.

    Deliberately not pytest's `tmp_path`: its basetemp root needs directory
    permissions that are not available on every Windows checkout, the same
    reason `tests/agents/test_closed_loops.py` builds its own.
    """

    root = Path(tempfile.mkdtemp(prefix="querymind-remote-config-"))
    monkeypatch.setattr(remote_config, "SNAPSHOT_ROOT", root)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_a_process_without_a_configuration_centre_pays_nothing():
    """Off unless explicitly enabled -- and then it does not even build a client."""

    client = FakeClient({"querymind": DOCUMENT})
    source = RemoteSettingsSource(Settings, client=client, config=_config(enabled=False))

    assert source() == {}
    assert client.fetches == []


def test_remote_values_reach_settings():
    source = RemoteSettingsSource(Settings, client=FakeClient({"querymind": DOCUMENT}), config=_config())
    settings = _probe(source)()

    assert settings.enable_calibration is True
    assert settings.top_k == 17


def test_a_source_must_return_alias_keys():
    """The silent failure this module exists to avoid.

    Field-name keys validate to nothing: `Settings` matches by alias and
    `extra="ignore"` drops the rest, so a backend returning `enable_calibration`
    instead of `ENABLE_CALIBRATION` would apply no configuration at all and
    raise nothing while doing it.
    """

    by_field_name = RemoteSettingsSource(
        Settings,
        client=FakeClient({"querymind": "enable_calibration=true\ntop_k=17\n"}),
        config=_config(),
    )
    settings = _probe(by_field_name)()

    assert settings.enable_calibration is False
    assert settings.top_k == 4


def test_the_process_environment_outranks_the_configuration_centre(monkeypatch):
    """A deployment keeps one pin the console cannot move."""

    monkeypatch.setenv("TOP_K", "3")
    source = RemoteSettingsSource(Settings, client=FakeClient({"querymind": DOCUMENT}), config=_config())

    assert _probe(source)().top_k == 3


def test_later_data_ids_override_earlier_ones():
    client = FakeClient({"base": "TOP_K=5\n", "overlay": "TOP_K=9\n"})
    source = RemoteSettingsSource(Settings, client=client, config=_config(data_ids=("base", "overlay")))

    assert _probe(source)().top_k == 9


def test_an_unreachable_centre_falls_back_to_the_last_good_fetch():
    """The snapshot is what makes the dependency survivable."""

    config = _config()
    good = RemoteSettingsSource(Settings, client=FakeClient({"querymind": DOCUMENT}), config=config)
    assert _probe(good)().top_k == 17

    down = RemoteSettingsSource(Settings, client=FakeClient(error=TimeoutError("nacos down")), config=config)
    assert _probe(down)().top_k == 17


def test_no_centre_and_no_snapshot_still_starts():
    """Values are lost; the process is not."""

    source = RemoteSettingsSource(Settings, client=FakeClient(error=TimeoutError("down")), config=_config())

    assert source() == {}
    assert _probe(source)().top_k == 4


def test_a_missing_document_is_not_an_error():
    """A data id nobody has published yet leaves the lower sources in charge."""

    source = RemoteSettingsSource(Settings, client=FakeClient({}), config=_config())

    assert source() == {}


def test_a_malformed_line_does_not_take_the_process_down():
    source = RemoteSettingsSource(
        Settings,
        client=FakeClient({"querymind": "this line has no equals sign\nTOP_K=11\n"}),
        config=_config(),
    )

    assert _probe(source)().top_k == 11


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# comment\n\nA=1\n", {"A": "1"}),
        ('B="quoted"\n', {"B": "quoted"}),
        ("C='single'\n", {"C": "single"}),
        ("D=has=equals\n", {"D": "has=equals"}),
        ("  E  =  spaced  \n", {"E": "spaced"}),
        ("=novalue\n", {}),
    ],
)
def test_parse_properties(text, expected):
    assert parse_properties(text) == expected


def test_watching_is_off_when_the_centre_is(monkeypatch):
    monkeypatch.delenv("NACOS_ENABLED", raising=False)

    assert watch_remote_config(lambda: None) is False


def test_watching_covers_every_data_id(monkeypatch):
    monkeypatch.setenv("NACOS_ENABLED", "true")
    monkeypatch.setenv("NACOS_SERVER_ADDR", "nacos.test:8848")
    monkeypatch.setenv("NACOS_DATA_IDS", "base,overlay")
    client = FakeClient()

    assert watch_remote_config(lambda: None, client=client) is True
    assert client.watched == [("DEFAULT_GROUP", "base"), ("DEFAULT_GROUP", "overlay")]


class _Marker(PydanticBaseSettingsSource):
    """A stand-in, so the order can be read without building real sources."""

    def get_field_value(self, field, field_name):
        return None, field_name, False

    def __call__(self):
        return {}


def test_settings_declares_the_source_order():
    """The precedence in the docstring is the precedence in the code.

    init > process environment > configuration centre > .runtime/*.env > defaults
    """

    init, env, dotenv, secrets = (_Marker(Settings) for _ in range(4))
    order = Settings.settings_customise_sources(Settings, init, env, dotenv, secrets)

    assert order[0] is init
    assert order[1] is env
    assert type(order[2]).__name__ == "RemoteSettingsSource"
    assert order[3] is dotenv


def test_the_remote_source_is_inert_for_a_default_checkout(monkeypatch):
    """No NACOS_* set: `Settings()` behaves exactly as it did before."""

    for key in ("NACOS_ENABLED", "NACOS_SERVER_ADDR", "NACOS_DATA_IDS"):
        monkeypatch.delenv(key, raising=False)

    assert isinstance(Settings(), BaseSettings)
    assert RemoteSettingsSource(Settings)() == {}
