from types import SimpleNamespace

import app.retrievers.reranker as reranker
from app.services.evidence_scoring import evidence_is_sufficient
from app.services.explainability import build_explainability_report
from app.services.query_rewrite import build_rewrite_queries


def test_query_rewrite_generates_multiple_variants():
    variants = build_rewrite_queries("Alpha Beta Gamma", enable_llm=False)
    assert variants
    assert len(variants) >= 2


def test_query_rewrite_decomposes_compound_question():
    variants = build_rewrite_queries("分析A风险，并且给出B的缓解建议；再比较C和D", enable_llm=False, enable_decompose=True)
    assert any("分析a风险" in v.lower() for v in variants)
    assert any("缓解建议" in v for v in variants)


def test_reranker_uses_lexical_fallback_when_disabled(monkeypatch):
    monkeypatch.setattr(
        reranker,
        "get_settings",
        lambda: SimpleNamespace(enable_reranker=False, reranker_top_n=3),
    )
    candidates = [
        {"id": "a", "text": "completely unrelated sentence", "hybrid_score": 0.9},
        {"id": "b", "text": "beta gamma details", "hybrid_score": 0.1},
    ]
    out = reranker.rerank("beta gamma", candidates, top_n=2)
    assert [x["id"] for x in out] == ["b", "a"]
    assert "rerank_score" in out[0]


def test_combined_evidence_can_be_sufficient_for_hybrid():
    ok = evidence_is_sufficient(
        {"retrieved_count": 2, "effective_hit_count": 2},
        {"entities": ["e1", "e2", "e3"], "neighbors": [{"x": 1}] * 8},
        route="hybrid",
        min_hits=3,
    )
    assert ok is True


def test_combined_evidence_can_be_insufficient_for_hybrid():
    ok = evidence_is_sufficient(
        {"retrieved_count": 1, "effective_hit_count": 1},
        {"entities": [], "neighbors": []},
        route="hybrid",
        min_hits=3,
    )
    assert ok is False


def test_explainability_report_contains_core_fields():
    report = build_explainability_report(
        {
            "route": "vector",
            "reason": "test",
            "vector_result": {"retrieved_count": 2, "effective_hit_count": 1, "retrieval_diagnostics": {"rewrites": ["q"]}},
            "graph_result": {"entities": [], "neighbors": []},
            "web_result": {"used": False},
            "grounding": {"support_ratio": 0.8},
        }
    )
    assert report["route"] == "vector"
    assert "vector_score" in report
    assert report["decision_summary"] == "local_evidence_sufficient_no_web"
