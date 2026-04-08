from app.services.agent_classifier import classify_agent_class, pick_cyber_skill


def test_classify_pdf_text():
    q = "帮我读取这个PDF文字并提取关键内容"
    assert classify_agent_class(q) == "pdf_text"


def test_classify_artificial_intelligence():
    q = "请解释人工智能和机器学习的区别"
    assert classify_agent_class(q) == "artificial_intelligence"


def test_classify_cybersecurity():
    q = "这次漏洞攻击链怎么分析，如何防护"
    assert classify_agent_class(q) == "cybersecurity"


def test_classify_general():
    q = "今天上海天气怎么样"
    assert classify_agent_class(q) == "general"


def test_classify_image_ocr_as_pdf_text():
    q = "请读取这张图片里的文字并做OCR摘要"
    assert classify_agent_class(q) == "pdf_text"


def test_pick_cyber_skill_attack():
    assert pick_cyber_skill("分析横向移动和权限提升") == "cyber_attack_analysis"


def test_pick_cyber_skill_ir():
    assert pick_cyber_skill("给我一个应急处置和隔离流程") == "incident_response_playbook"


def test_pick_cyber_skill_default_defense():
    assert pick_cyber_skill("如何做网络安全防护体系建设") == "cyber_defense_hardening"
