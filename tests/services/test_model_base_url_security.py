from types import SimpleNamespace

import pytest

from app.services.security import network


def _settings(**overrides):
    values = {
        "api_base_url_allowlist": "",
        "api_base_url_allow_private": False,
        "api_base_url_dns_check": True,
        "ollama_base_url": "http://localhost:11434",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_ollama_only_allows_the_configured_private_origin_by_default(monkeypatch):
    monkeypatch.setattr(network, "get_settings", lambda: _settings())

    assert (
        network.validate_api_base_url_for_provider(
            "http://localhost:11434", provider="ollama"
        )
        == "http://localhost:11434"
    )

    with pytest.raises(network.OutboundURLValidationError):
        network.validate_api_base_url_for_provider(
            "http://169.254.169.254/latest/meta-data", provider="ollama"
        )


def test_model_base_url_rejects_mixed_public_private_dns(monkeypatch):
    monkeypatch.setattr(network, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        network.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ],
    )

    with pytest.raises(network.OutboundURLValidationError):
        network.validate_api_base_url_for_provider(
            "https://model.example/v1", provider="custom"
        )
