from app.services.adaptive_rag_policy import build_adaptive_plan


def test_adaptive_plan_upgrades_vector_to_hybrid_for_complex_query():
    plan = build_adaptive_plan(
        question="请给我做一次全链路根因分析并给出多阶段时间线",
        initial_route="vector",
        skill="answer_with_citations",
        use_web_fallback=True,
        force_web=False,
    )
    assert plan.level == "complex"
    assert plan.route == "hybrid"
    assert plan.prefer_graph is True
    assert plan.min_vector_hits == 3


def test_adaptive_plan_keeps_simple_vector_with_lower_threshold():
    plan = build_adaptive_plan(
        question="vpn 端口是多少",
        initial_route="vector",
        skill="answer_with_citations",
        use_web_fallback=True,
        force_web=False,
    )
    assert plan.level == "simple"
    assert plan.route == "vector"
    assert plan.min_vector_hits == 1
    assert plan.prefer_web is False


def test_adaptive_plan_does_not_prefer_web_when_toggle_off():
    plan = build_adaptive_plan(
        question="vpn 端口是多少",
        initial_route="vector",
        skill="answer_with_citations",
        use_web_fallback=False,
        force_web=False,
    )
    assert plan.prefer_web is False


def test_adaptive_plan_prefers_web_when_forced():
    plan = build_adaptive_plan(
        question="请上网查最新漏洞",
        initial_route="vector",
        skill="web_fact_check",
        use_web_fallback=True,
        force_web=True,
    )
    assert plan.prefer_web is True
