import importlib
import sys
import types


class _FakeClient:
    def search_entities(self, keywords, limit=8, allowed_sources=None):
        return [
            {
                "entity": "AI",
                "relations": [
                    {"relation": "related", "other": "LLM"},
                    {"relation": "depends_on", "other": "GPU"},
                ],
            }
        ]

    def entity_neighbors(self, entity, limit=10, allowed_sources=None):
        return [
            {"entity": "AI", "relation": "related", "other": "LLM"},
            {"entity": "AI", "relation": "depends_on", "other": "GPU"},
            {"entity": "AI", "relation": "depends_on", "other": "GPU"},
        ]

    def entity_paths_2hop(self, entity, limit=8, allowed_sources=None):
        return [
            {"source": "AI", "rel1": "depends_on", "middle": "GPU", "rel2": "targets", "target": "Model"},
            {"source": "AI", "rel1": "related", "middle": "LLM", "rel2": "related", "target": "NLP"},
        ]

    def close(self):
        return None


def test_graph_lookup_normalizes_and_dedupes(monkeypatch):
    fake_neo4j_module = types.ModuleType("app.graph.neo4j_client")
    fake_neo4j_module.Neo4jClient = lambda: _FakeClient()
    monkeypatch.setitem(sys.modules, "app.graph.neo4j_client", fake_neo4j_module)

    graph_tools = importlib.import_module("app.tools.graph_tools")
    graph_tools = importlib.reload(graph_tools)
    out = graph_tools.graph_lookup("AI architecture")
    assert out["entities"][0]["entity"] == "artificial intelligence"
    # noisy relation should be filtered out
    rels = out["entities"][0]["relations"]
    assert all(r["relation"] != "related" for r in rels)
    # dedupe neighbors
    assert len(out["neighbors"]) == 1
    assert len(out["paths"]) == 1
    assert out["graph_signal_score"] > 0
