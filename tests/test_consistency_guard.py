from app.services.consistency_guard import should_stabilize, text_similarity


def test_consistency_guard_detects_low_similarity():
    sim = text_similarity("系统依赖GPU运行", "今天下午天气晴朗")
    assert sim < 0.3
    assert should_stabilize("系统依赖GPU运行", "今天下午天气晴朗", threshold=0.55) is True
