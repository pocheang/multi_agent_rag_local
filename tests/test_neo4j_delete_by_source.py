import types
import sys

sys.modules.setdefault("neo4j", types.SimpleNamespace(GraphDatabase=types.SimpleNamespace(driver=lambda *a, **k: None)))
import app.graph.neo4j_client as neo4j_client


class _FakeResult:
    def __init__(self, row=None):
        self._row = row or {}

    def single(self):
        return self._row


class _FakeSession:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, cypher, **params):
        self.calls.append((str(cypher), dict(params)))
        if "RETURN count(r) AS rel_count" in str(cypher):
            return _FakeResult({"rel_count": 2})
        return _FakeResult({})


class _FakeDriver:
    def __init__(self):
        self.calls = []

    def session(self):
        return _FakeSession(self.calls)

    def close(self):
        return None


def test_delete_by_source_deletes_related_edges(monkeypatch):
    fake_driver = _FakeDriver()
    fake_graphdb = types.SimpleNamespace(driver=lambda *args, **kwargs: fake_driver)
    monkeypatch.setattr(neo4j_client, "GraphDatabase", fake_graphdb)
    monkeypatch.setattr(
        neo4j_client,
        "get_settings",
        lambda: types.SimpleNamespace(neo4j_uri="bolt://x", neo4j_username="u", neo4j_password="p"),
    )
    client = neo4j_client.Neo4jClient()
    try:
        removed = client.delete_by_source("s1")
    finally:
        client.close()
    assert removed == 2
    cyphers = [c for c, _p in fake_driver.calls]
    assert any("DELETE r" in c for c in cyphers)
