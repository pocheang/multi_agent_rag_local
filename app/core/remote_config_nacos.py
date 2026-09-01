"""The Nacos adapter behind `RemoteConfigClient`.

Kept in its own module so the SDK is imported only when a configuration centre
is actually configured: `RemoteSettingsSource` imports this lazily and treats an
`ImportError` as "no client", which degrades to the local snapshot. An
installation that has not adopted Nacos therefore does not need the dependency
installed at all.

**The dependency is pinned to the 1.x line, and that is a design constraint, not
conservatism.** `nacos-sdk-python` 2.x and 3.x are a rewrite: the package is
imported as `v2.nacos`, not `nacos`, and `get_config` is a coroutine. This layer
is called from `Settings()` construction, which is synchronous and may run
inside an already-running event loop -- `reload_settings()` is reachable from a
request handler. Driving an async client from there means `asyncio.run` (which
raises inside a running loop) or a private loop per call, which is the exact
defect this repository has already fixed twice, in `app/agents/rag/cache.py` and
`app/agents/shared/cache.py`. 1.0.0 is the last release with the synchronous
client, and its signatures were verified against the installed package rather
than taken from documentation.

`scripts/verify_config_centre.py` exercises this module against the real SDK
with a stub server and no container. Run it after any change here, or after
bumping the pin: the unit tests use a fake client, which answers whatever shape
it is asked for and therefore cannot catch these calls drifting from the SDK's.

Only `fetch` lives here. Change detection is polled by
`remote_config.watch_remote_config`, because the SDK's own watcher builds a
`multiprocessing.Manager()` and never returned on Windows -- see that function.

Everything the SDK raises is the caller's to handle -- `RemoteSettingsSource`
catches per call so one unreachable server cannot fail a start.
"""

from __future__ import annotations

from app.core.remote_config import RemoteConfigSettings


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
        # Client-wide, so the fetch `add_config_watcher` performs internally
        # obeys it too. Without this the SDK falls back to its own snapshot
        # directory and creates `nacos-data/` in the working directory -- a
        # second cache with different contents and no log line saying which one
        # answered.
        self._client.set_options(no_snapshot=True)
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
