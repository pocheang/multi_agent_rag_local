import importlib
import sys
import types


def test_web_research_filters_by_allowlist(monkeypatch):
    fake_web_search = types.ModuleType("app.tools.web_search")
    fake_web_search.search_web = lambda _q, max_results=5: []
    monkeypatch.setitem(sys.modules, "app.tools.web_search", fake_web_search)
    web_agent = importlib.import_module("app.agents.web_research_agent")
    web_agent = importlib.reload(web_agent)
    monkeypatch.setattr(
        web_agent,
        "get_settings",
        lambda: type(
            "S",
            (),
            {"web_domain_allowlist": "cisa.gov,mitre.org", "web_min_source_score": 0.5},
        )(),
    )
    monkeypatch.setattr(
        web_agent,
        "search_web",
        lambda _q, max_results=5: [
            {"title": "a", "href": "https://www.cisa.gov/news", "body": "ok"},
            {"title": "b", "href": "https://random.example.com/post", "body": "no"},
        ],
    )
    out = web_agent.run_web_research("latest cve")
    assert out["used"] is True
    assert len(out["citations"]) == 1
    assert "cisa.gov" in out["citations"][0]["source"]
