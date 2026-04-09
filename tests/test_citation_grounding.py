from app.services.citation_grounding import apply_sentence_grounding


def test_grounding_skips_when_no_evidence():
    answer, report = apply_sentence_grounding("这是一个回答。", evidence_texts=[])
    assert answer == "这是一个回答。"
    assert report["enabled"] is False


def test_grounding_rewrites_low_support_sentence():
    answer, report = apply_sentence_grounding(
        "系统依赖GPU。它还能自动修复所有漏洞。",
        evidence_texts=["系统 依赖 GPU 才能运行"],
    )
    assert "基于当前可用证据" in answer
    assert report["enabled"] is True
    assert report["total_sentences"] >= 1
