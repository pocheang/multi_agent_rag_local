"""LLM-based intent classification for query routing."""

import json
import logging
import re

from app.services.models.runtime import get_chat_model
from app.services.observability.log_safety import question_ref

logger = logging.getLogger(__name__)

INTENT_CLASSIFICATION_PROMPT = """你是一个智能意图分类器。根据用户问题，判断应该使用哪个专业Agent来回答。

可用的Agent类别及其范围：

1. cybersecurity（网络安全）
   - 安全架构、安全策略、合规管理（Compliance）
   - 漏洞、攻击、防护、威胁情报、入侵检测
   - 身份认证、访问控制、权限管理、加密
   - 安全审计、日志分析、安全监控
   - 防火墙、WAF、IDS/IPS、安全设备
   - 数据安全、隐私保护、GDPR、等保
   - 关键词：security, vulnerability, attack, defense, threat, compliance, audit, encryption, authentication, authorization, firewall, malware, exploit, penetration, intrusion

2. artificial_intelligence（人工智能）
   - AI、机器学习、深度学习、神经网络
   - 模型训练、推理、优化、调参
   - NLP、CV、语音识别、推荐系统
   - Transformer、LLM、GPT、BERT
   - 关键词：AI, machine learning, deep learning, neural network, model, training, inference, algorithm, transformer, LLM, GPT, NLP, computer vision

3. pdf_text（PDF文档）
   - PDF文档阅读、文本提取、文档分析
   - 仅当用户明确提到PDF或要求分析文档时使用
   - 关键词：PDF, 文档, document, 阅读, read

4. general（通用知识）
   - 不属于以上三个类别的其他问题
   - 通用知识、常识问答、其他领域

分类示例：
- "什么是Compliance Layer？" → cybersecurity（合规层是安全架构的一部分）
- "如何实现访问控制？" → cybersecurity
- "解释一下Transformer模型" → artificial_intelligence
- "如何训练神经网络？" → artificial_intelligence
- "分析这个PDF文档" → pdf_text
- "今天天气怎么样？" → general

请严格按照JSON格式输出，不要输出其他内容：
{"agent_class": "类别", "confidence": 0.9, "reason": "理由"}

用户问题：{{question}}"""


def classify_intent_with_llm(question: str) -> dict:
    """Classify a user question with the routing LLM and rule-based fallback."""
    try:
        model = get_chat_model(temperature=0.0)
        prompt = INTENT_CLASSIFICATION_PROMPT.replace("{{question}}", question)
        response = model.invoke([("system", prompt)])
        content = response.content.strip()

        json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            json_str = json_str.replace('"', '"').replace('"', '"').replace(', "\'").replace(', "'")
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as error:
                logger.warning(f"JSON parse error: {error}, content: {json_str}")
                return _fallback_classification(question)

            valid_classes = {"cybersecurity", "artificial_intelligence", "pdf_text", "general"}
            agent_class = result.get("agent_class", "general")
            if agent_class not in valid_classes:
                logger.warning(f"Invalid agent_class '{agent_class}', fallback to 'general'")
                agent_class = "general"

            confidence = float(result.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            return {
                "agent_class": agent_class,
                "confidence": confidence,
                "reason": result.get("reason", "LLM classification"),
                "method": "llm",
            }

        # The response can echo the user's question back, so it gets the same
        # treatment; the length in the ref is what usually identifies the fault.
        logger.warning("Failed to extract JSON from LLM response: %s", question_ref(content))
        return _fallback_classification(question)
    except Exception as error:
        logger.exception(f"LLM intent classification failed: {error}")
        return _fallback_classification(question)


def _fallback_classification(question: str) -> dict:
    """Classify by the established keyword fallback when the LLM path fails."""
    q_lower = question.lower()
    security_keywords = [
        "安全",
        "漏洞",
        "攻击",
        "防护",
        "威胁",
        "入侵",
        "渗透",
        "加密",
        "认证",
        "授权",
        "合规",
        "审计",
        "监控",
        "防火墙",
        "恶意",
        "风险",
        "隐私",
        "权限",
        "访问控制",
        "身份",
        "密码",
        "证书",
        "签名",
        "令牌",
        "会话",
        "策略",
        "日志",
        "告警",
        "security",
        "vulnerability",
        "attack",
        "defense",
        "threat",
        "intrusion",
        "penetration",
        "encryption",
        "authentication",
        "authorization",
        "firewall",
        "malware",
        "exploit",
        "compliance",
        "audit",
        "monitoring",
        "privacy",
        "permission",
        "access control",
        "identity",
        "password",
        "certificate",
        "signature",
        "token",
        "session",
        "policy",
        "log",
        "alert",
        "incident",
        "breach",
        "phishing",
        "ransomware",
        "backdoor",
        "waf",
        "ids",
        "ips",
        "siem",
        "soc",
        "iam",
        "pki",
        "vpn",
        "ssl",
        "tls",
        "oauth",
        "saml",
        "jwt",
        "cors",
        "csrf",
        "xss",
        "sqli",
        "injection",
        "gdpr",
        "hipaa",
        "pci",
        "iso27001",
        "等保",
        "sox",
        "compliance layer",
    ]
    ai_keywords = [
        "人工智能",
        "机器学习",
        "深度学习",
        "神经网络",
        "模型",
        "训练",
        "推理",
        "算法",
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "neural network",
        "model",
        "training",
        "inference",
        "algorithm",
        "transformer",
        "llm",
        "gpt",
        "bert",
        "nlp",
        "computer vision",
        "cv",
        "cnn",
        "rnn",
        "lstm",
        "gan",
        "reinforcement learning",
        "supervised",
        "unsupervised",
        "classification",
        "regression",
    ]
    pdf_keywords = ["pdf", "文档", "document", "阅读", "read", "分析", "analyze"]

    if any(keyword in q_lower for keyword in security_keywords):
        return {
            "agent_class": "cybersecurity",
            "confidence": 0.7,
            "reason": "Matched security keywords (fallback)",
            "method": "fallback",
        }
    if any(keyword in q_lower for keyword in ai_keywords):
        return {
            "agent_class": "artificial_intelligence",
            "confidence": 0.7,
            "reason": "Matched AI keywords (fallback)",
            "method": "fallback",
        }
    if any(keyword in q_lower for keyword in pdf_keywords):
        return {
            "agent_class": "pdf_text",
            "confidence": 0.6,
            "reason": "Matched PDF keywords (fallback)",
            "method": "fallback",
        }
    return {
        "agent_class": "general",
        "confidence": 0.5,
        "reason": "No specific category matched (fallback)",
        "method": "fallback",
    }
