import re


def classify_agent_class(question: str) -> str:
    text = (question or "").strip().lower()
    if not text:
        return "general"

    pdf_patterns = [
        r"\bpdf\b",
        r"pdf提取",
        r"提取pdf",
        r"读取pdf",
        r"pdf文字",
        r"pdf文本",
        r"ocr",
        r"图片",
        r"图像",
        r"照片",
        r"截图",
        r"\bimage\b",
    ]
    ai_patterns = [
        r"人工智能",
        r"\bai\b",
        r"机器学习",
        r"深度学习",
        r"大模型",
        r"\bllm\b",
        r"神经网络",
        r"rag",
        r"提示词",
        r"prompt",
    ]
    cyber_patterns = [
        r"网络安全",
        r"攻防",
        r"漏洞",
        r"入侵",
        r"攻击",
        r"防护",
        r"加固",
        r"应急",
        r"溯源",
        r"病毒",
        r"木马",
        r"勒索",
        r"cve",
        r"sql注入",
        r"xss",
        r"横向移动",
        r"权限提升",
        r"c2",
        r"mitre",
        r"att&ck",
        r"soc",
        r"siem",
        r"edr",
    ]

    if any(re.search(p, text) for p in pdf_patterns):
        return "pdf_text"
    if any(re.search(p, text) for p in ai_patterns):
        return "artificial_intelligence"
    if any(re.search(p, text) for p in cyber_patterns):
        return "cybersecurity"
    return "general"


def pick_cyber_skill(question: str) -> str:
    text = (question or "").lower()
    if any(k in text for k in ["攻击", "漏洞", "横向移动", "权限提升", "c2", "注入", "exploit"]):
        return "cyber_attack_analysis"
    if any(k in text for k in ["应急", "处置", "隔离", "溯源", "恢复", "playbook"]):
        return "incident_response_playbook"
    return "cyber_defense_hardening"
