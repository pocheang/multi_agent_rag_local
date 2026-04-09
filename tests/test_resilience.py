import app.services.resilience as resilience


def test_ttl_cache_roundtrip():
    c = resilience.TTLCache(ttl_seconds=60, max_items=4)
    c.set("k", {"v": 1})
    assert c.get("k") == {"v": 1}


def test_circuit_breaker_opens_after_failures(monkeypatch):
    class _Settings:
        circuit_breaker_enabled = True
        circuit_breaker_fail_threshold = 2
        circuit_breaker_cooldown_seconds = 60

    monkeypatch.setattr(resilience, "get_settings", lambda: _Settings())
    resilience._BREAKERS.clear()

    def _boom():
        raise RuntimeError("boom")

    for _ in range(2):
        try:
            resilience.call_with_circuit_breaker("x", _boom)
        except Exception:
            pass

    try:
        resilience.call_with_circuit_breaker("x", lambda: 1)
        assert False, "expected circuit open"
    except resilience.CircuitBreakerOpenError:
        assert True
