"""
企业级多智能体RAG系统 - 专业提示词库 v2.1

提示词按功能模块分类组织：
- router_prompts.py - 路由决策提示词
- intent_prompts.py - 意图分类提示词
- synthesis_prompts.py - 答案合成提示词
- review_prompts.py - 答案质检提示词
- react_prompts.py - ReAct推理提示词
- self_rag_prompts.py - Self-RAG评估提示词

专业技能提示词：
- cybersecurity_skills_prompts.py - 网络安全技能（攻击分析、防御加固、应急响应）
- comparison_timeline_prompts.py - 对比分析和时间线构建
- ai_knowledge_prompts.py - AI/ML知识助手
- pdf_web_prompts.py - PDF阅读和Web事实核查

- manager.py - 统一管理器

设计原则：
1. 专业性：准确的技术术语和领域知识
2. 完整性：覆盖所有业务场景和边界情况
3. 可维护性：模块化设计，职责单一
4. 性能优化：平衡准确性和推理速度
5. 多语言支持：中英文双语适配
"""

# 核心模块提示词
from .core.canonical_agent_prompts import (
    ANSWER_PROMPT as CANONICAL_ANSWER_PROMPT,
)
from .core.canonical_agent_prompts import (
    QUERY_DECOMPOSITION_PROMPT,
    build_router_prompt,
)
from .core.canonical_agent_prompts import (
    REACT_SYSTEM_PROMPT as CANONICAL_REACT_SYSTEM_PROMPT,
)
from .core.canonical_agent_prompts import (
    REVIEW_PROMPT as CANONICAL_REVIEW_PROMPT,
)
from .core.canonical_agent_prompts import (
    ROUTER_PROMPT_TEMPLATE as CANONICAL_ROUTER_PROMPT_TEMPLATE,
)
from .core.intent_prompts import (
    INTENT_CLASSIFICATION_SYSTEM_PROMPT,
    INTENT_CLASSIFICATION_USER_PROMPT_TEMPLATE,
)
from .core.react_prompts import (
    REACT_SYSTEM_PROMPT,
    REACT_USER_PROMPT_TEMPLATE,
)
from .core.review_prompts import (
    REVIEW_SYSTEM_PROMPT,
    REVIEW_USER_PROMPT_TEMPLATE,
)
from .core.router_prompts import (
    ROUTER_SYSTEM_PROMPT,
    ROUTER_USER_PROMPT_TEMPLATE,
)
from .core.synthesis_prompts import (
    SYNTHESIS_SYSTEM_PROMPT,
    SYNTHESIS_USER_PROMPT_TEMPLATE,
)
from .manager import (
    PromptManager,
    get_prompt_manager,
)
from .retrieval.rag_quick_retrieval_prompts import (
    CONTEXT_SUMMARY_SYSTEM_PROMPT,
    CONTEXT_SUMMARY_USER_PROMPT_TEMPLATE,
    DOCUMENT_SEARCH_SYSTEM_PROMPT,
    DOCUMENT_SEARCH_USER_PROMPT_TEMPLATE,
    INFORMATION_EXTRACTION_SYSTEM_PROMPT,
    INFORMATION_EXTRACTION_USER_PROMPT_TEMPLATE,
    KEYWORD_SEARCH_SYSTEM_PROMPT,
    KEYWORD_SEARCH_USER_PROMPT_TEMPLATE,
    QUICK_ANSWER_SYSTEM_PROMPT,
    QUICK_ANSWER_USER_PROMPT_TEMPLATE,
    get_context_summary_prompts,
    get_document_search_prompts,
    get_information_extraction_prompts,
    get_keyword_search_prompts,
    get_quick_answer_prompts,
)
from .retrieval.self_rag_prompts import (
    SELF_RAG_ANSWER_QUALITY_PROMPT,
    SELF_RAG_RETRIEVAL_PROMPT,
)
from .skills.ai_knowledge_prompts import (
    AI_KNOWLEDGE_ASSISTANT_SYSTEM_PROMPT,
    AI_KNOWLEDGE_ASSISTANT_USER_PROMPT_TEMPLATE,
    get_ai_knowledge_assistant_prompts,
)
from .skills.comparison_timeline_prompts import (
    COMPARE_ENTITIES_SYSTEM_PROMPT,
    COMPARE_ENTITIES_USER_PROMPT_TEMPLATE,
    TIMELINE_BUILDER_SYSTEM_PROMPT,
    TIMELINE_BUILDER_USER_PROMPT_TEMPLATE,
    get_compare_entities_prompts,
    get_timeline_builder_prompts,
)

# 专业技能提示词
from .skills.cybersecurity_skills_prompts import (
    CYBER_ATTACK_ANALYSIS_SYSTEM_PROMPT,
    CYBER_ATTACK_ANALYSIS_USER_PROMPT_TEMPLATE,
    CYBER_DEFENSE_HARDENING_SYSTEM_PROMPT,
    CYBER_DEFENSE_HARDENING_USER_PROMPT_TEMPLATE,
    INCIDENT_RESPONSE_PLAYBOOK_SYSTEM_PROMPT,
    INCIDENT_RESPONSE_PLAYBOOK_USER_PROMPT_TEMPLATE,
    get_cyber_attack_analysis_prompts,
    get_cyber_defense_hardening_prompts,
    get_incident_response_playbook_prompts,
)
from .skills.pdf_web_prompts import (
    PDF_TEXT_READER_SYSTEM_PROMPT,
    PDF_TEXT_READER_USER_PROMPT_TEMPLATE,
    WEB_FACT_CHECK_SYSTEM_PROMPT,
    WEB_FACT_CHECK_USER_PROMPT_TEMPLATE,
    get_pdf_text_reader_prompts,
    get_web_fact_check_prompts,
)


# 便捷访问函数
def get_router_system_prompt() -> str:
    """获取路由器系统提示词"""
    return ROUTER_SYSTEM_PROMPT


def get_synthesis_system_prompt() -> str:
    """获取合成器系统提示词"""
    return SYNTHESIS_SYSTEM_PROMPT


def get_react_system_prompt() -> str:
    """获取ReAct系统提示词"""
    return REACT_SYSTEM_PROMPT


def get_intent_system_prompt() -> str:
    """获取意图分类系统提示词"""
    return INTENT_CLASSIFICATION_SYSTEM_PROMPT


def get_review_system_prompt() -> str:
    """获取质检系统提示词"""
    return REVIEW_SYSTEM_PROMPT


__all__ = [
    "CANONICAL_ANSWER_PROMPT",
    "CANONICAL_REACT_SYSTEM_PROMPT",
    "CANONICAL_REVIEW_PROMPT",
    "CANONICAL_ROUTER_PROMPT_TEMPLATE",
    "QUERY_DECOMPOSITION_PROMPT",
    "build_router_prompt",
    # 核心模块 - 路由相关
    "ROUTER_SYSTEM_PROMPT",
    "ROUTER_USER_PROMPT_TEMPLATE",
    "get_router_system_prompt",
    # 核心模块 - 意图分类
    "INTENT_CLASSIFICATION_SYSTEM_PROMPT",
    "INTENT_CLASSIFICATION_USER_PROMPT_TEMPLATE",
    "get_intent_system_prompt",
    # 核心模块 - 答案合成
    "SYNTHESIS_SYSTEM_PROMPT",
    "SYNTHESIS_USER_PROMPT_TEMPLATE",
    "get_synthesis_system_prompt",
    # 核心模块 - 答案质检
    "REVIEW_SYSTEM_PROMPT",
    "REVIEW_USER_PROMPT_TEMPLATE",
    "get_review_system_prompt",
    # 核心模块 - ReAct推理
    "REACT_SYSTEM_PROMPT",
    "REACT_USER_PROMPT_TEMPLATE",
    "get_react_system_prompt",
    # 核心模块 - Self-RAG
    "SELF_RAG_RETRIEVAL_PROMPT",
    "SELF_RAG_ANSWER_QUALITY_PROMPT",
    # 专业技能 - 网络安全
    "CYBER_ATTACK_ANALYSIS_SYSTEM_PROMPT",
    "CYBER_ATTACK_ANALYSIS_USER_PROMPT_TEMPLATE",
    "get_cyber_attack_analysis_prompts",
    "CYBER_DEFENSE_HARDENING_SYSTEM_PROMPT",
    "CYBER_DEFENSE_HARDENING_USER_PROMPT_TEMPLATE",
    "get_cyber_defense_hardening_prompts",
    "INCIDENT_RESPONSE_PLAYBOOK_SYSTEM_PROMPT",
    "INCIDENT_RESPONSE_PLAYBOOK_USER_PROMPT_TEMPLATE",
    "get_incident_response_playbook_prompts",
    # 专业技能 - 分析工具
    "COMPARE_ENTITIES_SYSTEM_PROMPT",
    "COMPARE_ENTITIES_USER_PROMPT_TEMPLATE",
    "get_compare_entities_prompts",
    "TIMELINE_BUILDER_SYSTEM_PROMPT",
    "TIMELINE_BUILDER_USER_PROMPT_TEMPLATE",
    "get_timeline_builder_prompts",
    # 专业技能 - 领域知识
    "AI_KNOWLEDGE_ASSISTANT_SYSTEM_PROMPT",
    "AI_KNOWLEDGE_ASSISTANT_USER_PROMPT_TEMPLATE",
    "get_ai_knowledge_assistant_prompts",
    "PDF_TEXT_READER_SYSTEM_PROMPT",
    "PDF_TEXT_READER_USER_PROMPT_TEMPLATE",
    "get_pdf_text_reader_prompts",
    "WEB_FACT_CHECK_SYSTEM_PROMPT",
    "WEB_FACT_CHECK_USER_PROMPT_TEMPLATE",
    "get_web_fact_check_prompts",
    # 专业技能 - RAG快速检索
    "QUICK_ANSWER_SYSTEM_PROMPT",
    "QUICK_ANSWER_USER_PROMPT_TEMPLATE",
    "get_quick_answer_prompts",
    "DOCUMENT_SEARCH_SYSTEM_PROMPT",
    "DOCUMENT_SEARCH_USER_PROMPT_TEMPLATE",
    "get_document_search_prompts",
    "INFORMATION_EXTRACTION_SYSTEM_PROMPT",
    "INFORMATION_EXTRACTION_USER_PROMPT_TEMPLATE",
    "get_information_extraction_prompts",
    "CONTEXT_SUMMARY_SYSTEM_PROMPT",
    "CONTEXT_SUMMARY_USER_PROMPT_TEMPLATE",
    "get_context_summary_prompts",
    "KEYWORD_SEARCH_SYSTEM_PROMPT",
    "KEYWORD_SEARCH_USER_PROMPT_TEMPLATE",
    "get_keyword_search_prompts",
    # 管理器
    "PromptManager",
    "get_prompt_manager",
]
