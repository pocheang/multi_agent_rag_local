"""Enhanced Router service with information completeness checking and proactive clarification.

This service extends the base RouterAgentService with:
1. Dynamic round limits (2-10 rounds based on intent complexity)
2. Information completeness checking
3. Multi-round clarification support
4. Historical context extraction
5. Hybrid mode: Rule-based (fast) + LLM fallback (intelligent)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.agents.router.service import RouterAgentService
from app.domain.contracts import (
    ClarificationContext,
    ClarificationQuestion,
    EnhancedRouteDecision,
    RouteDecision,
    RouterAction,
)
from app.orchestration.request import OrchestrationRequest

# Module-level logger (best practice)
logger = logging.getLogger(__name__)

# Import hybrid service if available
try:
    from app.agents.router.hybrid_clarification import get_hybrid_clarification_service
    from app.agents.router.hybrid_config import (
        USE_HYBRID_CLARIFICATION,
        LLM_FALLBACK_THRESHOLD,
        LLM_ENHANCED_EXTRACTION,
        LLM_DYNAMIC_QUESTIONS,
    )

    HYBRID_MODE_AVAILABLE = True
    logger.info(
        f"Hybrid mode available: {USE_HYBRID_CLARIFICATION} "
        f"(threshold: {LLM_FALLBACK_THRESHOLD})"
    )
except ImportError:
    HYBRID_MODE_AVAILABLE = False
    USE_HYBRID_CLARIFICATION = False
    logger.info("Hybrid mode not available, using rule-based only")


# Intent complexity configuration (determines max clarification rounds)
INTENT_COMPLEXITY = {
    "simple_query": 2,           # Simple queries: max 2 rounds
    "document_lookup": 3,        # Document lookup: max 3 rounds
    "document_comparison": 5,    # Document comparison: max 5 rounds
    "rag_design": 7,             # RAG design: max 7 rounds (complex)
    "system_architecture": 8,    # System architecture: max 8 rounds
    "complex_analysis": 10,      # Complex analysis: max 10 rounds
    "default": 5,                # Default: 5 rounds
}

# Intent required information configuration
INTENT_REQUIRED_INFO: dict[str, dict[str, Any]] = {
    "rag_design": {
        "max_rounds": 7,  # Complex intent, max 7 rounds
        "fields": ["scenario", "data_source", "scale", "performance_requirement"],
        "questions": {
            "scenario": ClarificationQuestion(
                question="这个 RAG 主要用于什么场景？",
                options=["企业知识库", "客服问答", "代码知识库", "数据分析"],
                allow_custom_input=True,
                field_name="scenario",
            ),
            "data_source": ClarificationQuestion(
                question="数据来源是什么类型？",
                options=["PDF文档", "数据库", "API接口", "网页爬取"],
                allow_custom_input=True,
                field_name="data_source",
            ),
            "scale": ClarificationQuestion(
                question="预计的数据规模大概有多大？",
                options=["小型（<1GB）", "中型（1-10GB）", "大型（10-100GB）", "超大型（>100GB）"],
                allow_custom_input=True,
                field_name="scale",
            ),
            "performance_requirement": ClarificationQuestion(
                question="对响应速度有什么要求？",
                options=["实时（<1秒）", "快速（1-3秒）", "一般（3-5秒）", "可接受（>5秒）"],
                allow_custom_input=True,
                field_name="performance_requirement",
            ),
        },
    },
    "document_comparison": {
        "max_rounds": 5,  # Medium complexity, max 5 rounds
        "fields": ["doc_ids", "comparison_aspect", "output_format"],
        "questions": {
            "doc_ids": ClarificationQuestion(
                question="需要比较哪些文档？",
                options=[],  # Dynamically loaded from document store
                allow_custom_input=True,
                field_name="doc_ids",
            ),
            "comparison_aspect": ClarificationQuestion(
                question="比较什么方面？",
                options=["价格", "功能", "性能", "时间"],
                allow_custom_input=True,
                field_name="comparison_aspect",
            ),
            "output_format": ClarificationQuestion(
                question="需要什么样的输出格式？",
                options=["对比表格", "详细报告", "简要总结", "可视化图表"],
                allow_custom_input=True,
                field_name="output_format",
            ),
        },
    },
    "specific_query": {
        "max_rounds": 3,  # Simple query, max 3 rounds
        "fields": ["entity", "attribute"],
        "questions": {
            "entity": ClarificationQuestion(
                question="你想查询哪个实体的信息？",
                options=[],  # Extracted from context
                allow_custom_input=True,
                field_name="entity",
            ),
            "attribute": ClarificationQuestion(
                question="你想了解它的什么属性？",
                options=["价格", "规格", "日期", "数量"],
                allow_custom_input=True,
                field_name="attribute",
            ),
        },
    },
}


class EnhancedRouterService:
    """Enhanced Router service: clarification + classification.

    Supports two modes:
    1. Rule-based mode (default): Fast, predictable, uses INTENT_REQUIRED_INFO
    2. Hybrid mode: Rule-based + LLM fallback for flexibility
    """

    def __init__(self, base_router: RouterAgentService | None = None) -> None:
        self.base_router = base_router or RouterAgentService()

        # Initialize hybrid service if enabled
        self.hybrid_service = None
        if USE_HYBRID_CLARIFICATION and HYBRID_MODE_AVAILABLE:
            self.hybrid_service = get_hybrid_clarification_service()
            logger.info("EnhancedRouter initialized with hybrid mode")
        else:
            logger.info("EnhancedRouter initialized with rule-based mode")

    async def route(
        self,
        request: OrchestrationRequest,
        clarification_context: ClarificationContext | None = None,
    ) -> EnhancedRouteDecision:
        """Execute enhanced route decision.

        Flow:
        1. Check clarification context
        2. Analyze intent
        3. Set dynamic max_rounds based on intent complexity
        4. Check information completeness
        5. Return CONTINUE or NEED_CLARIFICATION

        Args:
            request: Orchestration request
            clarification_context: Current clarification context (from session)

        Returns:
            Enhanced route decision with clarification info
        """
        # Initialize context
        if clarification_context is None:
            clarification_context = ClarificationContext()

        # Build memory context from conversation history
        memory_context = ""
        if request.conversation:
            memory_lines = []
            for turn in request.conversation[-5:]:  # Last 5 turns
                memory_lines.append(f"{turn.role}: {turn.content}")
            memory_context = "\n".join(memory_lines)

        # Extract known information from history (hybrid mode if enabled)
        if self.hybrid_service and LLM_ENHANCED_EXTRACTION:
            # Hybrid extraction: rule + LLM enhancement
            config = INTENT_REQUIRED_INFO.get(intent, {})
            required_fields = config.get("fields", [])
            extracted_info = await self.hybrid_service.extract_info_from_context(
                request.question,
                memory_context,
                required_fields,
                use_llm=True,
            )
        else:
            # Rule-based extraction
            extracted_info = self._extract_info_from_history(
                request.question,
                memory_context,
            )

        # Merge collected and extracted information
        all_known_info = {
            **clarification_context.collected_info,
            **extracted_info,
        }

        logger.info(f"[EnhancedRouter] Question: {request.question[:50]}...")
        logger.info(f"[EnhancedRouter] Collected info: {clarification_context.collected_info}")
        logger.info(f"[EnhancedRouter] Extracted info: {extracted_info}")
        logger.info(f"[EnhancedRouter] All known info: {all_known_info}")
        logger.info(
            f"[EnhancedRouter] Round: {clarification_context.clarification_round}/"
            f"{clarification_context.max_rounds}"
        )

        # Identify intent (hybrid mode if available)
        if self.hybrid_service:
            # Hybrid mode: rule + LLM fallback
            intent, confidence = await self.hybrid_service.identify_intent(
                request.question, all_known_info
            )
            logger.info(f"[EnhancedRouter] Hybrid intent: {intent} (confidence: {confidence:.2f})")
        else:
            # Rule-based mode
            intent = await self._identify_intent(request.question, all_known_info)
            confidence = 0.8  # Default confidence for rule-based
            logger.info(f"[EnhancedRouter] Rule-based intent: {intent}")

        # Dynamically set max_rounds (based on intent complexity)
        if not clarification_context.intent or clarification_context.intent != intent:
            # Intent changed or first time, reset max_rounds
            clarification_context.intent = intent
            clarification_context.max_rounds = self._get_max_rounds_for_intent(intent)
            logger.info(f"[EnhancedRouter] Set max_rounds to {clarification_context.max_rounds} for intent {intent}")

        # Check if max rounds exceeded
        if clarification_context.clarification_round >= clarification_context.max_rounds:
            logger.info("[EnhancedRouter] Max rounds exceeded, forcing CONTINUE")
            # Force continue with available information
            base_decision = await self.base_router.route(request)
            return self._to_enhanced_decision(
                base_decision,
                RouterAction.CONTINUE,
                clarification_context,
            )

        # Check if it's a simple query (no clarification needed)
        is_simple = self._is_simple_query(request.question, intent)
        logger.info(f"[EnhancedRouter] Is simple query: {is_simple}")
        if is_simple:
            base_decision = await self.base_router.route(request)
            return self._to_enhanced_decision(
                base_decision,
                RouterAction.CONTINUE,
                clarification_context,
            )

        # Check information completeness
        missing = self._check_missing_info(intent, all_known_info)
        logger.info(f"[EnhancedRouter] Missing fields: {missing}")

        if not missing:
            logger.info("[EnhancedRouter] All information collected, proceeding with CONTINUE")
            # Information is sufficient, continue execution
            base_decision = await self.base_router.route(request)
            return self._to_enhanced_decision(
                base_decision,
                RouterAction.CONTINUE,
                clarification_context,
            )

        # Information insufficient, select next question (hybrid mode if enabled)
        if self.hybrid_service and LLM_DYNAMIC_QUESTIONS:
            # Hybrid: try rule first, fallback to LLM generation
            next_question = await self.hybrid_service.generate_next_question(
                intent,
                missing,
                all_known_info,
                use_llm=False,  # Try rule first
            )
        else:
            # Rule-based: use predefined questions
            next_question = self._select_next_question(
                intent,
                missing,
                clarification_context.asked_questions,
            )
        logger.info(f"[EnhancedRouter] Next question: {next_question.field_name if next_question else None}")

        if next_question is None:
            logger.info("[EnhancedRouter] No more questions to ask, forcing CONTINUE")
            # No more questions to ask, force continue
            base_decision = await self.base_router.route(request)
            return self._to_enhanced_decision(
                base_decision,
                RouterAction.CONTINUE,
                clarification_context,
            )

        logger.info(f"[EnhancedRouter] Returning NEED_CLARIFICATION for field: {next_question.field_name}")
        # Return NEED_CLARIFICATION - no need to call base_router yet, defer until CONTINUE
        # Create a minimal route decision without LLM call
        from app.domain.contracts import RouteDecision

        # Map custom intent to valid Intent type for placeholder
        intent_mapping = {
            "rag_design": "knowledge_retrieval",
            "document_comparison": "knowledge_retrieval",
            "specific_query": "knowledge_retrieval",
            "general_query": "general_qa",
        }
        valid_intent = intent_mapping.get(intent, "knowledge_retrieval")

        placeholder_decision = RouteDecision(
            intent=valid_intent,
            route=intent,  # Use original intent as route
            confidence=0.5,  # Placeholder confidence
            requires_plan=False,
            allowed_capabilities=frozenset(),
            reason=f"Waiting for clarification on: {', '.join(missing)}",
        )
        return self._to_enhanced_decision(
            placeholder_decision,
            RouterAction.NEED_CLARIFICATION,
            clarification_context,
            missing_information=missing,
            clarification=next_question,
        )

    def _get_max_rounds_for_intent(self, intent: str) -> int:
        """Get max rounds based on intent.

        Priority:
        1. INTENT_REQUIRED_INFO[intent]["max_rounds"]
        2. INTENT_COMPLEXITY[intent]
        3. INTENT_COMPLEXITY["default"] (5)
        """
        config = INTENT_REQUIRED_INFO.get(intent)
        if config and "max_rounds" in config:
            return config["max_rounds"]

        # Fallback to INTENT_COMPLEXITY
        return INTENT_COMPLEXITY.get(intent, INTENT_COMPLEXITY["default"])

    def _extract_info_from_history(
        self,
        current_question: str,
        memory_context: str,
    ) -> dict[str, str]:
        """Extract known information from history messages.

        Uses pattern matching to identify (supports both Chinese and English):
        - Scenario keywords (more precise matching)
        - Data source types
        - Scale indicators
        - Performance requirements
        """
        extracted: dict[str, str] = {}

        # Scenario identification (Chinese + English) - more precise patterns
        # Priority: more specific patterns first to avoid false positives
        text = current_question + " " + memory_context
        text_lower = text.lower()

        # Check for RAG/knowledge base scenario (most specific first)
        if re.search(r"(rag|检索增强|知识库|knowledge\s*base|retrieval)", text_lower):
            if re.search(r"(代码|编程|开发者|技术文档|code|programming|developer|technical\s*doc)", text_lower):
                extracted["scenario"] = "代码知识库"
            elif re.search(r"(企业|公司|组织|内部|enterprise|company|organization|internal|corporate)", text_lower):
                extracted["scenario"] = "企业知识库"
            elif re.search(r"(客服|客户服务|support|customer|helpdesk)", text_lower):
                extracted["scenario"] = "客服问答"
            elif re.search(r"(数据|分析|统计|报表|data|analysis|analytics|report)", text_lower):
                extracted["scenario"] = "数据分析"
        # Fallback to general patterns only if no RAG context
        elif re.search(r"(客服|客户服务|support|customer|helpdesk)", text_lower):
            extracted["scenario"] = "客服问答"
        elif re.search(r"(代码|编程|技术文档|code|programming|technical\s*doc)", text_lower):
            extracted["scenario"] = "代码知识库"

        # Data source identification (Chinese + English)
        if re.search(r"\bpdf\b|\.pdf|文档|document", text_lower):
            extracted["data_source"] = "PDF文档"
        elif re.search(r"数据库|database|\bdb\b|sql|mysql|postgres|oracle", text_lower):
            extracted["data_source"] = "数据库"
        elif re.search(r"\bapi\b|接口|rest|graphql|endpoint", text_lower):
            extracted["data_source"] = "API接口"
        elif re.search(r"网页|爬虫|爬取|web|crawl|scrape|spider", text_lower):
            extracted["data_source"] = "网页爬取"

        # Scale identification (Chinese + English + numeric)
        # First try numeric pattern (e.g., "50GB", "100GB")
        gb_match = re.search(r"(\d+(?:\.\d+)?)\s*gb", text_lower)
        if gb_match:
            gb_value = float(gb_match.group(1))
            if gb_value < 1:
                extracted["scale"] = "小型（<1GB）"
            elif gb_value <= 10:
                extracted["scale"] = "中型（1-10GB）"
            elif gb_value <= 100:
                extracted["scale"] = "大型（10-100GB）"
            else:
                extracted["scale"] = "超大型（>100GB）"
        # Fallback to keyword matching
        elif re.search(r"小型|小规模|少量|small|tiny|minimal", text_lower):
            extracted["scale"] = "小型（<1GB）"
        elif re.search(r"中型|中等|适中|medium|moderate", text_lower):
            extracted["scale"] = "中型（1-10GB）"
        elif re.search(r"大型|大规模|海量|large|huge|massive", text_lower):
            extracted["scale"] = "大型（10-100GB）"
        elif re.search(r"超大|超大型|pb级|very\s*large|extremely\s*large|petabyte", text_lower):
            extracted["scale"] = "超大型（>100GB）"

        # Performance requirement identification (Chinese + English)
        if re.search(r"实时|毫秒级|real-?time|millisecond|instant|immediate|<\s*1\s*s", text_lower):
            extracted["performance_requirement"] = "实时（<1秒）"
        elif re.search(r"快速|秒级|fast|quick|rapid|1-3\s*s", text_lower):
            extracted["performance_requirement"] = "快速（1-3秒）"
        elif re.search(r"一般|normal|standard|acceptable|3-5\s*s", text_lower):
            extracted["performance_requirement"] = "一般（3-5秒）"
        elif re.search(r"可接受|慢|slow|relaxed|>\s*5\s*s", text_lower):
            extracted["performance_requirement"] = "可接受（>5秒）"

        return extracted

    async def _identify_intent(self, question: str, known_info: dict[str, str]) -> str:
        """Identify user intent.

        Uses contextual keyword matching and pattern recognition.
        Returns one of the intent types defined in INTENT_REQUIRED_INFO.

        Priority order (more specific to less specific):
        1. RAG design (requires both design words AND RAG context)
        2. Document comparison
        3. Specific query
        4. General query (fallback)
        """
        question_lower = question.lower()

        # RAG design intent (requires BOTH conditions to avoid false positives)
        # Design words: 设计, 搭建, 构建, 实现, 如何做, 怎么做
        has_design = any(
            keyword in question for keyword in ["设计", "搭建", "构建", "实现"]
        ) or any(
            keyword in question_lower
            for keyword in ["如何做", "怎么做", "how to build", "how to design", "how to implement"]
        )

        # RAG context: must explicitly mention RAG or knowledge base in context
        has_rag = any(
            keyword in question_lower
            for keyword in ["rag", "检索增强", "知识库系统", "knowledge base system"]
        )

        if has_design and has_rag:
            return "rag_design"

        # Document comparison intent
        if any(keyword in question for keyword in ["比较", "对比", "差异", "对照"]) or \
           any(keyword in question_lower for keyword in ["compare", "difference", "versus", " vs "]):
            return "document_comparison"

        # Specific query intent (has specific question words)
        if any(keyword in question for keyword in ["是什么", "有哪些", "什么时候", "多少", "哪里", "谁"]) or \
           any(keyword in question_lower for keyword in ["what is", "when", "where", "who", "how many", "which"]):
            return "specific_query"

        # Default to general query
        return "general_query"

    def _is_simple_query(self, question: str, intent: str) -> bool:
        """Determine if it's a simple question (no clarification needed).

        Logic:
        1. General queries always skip clarification
        2. Complex intents (rag_design, document_comparison, etc.) check for completeness:
           - If question contains sufficient specific details → simple
           - Otherwise → needs clarification
        3. Other intents check information density:
           - Has specific entities, numbers, dates, or multiple details → simple
           - Otherwise → may need clarification

        Note: Length is NOT a primary indicator - a long vague question still needs clarification.
        """
        # General query doesn't need clarification
        if intent == "general_query":
            return True

        # For complex intents, check if question already contains detailed specifications
        complex_intents = {"rag_design", "document_comparison", "system_architecture", "complex_analysis"}
        if intent in complex_intents:
            # Check for specific detailed indicators
            has_specific_details = (
                # Has specific scale/size mention
                re.search(r"\d+\s*(gb|GB|G|g|mb|MB|M|m|条|万|千)", question)
                or
                # Has specific document/file references
                re.search(r"(文档|document|文件|file).*[A-Za-z0-9_\-]{3,}", question)
                or
                # Has specific technical stack mention
                re.search(
                    r"(使用|采用|基于|use|based\s+on).*(vector|embedding|llm|gpt|claude)",
                    question,
                    re.IGNORECASE,
                )
                or
                # Has multiple requirement clauses (contains conjunctions with requirements)
                (len(re.findall(r"[，,、和及以及并且而且]", question)) >= 3)
            )
            return has_specific_details

        # For other intents (specific_query), check information density
        # Has multiple specific indicators
        info_indicators = sum([
            bool(re.search(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?", question)),  # Date
            bool(re.search(r"\d+\.?\d*\s*[元块美金$¥€]", question)),  # Price/money
            bool(re.search(r"\d+\.?\d*\s*(GB|MB|KB|TB|克|斤|kg|g|米|m|cm)", question)),  # Measurements
            len(re.findall(r"[A-Z][a-z]+|[一-龥]{2,}", question)) >= 3,  # Multiple entities (names/nouns)
            bool(re.search(r"(在|位于|from|in|at)\s*[一-龥A-Z][一-龥a-zA-Z\s]{2,}", question)),  # Location
        ])

        return info_indicators >= 2  # Has at least 2 specific indicators


    def _check_missing_info(self, intent: str, known_info: dict[str, str]) -> list[str]:
        """Check for missing information.

        Compares known_info against required fields for the intent.
        Returns list of missing field names.
        """
        config = INTENT_REQUIRED_INFO.get(intent)
        if config is None:
            return []

        required_fields = config["fields"]
        missing = []

        for field in required_fields:
            if field not in known_info or not known_info[field].strip():
                missing.append(field)

        return missing

    def _select_next_question(
        self,
        intent: str,
        missing_fields: list[str],
        asked_questions: list[str],
    ) -> ClarificationQuestion | None:
        """Select the next question to ask.

        Priority: first missing field that hasn't been asked yet.
        """
        config = INTENT_REQUIRED_INFO.get(intent)
        if config is None:
            return None

        # Select first missing field that hasn't been asked
        for field in missing_fields:
            if field not in asked_questions:
                return config["questions"].get(field)

        return None

    def _to_enhanced_decision(
        self,
        base_decision: RouteDecision,
        action: RouterAction,
        context: ClarificationContext,
        missing_information: list[str] | None = None,
        clarification: ClarificationQuestion | None = None,
    ) -> EnhancedRouteDecision:
        """Convert base RouteDecision to EnhancedRouteDecision."""
        return EnhancedRouteDecision(
            intent=base_decision.intent,
            route=base_decision.route,
            confidence=base_decision.confidence,
            requires_plan=base_decision.requires_plan,
            allowed_capabilities=base_decision.allowed_capabilities,
            reason=base_decision.reason,
            action=action,
            missing_information=tuple(missing_information or []),
            clarification=clarification,
            context=context,
        )
