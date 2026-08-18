"""
Hybrid Clarification System - 混合澄清系统

结合规则配置和LLM推理的优势：
- 常见场景：使用预定义规则（快速、可控）
- 罕见场景：使用LLM动态生成（灵活、智能）
- 信息提取：规则优先，LLM增强
"""

import json
import logging
from typing import Any

from app.core.models import get_chat_model
from app.domain.contracts import ClarificationQuestion

logger = logging.getLogger(__name__)


class HybridClarificationService:
    """混合澄清服务：规则 + LLM"""

    def __init__(self, enable_llm_fallback: bool = True):
        """
        初始化混合澄清服务

        Args:
            enable_llm_fallback: 是否启用LLM fallback（默认True）
        """
        self.enable_llm_fallback = enable_llm_fallback
        self.llm_model = get_chat_model(temperature=0.3) if enable_llm_fallback else None

        # 规则支持的意图（预定义配置）
        self.supported_intents = {
            "rag_design",
            "document_comparison",
            "specific_query",
        }

        logger.info(
            f"HybridClarificationService initialized (LLM fallback: {enable_llm_fallback})"
        )

    async def identify_intent(
        self,
        question: str,
        known_info: dict[str, str],
        use_llm: bool = False,
    ) -> tuple[str, float]:
        """
        识别用户意图（混合策略）

        Args:
            question: 用户问题
            known_info: 已知信息
            use_llm: 强制使用LLM（默认False，先用规则）

        Returns:
            (intent, confidence) 元组
        """
        # 策略1: 规则优先（快速路径）
        if not use_llm:
            intent, confidence = self._rule_based_intent(question)
            if confidence >= 0.8:  # 高置信度，直接返回
                logger.info(f"Rule-based intent: {intent} (confidence: {confidence:.2f})")
                return intent, confidence

        # 策略2: LLM增强（fallback或强制）
        if self.enable_llm_fallback and (use_llm or confidence < 0.8):
            llm_intent, llm_confidence = await self._llm_based_intent(question, known_info)
            logger.info(
                f"LLM-based intent: {llm_intent} (confidence: {llm_confidence:.2f}, "
                f"rule was: {intent})"
            )
            return llm_intent, llm_confidence

        # Fallback: 返回规则结果
        return intent, confidence

    def _rule_based_intent(self, question: str) -> tuple[str, float]:
        """规则判断意图（关键词匹配）"""
        question_lower = question.lower()

        # RAG design - 要求设计词 + RAG上下文
        has_design = any(
            kw in question for kw in ["设计", "搭建", "构建", "实现"]
        ) or any(
            kw in question_lower
            for kw in ["如何做", "怎么做", "how to build", "how to design"]
        )
        has_rag = any(
            kw in question_lower for kw in ["rag", "检索增强", "知识库系统", "retrieval"]
        )

        if has_design and has_rag:
            return "rag_design", 0.9

        # Document comparison
        if any(kw in question for kw in ["比较", "对比", "差异", "对照"]) or any(
            kw in question_lower for kw in ["compare", "difference", "versus", " vs "]
        ):
            return "document_comparison", 0.85

        # Specific query
        if any(kw in question for kw in ["是什么", "有哪些", "什么时候", "多少"]) or any(
            kw in question_lower for kw in ["what is", "when", "where", "how many"]
        ):
            return "specific_query", 0.8

        # General query (低置信度)
        return "general_query", 0.5

    async def _llm_based_intent(
        self, question: str, known_info: dict[str, str]
    ) -> tuple[str, float]:
        """LLM判断意图（智能分类）"""
        if not self.llm_model:
            return "general_query", 0.5

        prompt = f"""分析用户意图并返回JSON格式结果。

用户问题: {question}
已知信息: {json.dumps(known_info, ensure_ascii=False)}

可能的意图类型:
- rag_design: 用户想设计/搭建RAG系统
- document_comparison: 用户想比较文档
- specific_query: 用户查询具体信息
- general_query: 一般性问答
- custom: 以上都不匹配（需要自定义处理）

返回JSON格式:
{{
    "intent": "意图类型",
    "confidence": 0.0-1.0的置信度,
    "reasoning": "判断理由（简短）"
}}

只返回JSON，不要其他内容。"""

        try:
            response = await self.llm_model.ainvoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)

            # 提取JSON
            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                intent = result.get("intent", "general_query")
                confidence = float(result.get("confidence", 0.7))
                reasoning = result.get("reasoning", "")

                logger.debug(f"LLM intent reasoning: {reasoning}")
                return intent, confidence

        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}")

        return "general_query", 0.5

    async def extract_info_from_context(
        self,
        question: str,
        context: str,
        fields: list[str],
        use_llm: bool = False,
    ) -> dict[str, str]:
        """
        从上下文提取信息（混合策略）

        Args:
            question: 当前问题
            context: 上下文（历史对话）
            fields: 需要提取的字段
            use_llm: 是否使用LLM增强

        Returns:
            提取的信息字典
        """
        # 策略1: 规则提取（快速）
        from app.agents.router.enhanced_service import EnhancedRouterService

        service = EnhancedRouterService()
        rule_extracted = service._extract_info_from_history(question, context)

        # 如果规则提取完整，直接返回
        if not use_llm or set(fields).issubset(set(rule_extracted.keys())):
            logger.info(f"Rule-based extraction: {list(rule_extracted.keys())}")
            return rule_extracted

        # 策略2: LLM增强提取
        if self.enable_llm_fallback:
            llm_extracted = await self._llm_extract_info(question, context, fields)
            # 合并结果（规则优先）
            merged = {**llm_extracted, **rule_extracted}
            logger.info(
                f"Hybrid extraction: rule={list(rule_extracted.keys())}, "
                f"llm={list(llm_extracted.keys())}"
            )
            return merged

        return rule_extracted

    async def _llm_extract_info(
        self, question: str, context: str, fields: list[str]
    ) -> dict[str, str]:
        """LLM提取信息（智能NER）"""
        if not self.llm_model:
            return {}

        prompt = f"""从对话中提取指定信息。

当前问题: {question}
对话历史: {context[:500]}...

需要提取的字段: {', '.join(fields)}

字段说明:
- scenario: 使用场景（企业知识库/客服问答/代码知识库/数据分析）
- data_source: 数据来源（PDF文档/数据库/API接口/网页爬取）
- scale: 数据规模（小型/中型/大型/超大型）
- performance_requirement: 性能要求（实时/快速/一般/可接受）

返回JSON格式（只包含能确定的字段）:
{{
    "field_name": "提取的值"
}}

如果字段无法确定，不要包含在JSON中。只返回JSON，不要其他内容。"""

        try:
            response = await self.llm_model.ainvoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)

            # 提取JSON
            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                extracted = json.loads(json_match.group(0))
                # 只保留请求的字段
                filtered = {k: v for k, v in extracted.items() if k in fields}
                return filtered

        except Exception as e:
            logger.warning(f"LLM info extraction failed: {e}")

        return {}

    async def generate_next_question(
        self,
        intent: str,
        missing_fields: list[str],
        known_info: dict[str, str],
        use_llm: bool = False,
    ) -> ClarificationQuestion | None:
        """
        生成下一个澄清问题（混合策略）

        Args:
            intent: 意图类型
            missing_fields: 缺失的字段
            known_info: 已知信息
            use_llm: 是否使用LLM生成

        Returns:
            澄清问题对象，如果无法生成则返回None
        """
        if not missing_fields:
            return None

        # 策略1: 规则配置（快速路径）
        if not use_llm and intent in self.supported_intents:
            from app.agents.router.enhanced_service import INTENT_REQUIRED_INFO

            config = INTENT_REQUIRED_INFO.get(intent)
            if config:
                # 返回第一个缺失字段的问题
                for field in missing_fields:
                    question = config["questions"].get(field)
                    if question:
                        logger.info(f"Rule-based question for field: {field}")
                        return question

        # 策略2: LLM动态生成（fallback）
        if self.enable_llm_fallback and (use_llm or intent not in self.supported_intents):
            next_field = missing_fields[0]
            llm_question = await self._llm_generate_question(
                intent, next_field, known_info
            )
            if llm_question:
                logger.info(f"LLM-generated question for field: {next_field}")
                return llm_question

        return None

    async def _llm_generate_question(
        self, intent: str, field: str, known_info: dict[str, str]
    ) -> ClarificationQuestion | None:
        """LLM动态生成澄清问题"""
        if not self.llm_model:
            return None

        prompt = f"""生成一个澄清问题。

用户意图: {intent}
需要询问的字段: {field}
已知信息: {json.dumps(known_info, ensure_ascii=False)}

生成一个自然的问题，包含3-5个选项。

返回JSON格式:
{{
    "question": "问题文本",
    "options": ["选项1", "选项2", "选项3", "选项4"],
    "field_name": "{field}"
}}

只返回JSON，不要其他内容。"""

        try:
            response = await self.llm_model.ainvoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)

            # 提取JSON
            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return ClarificationQuestion(
                    question=data["question"],
                    options=data["options"],
                    allow_custom_input=True,
                    field_name=data["field_name"],
                )

        except Exception as e:
            logger.warning(f"LLM question generation failed: {e}")

        return None


# 便捷函数：获取混合服务单例
_hybrid_service_instance = None


def get_hybrid_clarification_service() -> HybridClarificationService:
    """获取混合澄清服务单例"""
    global _hybrid_service_instance
    if _hybrid_service_instance is None:
        _hybrid_service_instance = HybridClarificationService()
    return _hybrid_service_instance
