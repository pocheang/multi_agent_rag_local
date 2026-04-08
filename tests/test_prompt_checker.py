from app.services.prompt_checker import check_and_enhance_prompt


def test_prompt_checker_adds_structure_when_prompt_is_short():
    out = check_and_enhance_prompt(title="短模板", content="帮我分析", use_reasoning=False)
    assert out["title"]
    assert "补充建议结构" in out["content"]
    assert isinstance(out["issues"], list)
    assert len(out["issues"]) >= 1


def test_prompt_checker_keeps_content_non_empty():
    out = check_and_enhance_prompt(
        title="完整模板",
        content="任务目标：分析告警。\n上下文：来自SOC日志。\n约束：不要输出攻击命令。\n输出格式：先结论后要点。",
        use_reasoning=False,
    )
    assert out["content"].strip()
    assert isinstance(out["suggestions"], list)
