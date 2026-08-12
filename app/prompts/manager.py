"""
提示词管理器 (Prompt Manager)

统一管理所有提示词的中心类，提供：
1. 获取原始提示词模板
2. 格式化用户提示词
3. 便捷的访问接口
"""

import logging

from .skills.ai_knowledge_prompts import (
    AI_KNOWLEDGE_ASSISTANT_SYSTEM_PROMPT,
    AI_KNOWLEDGE_ASSISTANT_USER_PROMPT_TEMPLATE,
)
from .skills.comparison_timeline_prompts import (
    COMPARE_ENTITIES_SYSTEM_PROMPT,
    COMPARE_ENTITIES_USER_PROMPT_TEMPLATE,
    TIMELINE_BUILDER_SYSTEM_PROMPT,
    TIMELINE_BUILDER_USER_PROMPT_TEMPLATE,
)

# 专业技能提示词
from .skills.cybersecurity_skills_prompts import (
    CYBER_ATTACK_ANALYSIS_SYSTEM_PROMPT,
    CYBER_ATTACK_ANALYSIS_USER_PROMPT_TEMPLATE,
    CYBER_DEFENSE_HARDENING_SYSTEM_PROMPT,
    CYBER_DEFENSE_HARDENING_USER_PROMPT_TEMPLATE,
    INCIDENT_RESPONSE_PLAYBOOK_SYSTEM_PROMPT,
    INCIDENT_RESPONSE_PLAYBOOK_USER_PROMPT_TEMPLATE,
)
from .core.intent_prompts import (
    INTENT_CLASSIFICATION_SYSTEM_PROMPT,
    INTENT_CLASSIFICATION_USER_PROMPT_TEMPLATE,
)
from .skills.pdf_web_prompts import (
    PDF_TEXT_READER_SYSTEM_PROMPT,
    PDF_TEXT_READER_USER_PROMPT_TEMPLATE,
    WEB_FACT_CHECK_SYSTEM_PROMPT,
    WEB_FACT_CHECK_USER_PROMPT_TEMPLATE,
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
)
from .core.react_prompts import REACT_SYSTEM_PROMPT, REACT_USER_PROMPT_TEMPLATE
from .core.review_prompts import REVIEW_SYSTEM_PROMPT, REVIEW_USER_PROMPT_TEMPLATE
from .core.router_prompts import ROUTER_SYSTEM_PROMPT, ROUTER_USER_PROMPT_TEMPLATE
from .retrieval.self_rag_prompts import (
    SELF_RAG_ANSWER_QUALITY_PROMPT,
    SELF_RAG_RETRIEVAL_PROMPT,
)
from .core.synthesis_prompts import SYNTHESIS_SYSTEM_PROMPT, SYNTHESIS_USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class PromptManager:
    """
    统一管理所有提示词的中心类

    功能：
    - 获取各模块的系统提示词和用户模板
    - 格式化用户提示词（填充变量）
    - 提供便捷的访问接口
    """

    def __init__(self):
        """初始化提示词管理器"""
        self.prompts = {
            # 核心模块
            "router": {
                "system": ROUTER_SYSTEM_PROMPT,
                "user_template": ROUTER_USER_PROMPT_TEMPLATE,
            },
            "intent": {
                "system": INTENT_CLASSIFICATION_SYSTEM_PROMPT,
                "user_template": INTENT_CLASSIFICATION_USER_PROMPT_TEMPLATE,
            },
            "synthesis": {
                "system": SYNTHESIS_SYSTEM_PROMPT,
                "user_template": SYNTHESIS_USER_PROMPT_TEMPLATE,
            },
            "review": {
                "system": REVIEW_SYSTEM_PROMPT,
                "user_template": REVIEW_USER_PROMPT_TEMPLATE,
            },
            "react": {
                "system": REACT_SYSTEM_PROMPT,
                "user_template": REACT_USER_PROMPT_TEMPLATE,
            },
            "self_rag": {
                "retrieval": SELF_RAG_RETRIEVAL_PROMPT,
                "answer_quality": SELF_RAG_ANSWER_QUALITY_PROMPT,
            },
            # 专业技能 - 网络安全
            "cyber_attack_analysis": {
                "system": CYBER_ATTACK_ANALYSIS_SYSTEM_PROMPT,
                "user_template": CYBER_ATTACK_ANALYSIS_USER_PROMPT_TEMPLATE,
            },
            "cyber_defense_hardening": {
                "system": CYBER_DEFENSE_HARDENING_SYSTEM_PROMPT,
                "user_template": CYBER_DEFENSE_HARDENING_USER_PROMPT_TEMPLATE,
            },
            "incident_response_playbook": {
                "system": INCIDENT_RESPONSE_PLAYBOOK_SYSTEM_PROMPT,
                "user_template": INCIDENT_RESPONSE_PLAYBOOK_USER_PROMPT_TEMPLATE,
            },
            # 专业技能 - 分析工具
            "compare_entities": {
                "system": COMPARE_ENTITIES_SYSTEM_PROMPT,
                "user_template": COMPARE_ENTITIES_USER_PROMPT_TEMPLATE,
            },
            "timeline_builder": {
                "system": TIMELINE_BUILDER_SYSTEM_PROMPT,
                "user_template": TIMELINE_BUILDER_USER_PROMPT_TEMPLATE,
            },
            # 专业技能 - 领域知识
            "ai_knowledge_assistant": {
                "system": AI_KNOWLEDGE_ASSISTANT_SYSTEM_PROMPT,
                "user_template": AI_KNOWLEDGE_ASSISTANT_USER_PROMPT_TEMPLATE,
            },
            "pdf_text_reader": {
                "system": PDF_TEXT_READER_SYSTEM_PROMPT,
                "user_template": PDF_TEXT_READER_USER_PROMPT_TEMPLATE,
            },
            "web_fact_check": {
                "system": WEB_FACT_CHECK_SYSTEM_PROMPT,
                "user_template": WEB_FACT_CHECK_USER_PROMPT_TEMPLATE,
            },
            # 专业技能 - RAG快速检索
            "quick_answer": {
                "system": QUICK_ANSWER_SYSTEM_PROMPT,
                "user_template": QUICK_ANSWER_USER_PROMPT_TEMPLATE,
            },
            "document_search": {
                "system": DOCUMENT_SEARCH_SYSTEM_PROMPT,
                "user_template": DOCUMENT_SEARCH_USER_PROMPT_TEMPLATE,
            },
            "information_extraction": {
                "system": INFORMATION_EXTRACTION_SYSTEM_PROMPT,
                "user_template": INFORMATION_EXTRACTION_USER_PROMPT_TEMPLATE,
            },
            "context_summary": {
                "system": CONTEXT_SUMMARY_SYSTEM_PROMPT,
                "user_template": CONTEXT_SUMMARY_USER_PROMPT_TEMPLATE,
            },
            "keyword_search": {
                "system": KEYWORD_SEARCH_SYSTEM_PROMPT,
                "user_template": KEYWORD_SEARCH_USER_PROMPT_TEMPLATE,
            },
        }
        logger.info("PromptManager initialized with %d prompt modules", len(self.prompts))

    # ========================================================================
    # 获取提示词模板
    # ========================================================================

    def get_router_prompts(self) -> tuple[str, str]:
        """获取路由决策提示词（系统提示词 + 用户模板）"""
        return (
            self.prompts["router"]["system"],
            self.prompts["router"]["user_template"],
        )

    def get_intent_prompts(self) -> tuple[str, str]:
        """获取意图分类提示词（系统提示词 + 用户模板）"""
        return (
            self.prompts["intent"]["system"],
            self.prompts["intent"]["user_template"],
        )

    def get_synthesis_prompts(self) -> tuple[str, str]:
        """获取答案合成提示词（系统提示词 + 用户模板）"""
        return (
            self.prompts["synthesis"]["system"],
            self.prompts["synthesis"]["user_template"],
        )

    def get_review_prompts(self) -> tuple[str, str]:
        """获取答案质检提示词（系统提示词 + 用户模板）"""
        return (
            self.prompts["review"]["system"],
            self.prompts["review"]["user_template"],
        )

    def get_react_prompts(self) -> tuple[str, str]:
        """获取ReAct推理提示词（系统提示词 + 用户模板）"""
        return (
            self.prompts["react"]["system"],
            self.prompts["react"]["user_template"],
        )

    def get_self_rag_retrieval_prompt(self) -> str:
        """获取Self-RAG检索评估提示词"""
        return self.prompts["self_rag"]["retrieval"]

    def get_self_rag_answer_quality_prompt(self) -> str:
        """获取Self-RAG答案质量评估提示词"""
        return self.prompts["self_rag"]["answer_quality"]

    # ========================================================================
    # 格式化用户提示词
    # ========================================================================

    def format_router_prompt(
        self,
        question: str,
        previous_agent_class: str = "general",
        language: str = "auto",
    ) -> str:
        """
        格式化路由决策用户提示词

        Args:
            question: 用户问题
            previous_agent_class: 上一次使用的agent类别
            language: 语言（zh/en/auto）

        Returns:
            格式化后的用户提示词
        """
        return self.prompts["router"]["user_template"].format(
            question=question,
            previous_agent_class=previous_agent_class,
            language=language,
        )

    def format_intent_prompt(self, question: str) -> str:
        """
        格式化意图分类用户提示词

        Args:
            question: 用户问题

        Returns:
            格式化后的用户提示词
        """
        return self.prompts["intent"]["user_template"].format(question=question)

    def format_synthesis_prompt(
        self,
        question: str,
        skill_name: str,
        language: str = "zh",
        memory_context: str = "",
        vector_context: str = "",
        graph_context: str = "",
        web_context: str = "",
    ) -> str:
        """
        格式化答案合成用户提示词

        Args:
            question: 用户问题
            skill_name: 使用的技能名称
            language: 语言（zh/en）
            memory_context: 记忆上下文
            vector_context: 向量检索上下文
            graph_context: 图谱上下文
            web_context: 联网上下文

        Returns:
            格式化后的用户提示词
        """
        return self.prompts["synthesis"]["user_template"].format(
            language=language,
            skill_name=skill_name,
            question=question,
            memory_context=memory_context or "无",
            vector_context=vector_context or "无",
            graph_context=graph_context or "无",
            web_context=web_context or "无",
        )

    def format_review_prompt(
        self,
        question: str,
        current_answer: str,
        memory_context: str = "",
        vector_context: str = "",
        graph_context: str = "",
        web_context: str = "",
    ) -> str:
        """
        格式化答案质检用户提示词

        Args:
            question: 用户问题
            current_answer: 当前生成的答案
            memory_context: 记忆上下文
            vector_context: 向量检索上下文
            graph_context: 图谱上下文
            web_context: 联网上下文

        Returns:
            格式化后的用户提示词
        """
        return self.prompts["review"]["user_template"].format(
            question=question,
            current_answer=current_answer,
            memory_context=memory_context or "无",
            vector_context=vector_context or "无",
            graph_context=graph_context or "无",
            web_context=web_context or "无",
        )

    def format_react_prompt(
        self,
        question: str,
        memory_context: str = "",
        history: str = "",
    ) -> str:
        """
        格式化ReAct推理用户提示词

        Args:
            question: 用户问题
            memory_context: 记忆上下文
            history: 历史推理步骤

        Returns:
            格式化后的用户提示词
        """
        return self.prompts["react"]["user_template"].format(
            question=question,
            memory_context=memory_context or "无",
            history=history or "无",
        )

    def format_self_rag_retrieval_prompt(
        self,
        question: str,
        document: str,
    ) -> str:
        """
        格式化Self-RAG检索评估提示词

        Args:
            question: 用户问题
            document: 检索到的文档

        Returns:
            格式化后的提示词
        """
        return self.prompts["self_rag"]["retrieval"].format(
            question=question,
            document=document,
        )

    def format_self_rag_answer_quality_prompt(
        self,
        question: str,
        answer: str,
        documents: str,
    ) -> str:
        """
        格式化Self-RAG答案质量评估提示词

        Args:
            question: 用户问题
            answer: 生成的答案
            documents: 源文档列表

        Returns:
            格式化后的提示词
        """
        return self.prompts["self_rag"]["answer_quality"].format(
            question=question,
            answer=answer,
            documents=documents,
        )


# ============================================================================
# 全局单例
# ============================================================================

_prompt_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """
    获取全局提示词管理器实例（单例模式）

    Returns:
        PromptManager实例
    """
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
        logger.info("Global PromptManager instance created")
    return _prompt_manager

    # ========================================================================
    # 专业技能提示词获取方法
    # ========================================================================

    def get_skill_prompts(self, skill_name: str) -> tuple[str, str]:
        """
        根据技能名称获取对应的提示词

        Args:
            skill_name: 技能名称（如 'cyber_attack_analysis'）

        Returns:
            (系统提示词, 用户模板)
        """
        if skill_name in self.prompts:
            return (
                self.prompts[skill_name]["system"],
                self.prompts[skill_name]["user_template"],
            )
        else:
            # 默认使用synthesis提示词
            logger.warning(f"Skill '{skill_name}' not found, using default synthesis prompt")
            return self.get_synthesis_prompts()

    def format_skill_prompt(
        self,
        skill_name: str,
        question: str,
        language: str = "zh",
        vector_context: str = "",
        graph_context: str = "",
        web_context: str = "",
    ) -> str:
        """
        格式化技能提示词

        Args:
            skill_name: 技能名称
            question: 用户问题
            language: 语言
            vector_context: 向量上下文
            graph_context: 图谱上下文
            web_context: 网络上下文

        Returns:
            格式化后的用户提示词
        """
        if skill_name not in self.prompts:
            logger.warning(f"Skill '{skill_name}' not found, using synthesis prompt")
            return self.format_synthesis_prompt(
                question=question,
                skill_name=skill_name,
                language=language,
                vector_context=vector_context,
                graph_context=graph_context,
                web_context=web_context,
            )

        template = self.prompts[skill_name]["user_template"]
        return template.format(
            language=language,
            question=question,
            vector_context=vector_context or "无",
            graph_context=graph_context or "无",
            web_context=web_context or "无",
        )
