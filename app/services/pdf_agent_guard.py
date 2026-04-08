from pathlib import Path


def detect_selected_pdfs(question: str, pdf_names: list[str]) -> list[str]:
    text = (question or "").lower()
    selected: list[str] = []
    for name in pdf_names:
        low_name = name.lower()
        stem = Path(name).stem.lower()
        if low_name in text or (stem and stem in text):
            selected.append(name)
    dedup: list[str] = []
    for x in selected:
        if x not in dedup:
            dedup.append(x)
    return dedup


def choose_pdf_targets(question: str, pdf_names: list[str]) -> list[str]:
    if not pdf_names:
        return []
    selected = detect_selected_pdfs(question, pdf_names)
    if selected:
        return selected
    if len(pdf_names) == 1:
        return [pdf_names[0]]
    return []


def build_upload_pdf_hint() -> str:
    return (
        "你当前在使用文档读取智能体，但我还没有可用的 PDF/图片文档。\n"
        "请先上传至少一个 PDF 或图片文件，再继续提问。\n"
        "建议：上传后可直接说“读取 xxx.pdf 或 xxx.png 的关键结论”。"
    )


def build_choose_pdf_hint(pdf_names: list[str]) -> str:
    lines = [f"{i + 1}. {name}" for i, name in enumerate(pdf_names[:20])]
    suffix = "\n".join(lines) if lines else "(暂无可选文档)"
    return (
        "我检测到你在问文档内容，但当前有多个可选文档。\n"
        "请告诉我要读取哪一个或哪几个（可多选）。\n"
        f"可选文档：\n{suffix}\n"
        "示例：读取 1) a.pdf 和 3) c.png 的重点。"
    )


def apply_pdf_focus_to_question(question: str, selected_pdf_names: list[str]) -> str:
    if not selected_pdf_names:
        return question
    joined = ", ".join(selected_pdf_names)
    return f"{question}\n\n[仅聚焦以下文档文件: {joined}]"
