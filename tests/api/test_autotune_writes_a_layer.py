"""The replay autotuner may not change configuration behind the layers' back.

It used to assign its patch straight onto the live `Settings` object:

    settings.top_k = int(patch["TOP_K"])

which fails twice over. The change belongs to no configuration layer, so it is
lost at the next `apply_config_reload()` -- including the one the administrator
triggers from the very page that shows the value. And that page's "which layer
did this come from" column, the thing it exists for, had no way to know: the
value came from neither the environment, nor the centre, nor the runtime file,
nor the field default.

The endpoint reported `applied_patch` either way.

So: `recommend_replay_autotune` computes and changes nothing, and applying goes
through `write_config_values` like an administrator's edit -- which also means it
inherits the refusals, including the one for a value the process environment
pins.
"""

from __future__ import annotations

import pytest
from starlette.requests import Request

from app.api.application import config_reload
from app.api.routes.admin import ops as admin_ops
from app.core.config import Settings
from app.services.runtime.runtime_ops import recommend_replay_autotune

ADMIN = {"user_id": "admin-1", "username": "ops-admin", "role": "admin", "permissions": ["admin:ops_manage"]}

SLOW = {"latency_ms": {"p95": 9000.0}, "grounding_support_ratio": {"avg": 0.9}}
UNGROUNDED = {"latency_ms": {"p95": 100.0}, "grounding_support_ratio": {"avg": 0.1}}
HEALTHY = {"latency_ms": {"p95": 100.0}, "grounding_support_ratio": {"avg": 0.9}}


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/admin/ops/autotune",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 0),
            "query_string": b"",
        }
    )


class FakeDocuments:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, str]]] = []

        class _Config:
            data_ids = ("querymind",)
            group = "DEFAULT_GROUP"

        self.config = _Config()

    def all(self) -> dict[str, str]:
        return {"querymind": "TOP_K=4\n"}

    def publish(self, data_id: str, values: dict[str, str]) -> bool:
        self.published.append((data_id, dict(values)))
        return True


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(admin_ops, "_audit", lambda *a, **k: None)
    monkeypatch.setattr(admin_ops, "_require_permission", lambda *a, **k: None)


@pytest.fixture
def _centre(monkeypatch):
    documents = FakeDocuments()
    monkeypatch.setattr(config_reload, "remote_config_enabled", lambda: True)
    monkeypatch.setattr(config_reload, "RemoteDocuments", lambda *a, **k: documents)
    monkeypatch.setattr(config_reload, "apply_config_reload", lambda: None)
    return documents


def _trend(monkeypatch, entry):
    monkeypatch.setattr(admin_ops, "read_replay_trends", lambda **_: [entry], raising=False)
    import app.services.runtime.runtime_ops as runtime_ops

    monkeypatch.setattr(runtime_ops, "read_replay_trends", lambda **_: [entry])


def test_recommending_changes_no_settings(monkeypatch):
    """The property the old implementation could not hold."""

    _trend(monkeypatch, SLOW)
    settings = Settings()
    before = (settings.top_k, settings.max_context_chunks)

    _, patch = recommend_replay_autotune(target_p95=3000, target_grounding=0.65, settings=settings)

    assert patch["TOP_K"] == settings.top_k - 1
    assert (settings.top_k, settings.max_context_chunks) == before


def test_a_healthy_trend_recommends_nothing(monkeypatch):
    _trend(monkeypatch, HEALTHY)

    _, patch = recommend_replay_autotune(target_p95=3000, target_grounding=0.65, settings=Settings())

    assert patch == {}


def test_applying_writes_a_configuration_layer(monkeypatch, _centre):
    """The patch has to land somewhere a reload will read it back."""

    _trend(monkeypatch, UNGROUNDED)
    for alias in ("TOP_K", "RANK_FEATURE_ENABLED", "DYNAMIC_RETRIEVAL_ENABLED"):
        monkeypatch.delenv(alias, raising=False)

    body = admin_ops.admin_ops_autotune({}, _request(), ADMIN)

    assert body["applied"] is True
    assert body["reason"] is None
    _, written = _centre.published[0]
    assert written["RANK_FEATURE_ENABLED"] == "True"
    assert int(written["TOP_K"]) > 4


def test_nothing_is_written_when_the_trend_is_healthy(monkeypatch, _centre):
    _trend(monkeypatch, HEALTHY)

    body = admin_ops.admin_ops_autotune({}, _request(), ADMIN)

    assert body["recommended_patch"] == {}
    assert body["applied"] is False
    assert _centre.published == []


def test_a_refused_write_is_reported_rather_than_claimed(monkeypatch, _centre):
    """A value the environment pins cannot be autotuned either, and says so."""

    _trend(monkeypatch, UNGROUNDED)
    monkeypatch.setenv("TOP_K", "11")

    body = admin_ops.admin_ops_autotune({}, _request(), ADMIN)

    assert body["applied"] is False
    assert "pinned in the process environment" in body["reason"]
    assert _centre.published == []


def test_without_a_configuration_centre_it_recommends_but_does_not_apply(monkeypatch):
    """Better than mutating an object whose change nothing will read back."""

    _trend(monkeypatch, UNGROUNDED)
    monkeypatch.setattr(config_reload, "remote_config_enabled", lambda: False)

    body = admin_ops.admin_ops_autotune({}, _request(), ADMIN)

    assert body["recommended_patch"]
    assert body["applied"] is False
    assert "NACOS_ENABLED" in body["reason"]
