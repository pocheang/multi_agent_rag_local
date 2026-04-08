from app.services.pdf_agent_guard import choose_pdf_targets


def test_choose_pdf_targets_prefers_exact_selected():
    names = ["a.pdf", "b.pdf"]
    assert choose_pdf_targets("读取 b.pdf", names) == ["b.pdf"]


def test_choose_pdf_targets_single_auto_select():
    names = ["only.pdf"]
    assert choose_pdf_targets("读取这个pdf", names) == ["only.pdf"]
