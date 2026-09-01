#!/usr/bin/env python
"""Drive the real Nacos SDK against a stub server. No container required.

Run this when you touch `app/core/remote_config_nacos.py` or bump the SDK pin:

    conda run -n rag-local python scripts/verify_config_centre.py

`tests/core/test_remote_config_source.py` covers the layer above with a fake
client -- the protocol, the precedence, the degradation. What it cannot cover is
whether this repository's calls match the SDK it is pinned against, because a
fake answers whatever shape it is asked for. That gap is exactly where the three
defects found on 2026-09-01 lived: a pin that resolved to an incompatible major
version, a watcher that never returned on Windows, and an SDK snapshot directory
being written behind this layer's back.

Deliberately a script and not a test. The SDK is an optional extra, so a pytest
version would skip on every CI run and report a pass that verified nothing, and
the suite does not otherwise bind sockets.

Exits non-zero on the first failure.
"""

from __future__ import annotations

import http.server
import os
import socket
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DOCUMENT = {"content": "ENABLE_CALIBRATION=true\nTOP_K=23\nSTRICT_CSP=true\n"}


class _StubNacos(http.server.BaseHTTPRequestHandler):
    """Just enough of `/nacos/v1/cs/configs` for the SDK to be satisfied."""

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's naming
        if urlparse(self.path).path == "/nacos/v1/cs/configs":
            body = DOCUMENT["content"].encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def main() -> int:
    try:
        import nacos  # noqa: F401
    except ImportError:
        print("nacos-sdk-python is not installed: pip install -e .[config-centre]")
        return 1

    port = _free_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _StubNacos)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    snapshot_root = Path(tempfile.mkdtemp(prefix="verify-config-centre-"))
    from app.core import remote_config

    remote_config.SNAPSHOT_ROOT = snapshot_root

    from app.core.config import Settings
    from app.core.remote_config import RemoteConfigSettings, RemoteSettingsSource, watch_remote_config
    from app.core.remote_config_nacos import NacosConfigClient

    config = RemoteConfigSettings(
        enabled=True,
        server_addr=f"127.0.0.1:{port}",
        namespace="",
        group="DEFAULT_GROUP",
        data_ids=("querymind",),
        username="",
        password="",
        timeout_ms=3000,
        poll_interval_ms=1000,
    )
    client = NacosConfigClient(config)

    print("1. the SDK's own get_config, through this adapter")
    raw = client.fetch(config.group, "querymind")
    assert raw == DOCUMENT["content"], raw
    print(f"   {raw!r}\n")

    print("2. values reach Settings, keyed by alias")

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
            return (
                init_settings,
                env_settings,
                RemoteSettingsSource(settings_cls, client=client, config=config),
                dotenv_settings,
                file_secret_settings,
            )

    probe = Probe()
    assert (probe.enable_calibration, probe.top_k, probe.strict_csp) == (True, 23, True)
    print(f"   enable_calibration={probe.enable_calibration} top_k={probe.top_k} strict_csp={probe.strict_csp}\n")

    print("3. one snapshot, ours, and no nacos-data/ from the SDK")
    assert list(snapshot_root.rglob("*.properties")), "no snapshot written"
    assert not Path("nacos-data").exists(), "the SDK wrote its own snapshot directory"
    print(f"   {[str(p.relative_to(snapshot_root)) for p in snapshot_root.rglob('*.properties')]}\n")

    print("4. the poller stays silent until the document changes")
    fired = threading.Event()
    stop = threading.Event()
    assert watch_remote_config(fired.set, client=client, stop=stop, config=config) is True
    assert fired.wait(2.5) is False, "fired without a change"
    print("   quiet for 2.5s")
    DOCUMENT["content"] = "TOP_K=99\n"
    assert fired.wait(5.0) is True, "did not fire on a change"
    print("   fired after the edit\n")
    stop.set()

    print("5. server down, snapshot takes over")
    server.shutdown()
    values = RemoteSettingsSource(Settings, client=client, config=config)()
    assert values.get("TOP_K") == "99", values
    print(f"   {values}\n")

    print("ALL CHECKS PASSED")
    sys.stdout.flush()
    # The SDK leaves worker threads behind; nothing here needs a clean teardown.
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
