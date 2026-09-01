"""The Nacos adapter behind `RemoteConfigClient`.

Kept in its own module so the SDK is imported only when a configuration centre
is actually configured: `RemoteSettingsSource` imports this lazily and treats an
`ImportError` as "no client", which degrades to the local snapshot. An
installation that has not adopted Nacos therefore does not need the dependency
installed at all.

Everything the SDK raises is the caller's to handle -- `RemoteSettingsSource`
catches per call so one unreachable server cannot fail a start.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.core.remote_config import RemoteConfigSettings

logger = logging.getLogger(__name__)


class NacosConfigClient:
    """`RemoteConfigClient` over `nacos-sdk-python`."""

    def __init__(self, config: RemoteConfigSettings) -> None:
        import nacos  # imported here so the dependency stays optional

        if not config.server_addr:
            raise ValueError("NACOS_SERVER_ADDR is required when NACOS_ENABLED is true")
        self._config = config
        self._client = nacos.NacosClient(
            config.server_addr,
            namespace=config.namespace or None,
            username=config.username or None,
            password=config.password or None,
        )
        # Seconds; the bootstrap is in milliseconds to match STAGE_TIMEOUT_*.
        self._timeout = max(config.timeout_ms, 1) / 1000.0

    def fetch(self, group: str, data_id: str) -> str | None:
        """The current document, or None.

        `no_snapshot=True` because this layer keeps its own snapshot, under
        `.runtime/remote-config/`, written only after a fetch that actually
        succeeded. Letting the SDK silently substitute its own cache here would
        make "the server answered" and "the server did not" indistinguishable,
        and the log line that says which one happened is the thing an operator
        needs when a value does not take effect.
        """

        content = self._client.get_config(data_id, group, timeout=self._timeout, no_snapshot=True)
        return content if isinstance(content, str) else None

    def watch(self, group: str, data_id: str, callback: Callable[[], None]) -> None:
        """Run `callback` on every change to this document."""

        def _on_change(args: object) -> None:
            # The SDK hands over the changed content; this layer re-reads
            # everything through the settings sources instead, so that one
            # changed document and a full reload take the identical path.
            del args
            try:
                callback()
            except Exception:
                logger.exception("remote config: change callback failed for %s", data_id)

        self._client.add_config_watcher(data_id, group, _on_change)
