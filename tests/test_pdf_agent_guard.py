from app.services.pdf_agent_guard import (
    apply_pdf_focus_to_question,
    build_choose_pdf_hint,
    build_upload_pdf_hint,
    choose_pdf_targets,
    detect_selected_pdfs,
)


def test_detect_selected_pdfs_by_filename_and_stem():
    pdfs = ["incident-report.pdf", "q1_summary.pdf", "threat-model.pdf"]
    q = "请读取 incident-report.pdf 和 threat-model 的关键结论"
    selected = detect_selected_pdfs(q, pdfs)
    assert selected == ["incident-report.pdf", "threat-model.pdf"]


def test_detect_selected_pdfs_none():
    pdfs = ["a.pdf", "b.pdf"]
    q = "请帮我总结这些文档"
    assert detect_selected_pdfs(q, pdfs) == []


def test_build_upload_pdf_hint_has_upload_guidance():
    msg = build_upload_pdf_hint()
    assert "上传" in msg
    assert "PDF" in msg
    assert "图片" in msg


def test_build_choose_pdf_hint_lists_candidates():
    msg = build_choose_pdf_hint(["a.pdf", "b.pdf"])
    assert "a.pdf" in msg
    assert "b.pdf" in msg
    assert "哪一个" in msg or "哪几个" in msg


def test_apply_pdf_focus_to_question():
    q = "读取重点"
    focused = apply_pdf_focus_to_question(q, ["a.pdf", "b.pdf"])
    assert "[仅聚焦以下文档文件: a.pdf, b.pdf]" in focused


def test_choose_pdf_targets_auto_pick_when_only_one_pdf():
    chosen = choose_pdf_targets("请帮我总结这个PDF", ["only-one.pdf"])
    assert chosen == ["only-one.pdf"]
