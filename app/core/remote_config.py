"""A configuration centre as a settings source, not as a fourth layer.

`Settings` stays the single schema: types, defaults, aliases and validation all
live there, and this module only supplies values for it to validate. The
alternative -- fetching the remote configuration at startup and writing it into
`os.environ` -- was rejected twice over: it destroys the "a deployment can pin a
value the configuration centre cannot move" semantics that `MODEL_BACKEND=local`
already relies on, and it smuggles values past `Settings`'s own validation.

Precedence is therefore declared once, by the source order in
`Settings.settings_customise_sources`:

    init > real process environment > remote configuration > .runtime/*.env > defaults

**Nothing here may block or break startup.** A configuration centre is an
external dependency on the path to `get_settings()`, which is on the path to
everything. Three levels of degradation, in order: the remote value, the local
snapshot written by the last successful fetch, and finally nothing at all --
which simply leaves the lower sources (`.runtime/*.env`, then field defaults) in
charge. Every failure is logged and swallowed.

**A source must return values keyed by field *alias*.** `{"ENABLE_CALIBRATION":
True}` is applied; `{"enable_calibration": True}` is silently ignored, because
`Settings` validates by alias and `extra="ignore"` drops the rest. Silently is
the operative word -- there is no error to notice -- so
`tests/core/test_remote_config_source.py` pins it. Aliases are also what
`config/env/*` and the rendered runtime file already use, so one name follows a
value from the repository to the console.

Bootstrap (`NACOS_*`) is read from the real environment and is deliberately not
in `Settings`: it configures the thing that supplies `Settings`, the same
chicken-and-egg that keeps `APP_ENV` and `RUNTIME_ENV_FILE` out of it.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic.fields import FieldInfo
from pydantic_settings import PydanticBaseSettingsSource

logger = logging.getLogger(__name__)

SNAPSHOT_ROOT = Path(".runtime") / "remote-config"


class RemoteConfigClient(Protocol):
    """The two operations a configuration centre has to provide.

    Narrow on purpose: it is what a fake in a test has to implement, and the
    whole surface a different backend would have to satisfy. Change detection is
    deliberately *not* part of it -- see `watch_remote_config`, which polls
    `fetch`.
    """

    def fetch(self, group: str, data_id: str) -> str | None:
        """Return the raw document, or None when it is unavailable."""

    def publish(self, group: str, data_id: str, content: str) -> bool:
        """Replace the document. Returns whether the centre accepted it."""


@dataclass(frozen=True)
class RemoteConfigSettings:
    """Bootstrap, read from the real process environment."""

    enabled: bool
    server_addr: str
    namespace: str
    group: str
    data_ids: tuple[str, ...]
    username: str
    password: str
    timeout_ms: int
    poll_interval_ms: int = 30_000

    @property
    def snapshot_dir(self) -> Path:
        return SNAPSHOT_ROOT / (self.namespace or "public") / self.group


def _bootstrap() -> RemoteConfigSettings:
    """Read the `NACOS_*` bootstrap.

    Off unless `NACOS_ENABLED` is explicitly true, so an installation that has
    not adopted a configuration centre pays nothing -- not even an import of the
    SDK.
    """

    raw_ids = os.getenv("NACOS_DATA_IDS", "querymind").strip()
    return RemoteConfigSettings(
        enabled=os.getenv("NACOS_ENABLED", "false").strip().lower() == "true",
        server_addr=os.getenv("NACOS_SERVER_ADDR", "").strip(),
        namespace=os.getenv("NACOS_NAMESPACE", "").strip(),
        group=os.getenv("NACOS_GROUP", "DEFAULT_GROUP").strip(),
        data_ids=tuple(part.strip() for part in raw_ids.split(",") if part.strip()),
        username=os.getenv("NACOS_USERNAME", "").strip(),
        password=os.getenv("NACOS_PASSWORD", ""),
        timeout_ms=int(os.getenv("NACOS_TIMEOUT_MS", "3000")),
        poll_interval_ms=int(os.getenv("NACOS_POLL_INTERVAL_MS", "30000")),
    )


def parse_properties(text: str) -> dict[str, str]:
    """Parse the `KEY=value` form the rendered runtime file already uses.

    Mirrors `deploy/scripts/config.py::parse_env_file` so one document format
    travels from `config/env/*` through the render step to the console. A
    malformed line is skipped rather than raising: a typo in a remote document
    must not take the process down, and the lower sources still have the value.
    """

    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            logger.warning("remote config: skipping malformed line")
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values


class RemoteDocuments:
    """Fetching and snapshotting, with no pydantic in it.

    Separate from `RemoteSettingsSource` because the poller needs exactly this
    and has no settings class to give a `PydanticBaseSettingsSource`. Keeping
    them one class meant constructing a source around a placeholder type, which
    is a sign the responsibility was mixed rather than a thing to work around.
    """

    def __init__(
        self,
        client: RemoteConfigClient | None = None,
        config: RemoteConfigSettings | None = None,
    ) -> None:
        self._config = config if config is not None else _bootstrap()
        self._client = client

    @property
    def config(self) -> RemoteConfigSettings:
        return self._config

    def _resolve_client(self) -> RemoteConfigClient | None:
        if self._client is not None:
            return self._client
        try:
            from app.core.remote_config_nacos import NacosConfigClient
        except ImportError:
            logger.warning("remote config: nacos client unavailable, using snapshot only")
            return None
        try:
            self._client = NacosConfigClient(self._config)
        except Exception:
            logger.exception("remote config: could not build the client")
            return None
        return self._client

    def _snapshot_path(self, data_id: str) -> Path:
        return self._config.snapshot_dir / f"{data_id}.properties"

    def _write_snapshot(self, data_id: str, text: str) -> None:
        path = self._snapshot_path(data_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError:
            # A snapshot that cannot be written costs the next cold start its
            # remote values; it must not cost this start anything.
            logger.warning("remote config: could not write snapshot for %s", data_id)

    def _read_snapshot(self, data_id: str) -> str | None:
        path = self._snapshot_path(data_id)
        try:
            return path.read_text(encoding="utf-8") if path.is_file() else None
        except OSError:
            return None

    def _document(self, data_id: str) -> str | None:
        """The remote document, or the last one that arrived, or nothing."""

        client = self._resolve_client()
        if client is not None:
            try:
                text = client.fetch(self._config.group, data_id)
            except Exception:
                logger.exception("remote config: fetch failed for %s", data_id)
                text = None
            if text is not None:
                self._write_snapshot(data_id, text)
                return text
        snapshot = self._read_snapshot(data_id)
        if snapshot is not None:
            logger.warning("remote config: using local snapshot for %s", data_id)
        return snapshot

    def all(self) -> dict[str, str]:
        """Every watched document, by data id, skipping the ones with nothing.

        Shared with the poller so change detection sees exactly what a reload
        would load. Comparing against anything else would eventually report a
        change that changes no setting, or miss one that does.
        """

        found: dict[str, str] = {}
        for data_id in self._config.data_ids:
            document = self._document(data_id)
            if document:
                found[data_id] = document
        return found


class RemoteSettingsSource(PydanticBaseSettingsSource):
    """Values from the configuration centre, degrading to a snapshot, then to nothing."""

    def __init__(
        self,
        settings_cls: type,
        client: RemoteConfigClient | None = None,
        config: RemoteConfigSettings | None = None,
    ) -> None:
        super().__init__(settings_cls)
        self._documents = RemoteDocuments(client=client, config=config)

    # `PydanticBaseSettingsSource` declares this abstract; the whole document is
    # read at once in `__call__`, so there is nothing per-field to do here.
    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        config = self._documents.config
        if not config.enabled:
            return {}
        values: dict[str, Any] = {}
        # Later data ids win, so the declared order in NACOS_DATA_IDS is the
        # override order -- the same rule the render step uses for its layers.
        for document in self._documents.all().values():
            values.update(parse_properties(document))
        if values:
            logger.info("remote config: %d values from %s", len(values), config.server_addr or "snapshot")
        return values

    def publish(self, data_id: str, values: dict[str, str]) -> bool:
        """Replace one document with `values`, rendered in the same format.

        The document is rewritten whole rather than patched: the centre keeps
        the version history and the rollback, so a merge here would be a second,
        worse implementation of both. The caller is responsible for having read
        the current values first -- which the admin endpoint does, from this same
        source, so what it writes back is what the page was showing plus the
        edit.
        """

        client = self._resolve_client()
        if client is None:
            raise RuntimeError("no configuration centre client available")
        body = "".join(f"{key}={values[key]}\n" for key in sorted(values))
        return bool(client.publish(self._config.group, data_id, body))


def _digest(documents: dict[str, str]) -> str:
    """A stable fingerprint of every watched document."""

    hasher = hashlib.sha256()
    for data_id in sorted(documents):
        hasher.update(data_id.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(documents[data_id].encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def watch_remote_config(
    callback: Callable[[], None],
    client: RemoteConfigClient | None = None,
    stop: threading.Event | None = None,
    config: RemoteConfigSettings | None = None,
) -> bool:
    """Poll the watched documents; call `callback` when any of them changes.

    **Deliberately polling rather than the SDK's own watcher.**
    `nacos-sdk-python` 1.x does change detection in `_init_pulling`, which builds
    a `multiprocessing.Manager()`, a `multiprocessing.Queue` and a ten-thread
    callback pool. On Windows, where the start method is spawn, registering a
    watcher did not return at all -- verified twice against a stub server, once
    with and once without a `__main__` guard. One HTTP GET per document on a
    daemon thread costs a process and a thread pool less, behaves the same on
    every platform, and reuses the `fetch` path that already degrades to a
    snapshot.

    The cost is latency: an edit in the console takes effect within
    `NACOS_POLL_INTERVAL_MS` (default 30s), the same order as the long poll it
    replaces.

    Returns whether polling began. Wiring `callback` to the reload sequence is
    the caller's job, because this module must not import the API layer.
    """

    config = config if config is not None else _bootstrap()
    if not config.enabled:
        return False
    documents = RemoteDocuments(client=client, config=config)
    stop_event = stop if stop is not None else threading.Event()

    def _poll() -> None:
        # Seeded with what this process already loaded, so an unchanged document
        # does not fire a reload on the first tick.
        try:
            last = _digest(documents.all())
        except Exception:
            logger.exception("remote config: could not seed the poller")
            last = ""
        interval = max(config.poll_interval_ms, 1000) / 1000.0
        while not stop_event.wait(interval):
            try:
                current = _digest(documents.all())
            except Exception:
                logger.exception("remote config: poll failed")
                continue
            if current != last:
                last = current
                logger.info("remote config: change detected")
                callback()

    threading.Thread(target=_poll, name="remote-config-poller", daemon=True).start()
    return True


def remote_config_enabled() -> bool:
    """Whether a configuration centre is configured for this process."""

    return _bootstrap().enabled


def data_ids() -> Iterable[str]:
    return _bootstrap().data_ids
