"""The half of the loop that was missing: writing configuration from the console.

`POST /admin/config/reload` re-read `.runtime/{APP_ENV}.env`, a file no HTTP path
could produce, so from a browser the button did nothing unless somebody had
already edited the file on the host. These endpoints add the write.

What is worth pinning here is not the plumbing but the refusals, because each one
prevents the console from claiming a change it did not make:

- no configuration centre configured -> refuse, rather than write somewhere that
  is not read;
- a value pinned in the process environment -> refuse, because the environment
  outranks the centre and the write would succeed and change nothing;
- an untouched key in the same document -> preserved, because the document is
  rewritten whole.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.application import config_reload
from app.api.routes.admin import config as admin_config
from app.core import remote_config
from app.core.remote_config import RemoteConfigSettings

ADMIN = {"user_id": "admin-1", "username": "ops-admin", "role": "admin", "permissions": ["admin:ops_manage"]}


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/admin/config/values",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 0),
            "query_string": b"",
        }
    )


class FakeDocuments:
    """A configuration centre that records what it was asked to store."""

    def __init__(self, documents: dict[str, str] | None = None, accepts: bool = True) -> None:
        self._documents = documents or {}
        self.accepts = accepts
        self.published: list[tuple[str, dict[str, str]]] = []

        class _Config:
            data_ids = ("querymind-base", "querymind-retrieval")
            group = "DEFAULT_GROUP"

        self.config = _Config()

    def all(self) -> dict[str, str]:
        return dict(self._documents)

    def publish(self, data_id: str, values: dict[str, str]) -> bool:
        self.published.append((data_id, dict(values)))
        return self.accepts


@pytest.fixture(autouse=True)
def _no_audit_writes(monkeypatch):
    """Audit entries go to the auth database; a unit test has no business there."""

    monkeypatch.setattr(admin_config, "_audit", lambda *a, **k: None)
    monkeypatch.setattr(admin_config, "_require_permission", lambda *a, **k: None)


@pytest.fixture
def _centre(monkeypatch):
    documents = FakeDocuments(
        {
            "querymind-base": "TOP_K=7\n",
            "querymind-retrieval": "RERANKER_TOP_N=5\n",
        }
    )
    monkeypatch.setattr(admin_config, "remote_config_enabled", lambda: True)
    monkeypatch.setattr(admin_config, "RemoteDocuments", lambda *a, **k: documents)
    monkeypatch.setattr(config_reload, "remote_config_enabled", lambda: True)
    monkeypatch.setattr(config_reload, "RemoteDocuments", lambda *a, **k: documents)
    monkeypatch.setattr(config_reload, "apply_config_reload", lambda: None)
    return documents


def test_the_schema_lists_the_editable_fields(monkeypatch):
    monkeypatch.setattr(admin_config, "remote_config_enabled", lambda: False)

    body = admin_config.admin_config_schema(_request(), ADMIN)

    assert body["config_centre_enabled"] is False
    aliases = {field["alias"] for field in body["fields"]}
    assert {"TOP_K", "STAGE_TIMEOUT_TOTAL_MS", "STRICT_CSP"} <= aliases
    assert all({"layer", "value", "summary", "group"} <= set(field) for field in body["fields"])


def test_saving_without_a_configuration_centre_is_refused(monkeypatch):
    """Better than writing to a file the console cannot make the process read."""

    monkeypatch.setattr(admin_config, "remote_config_enabled", lambda: False)
    monkeypatch.setattr(config_reload, "remote_config_enabled", lambda: False)
    payload = admin_config.ConfigValues(values={"TOP_K": "9"})

    with pytest.raises(HTTPException) as excinfo:
        admin_config.admin_save_config(payload, _request(), ADMIN)
    assert "NACOS_ENABLED" in str(excinfo.value.detail)


def test_an_empty_change_is_refused(_centre):
    with pytest.raises(HTTPException, match="no values"):
        admin_config.admin_save_config(admin_config.ConfigValues(values={}), _request(), ADMIN)


def test_a_field_that_is_not_editable_is_refused(_centre):
    payload = admin_config.ConfigValues(values={"APP_DB_PATH": "/tmp/anything"})

    with pytest.raises(HTTPException, match="not editable"):
        admin_config.admin_save_config(payload, _request(), ADMIN)
    assert _centre.published == []


def test_a_badly_typed_value_is_refused_before_it_is_written(_centre):
    payload = admin_config.ConfigValues(values={"TOP_K": "fifteen"})

    with pytest.raises(HTTPException, match="TOP_K"):
        admin_config.admin_save_config(payload, _request(), ADMIN)
    assert _centre.published == []


def test_a_value_pinned_in_the_environment_is_refused(monkeypatch, _centre):
    """The write would succeed and change nothing, because the environment wins."""

    monkeypatch.setenv("TOP_K", "11")
    payload = admin_config.ConfigValues(values={"TOP_K": "9"})

    with pytest.raises(HTTPException, match="pinned in the process environment"):
        admin_config.admin_save_config(payload, _request(), ADMIN)
    assert _centre.published == []


def test_saving_rewrites_the_document_whole_and_keeps_untouched_keys(monkeypatch, _centre):
    monkeypatch.delenv("TOP_K", raising=False)
    payload = admin_config.ConfigValues(values={"TOP_K": "9"}, data_id="querymind-retrieval")

    body = admin_config.admin_save_config(payload, _request(), ADMIN)

    assert body["ok"] is True
    assert body["changed"] == ["TOP_K"]
    data_id, written = _centre.published[0]
    assert data_id == "querymind-retrieval"
    assert written["TOP_K"] == "9"
    # The key the administrator did not touch survives the rewrite.
    assert written["RERANKER_TOP_N"] == "5"


def test_an_edited_key_goes_back_to_the_document_that_defines_it(monkeypatch, _centre):
    """Found by clicking Save against a real Nacos.

    Every edit used to go to the last data id, so `RERANKER_TOP_N` -- shown on
    the page as coming from `querymind-retrieval` -- was written into
    `querymind-router` instead. The key then existed in two documents with
    different values, the later one silently winning, and the page and the store
    drifted apart from that moment on.
    """

    monkeypatch.delenv("TOP_K", raising=False)
    payload = admin_config.ConfigValues(values={"TOP_K": "9", "RERANKER_TOP_N": "6"})

    admin_config.admin_save_config(payload, _request(), ADMIN)

    written = dict(_centre.published)
    assert set(written) == {"querymind-base", "querymind-retrieval"}
    assert written["querymind-base"]["TOP_K"] == "9"
    assert written["querymind-retrieval"]["RERANKER_TOP_N"] == "6"
    # And neither document gained the other's key.
    assert "RERANKER_TOP_N" not in written["querymind-base"]
    assert "TOP_K" not in written["querymind-retrieval"]


def test_a_key_no_document_defines_yet_goes_to_the_last_data_id(monkeypatch, _centre):
    """Later ids override earlier ones, so the last one is where a new key belongs."""

    monkeypatch.delenv("TOP_K", raising=False)
    payload = admin_config.ConfigValues(values={"BM25_TOP_K": "9"})

    admin_config.admin_save_config(payload, _request(), ADMIN)

    data_id, written = _centre.published[0]
    assert data_id == "querymind-retrieval"
    assert written["BM25_TOP_K"] == "9"


def test_an_unknown_data_id_is_refused(monkeypatch, _centre):
    monkeypatch.delenv("TOP_K", raising=False)
    payload = admin_config.ConfigValues(values={"TOP_K": "9"}, data_id="somewhere-else")

    with pytest.raises(HTTPException, match="unknown data id"):
        admin_config.admin_save_config(payload, _request(), ADMIN)


def test_a_centre_that_rejects_the_write_is_reported(monkeypatch, _centre):
    """`publish_config` returns a bool; a caller that ignored it would claim a save."""

    monkeypatch.delenv("TOP_K", raising=False)
    _centre.accepts = False
    payload = admin_config.ConfigValues(values={"TOP_K": "9"}, data_id="querymind-retrieval")

    with pytest.raises(HTTPException, match="did not accept"):
        admin_config.admin_save_config(payload, _request(), ADMIN)


def test_a_successful_save_reloads_the_runtime(monkeypatch, _centre):
    """Otherwise the console reports a change the running process has not taken."""

    monkeypatch.delenv("TOP_K", raising=False)
    reloaded: list[bool] = []
    monkeypatch.setattr(config_reload, "apply_config_reload", lambda: reloaded.append(True))
    payload = admin_config.ConfigValues(values={"TOP_K": "9"}, data_id="querymind-retrieval")

    admin_config.admin_save_config(payload, _request(), ADMIN)

    assert reloaded == [True]


def test_the_real_document_store_satisfies_what_the_endpoint_calls(monkeypatch):
    """The gap a fake cannot see.

    Every test above swaps in `FakeDocuments`, which implements whatever the
    endpoint asks for -- so `RemoteDocuments` shipped without a `publish` method
    at all (it had landed on the wrong class after a refactor) and every one of
    them still passed. The save failed the first time a human clicked it.

    This one fakes only the *client*, the actual network boundary, and drives the
    real store through the real endpoint.
    """

    published: list[tuple[str, str, str]] = []

    class FakeClient:
        def fetch(self, group: str, data_id: str) -> str:
            return "TOP_K=7\nRERANKER_TOP_N=5\n"

        def publish(self, group: str, data_id: str, content: str) -> bool:
            published.append((group, data_id, content))
            return True

    config = RemoteConfigSettings(
        enabled=True,
        server_addr="nacos.test:8848",
        namespace="test",
        group="DEFAULT_GROUP",
        data_ids=("querymind",),
        username="",
        password="",
        timeout_ms=3000,
    )
    root = Path(tempfile.mkdtemp(prefix="querymind-endpoint-"))
    monkeypatch.setattr(remote_config, "SNAPSHOT_ROOT", root)
    for module in (admin_config, config_reload):
        monkeypatch.setattr(module, "remote_config_enabled", lambda: True)
        monkeypatch.setattr(
            module,
            "RemoteDocuments",
            lambda *a, **k: remote_config.RemoteDocuments(client=FakeClient(), config=config),
        )
    monkeypatch.setattr(config_reload, "apply_config_reload", lambda: None)
    monkeypatch.delenv("TOP_K", raising=False)

    try:
        body = admin_config.admin_save_config(admin_config.ConfigValues(values={"BM25_TOP_K": "9"}), _request(), ADMIN)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    assert body["ok"] is True
    group, data_id, content = published[0]
    assert (group, data_id) == ("DEFAULT_GROUP", "querymind")
    # Rendered in the same KEY=value form, with the untouched keys preserved.
    assert "BM25_TOP_K=9" in content
    assert "TOP_K=7" in content
    assert "RERANKER_TOP_N=5" in content
