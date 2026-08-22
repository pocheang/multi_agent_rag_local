"""User-friendly progress tracking and quality feedback models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# User-Friendly Progress Tracking
# ============================================================================

StageStatus = Literal["pending", "in_progress", "completed", "failed", "skipped"]
ProgressIcon = Literal["🎯", "📚", "✍️", "✅", "⚠️", "❌", "🔍", "🛠️"]


class UserFriendlyProgress(BaseModel):
    """User-friendly progress update for real-time feedback."""

    model_config = ConfigDict(frozen=True)

    stage: str = Field(min_length=1)
    status: StageStatus
    user_message: str = Field(min_length=1, description="User-friendly message in their language")
    icon: ProgressIcon | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    estimated_seconds: int | None = Field(default=None, ge=0)
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_execution_event(
        cls,
        stage: str,
        status: str,
        message: str = "",
        language: str = "zh",
    ) -> UserFriendlyProgress:
        """Convert internal execution event to user-friendly progress."""
        translator = ProgressTranslator()
        return translator.translate(stage, status, message, language)


class ProgressTranslator:
    """Translate internal stage names to user-friendly messages."""

    STAGE_TRANSLATIONS = {
        "route": {
            "zh": {"message": "理解您的问题", "icon": "🎯"},
            "en": {"message": "Understanding your question", "icon": "🎯"},
        },
        "plan": {
            "zh": {"message": "规划解答步骤", "icon": "🔍"},
            "en": {"message": "Planning answer steps", "icon": "🔍"},
        },
        "rag": {
            "zh": {"message": "搜索相关文档", "icon": "📚"},
            "en": {"message": "Searching documents", "icon": "📚"},
        },
        "tool": {
            "zh": {"message": "执行工具调用", "icon": "🛠️"},
            "en": {"message": "Executing tools", "icon": "🛠️"},
        },
        "synthesize": {
            "zh": {"message": "生成答案", "icon": "✍️"},
            "en": {"message": "Generating answer", "icon": "✍️"},
        },
        "finalize": {
            "zh": {"message": "质量检查", "icon": "✅"},
            "en": {"message": "Quality check", "icon": "✅"},
        },
        "complete": {
            "zh": {"message": "完成", "icon": "✅"},
            "en": {"message": "Complete", "icon": "✅"},
        },
    }

    def translate(
        self,
        stage: str,
        status: str,
        message: str = "",
        language: str = "zh",
    ) -> UserFriendlyProgress:
        """Translate stage to user-friendly progress."""

        stage_info = self.STAGE_TRANSLATIONS.get(stage, {})
        lang_info = stage_info.get(language, stage_info.get("zh", {}))

        user_message = lang_info.get("message", stage)
        icon = lang_info.get("icon", "🔍")

        # Enhance message with details from internal message
        if message and stage == "rag":
            user_message = self._enhance_rag_message(user_message, message, language)
        elif message and stage == "synthesize":
            user_message = self._enhance_synthesis_message(user_message, message, language)

        # Calculate progress percentage
        progress_percent = self._estimate_progress(stage, status)

        # Estimate remaining time
        estimated_seconds = self._estimate_remaining_time(stage, status)

        return UserFriendlyProgress(
            stage=stage,
            status=status,
            user_message=user_message,
            icon=icon,
            progress_percent=progress_percent,
            estimated_seconds=estimated_seconds,
        )

    def _enhance_rag_message(self, base_message: str, internal_message: str, language: str) -> str:
        """Extract retrieval details and enhance message."""
        import re

        # Extract evidence count if present
        count_match = re.search(r"(\d+)\s+evidence", internal_message, re.IGNORECASE)
        if count_match:
            count = count_match.group(1)
            if language == "zh":
                return f"{base_message} - 已找到 {count} 份相关文档"
            else:
                return f"{base_message} - Found {count} relevant documents"

        # Check for degradation warnings
        if "degraded" in internal_message.lower():
            if language == "zh":
                return f"{base_message} - 部分检索成功"
            else:
                return f"{base_message} - Partial retrieval success"

        return base_message

    def _enhance_synthesis_message(self, base_message: str, internal_message: str, language: str) -> str:
        """Enhance synthesis message with progress info."""
        # For now, just return base message
        # TODO: Extract actual synthesis progress if available
        return base_message

    def _estimate_progress(self, stage: str, status: str) -> int | None:
        """Estimate overall progress percentage based on stage."""

        if status == "completed":
            stage_progress = {
                "route": 15,
                "plan": 25,
                "rag": 60,
                "tool": 75,
                "synthesize": 90,
                "finalize": 95,
                "complete": 100,
            }
            return stage_progress.get(stage, None)

        elif status == "in_progress":
            stage_progress = {
                "route": 10,
                "plan": 20,
                "rag": 50,
                "tool": 70,
                "synthesize": 85,
                "finalize": 93,
            }
            return stage_progress.get(stage, None)

        return None

    def _estimate_remaining_time(self, stage: str, status: str) -> int | None:
        """Estimate remaining time in seconds."""

        if status != "in_progress":
            return None

        # Rough estimates based on typical execution times
        remaining_times = {
            "route": 2,
            "plan": 3,
            "rag": 5,
            "tool": 8,
            "synthesize": 6,
            "finalize": 2,
        }

        return remaining_times.get(stage, None)


# ============================================================================
# Answer Quality Card
# ============================================================================

ConfidenceLevel = Literal["high", "medium", "low", "very_low"]
QualityLevel = Literal["excellent", "good", "fair", "poor"]


class AnswerQualityCard(BaseModel):
    """User-visible answer quality indicators."""

    model_config = ConfigDict(frozen=True)

    # Core metrics
    confidence_score: float = Field(ge=0, le=100, description="0-100 confidence score")
    confidence_level: ConfidenceLevel

    # Evidence quality
    evidence_count: int = Field(ge=0)
    retrieval_quality: QualityLevel

    # Completeness
    completeness: Literal["complete", "partial", "incomplete"]
    citation_coverage: float = Field(ge=0, le=1, description="Percentage of answer with citations")

    # User guidance
    suggestions: tuple[str, ...] = Field(default_factory=tuple)
    limitations: tuple[str, ...] = Field(default_factory=tuple)
    next_questions: tuple[str, ...] = Field(default_factory=tuple)

    # Metadata
    validation_method: str = Field(default="standard")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_user_display(self, language: str = "zh") -> dict[str, Any]:
        """Convert to user-friendly display format."""

        if language == "zh":
            return self._to_chinese_display()
        else:
            return self._to_english_display()

    def _to_chinese_display(self) -> dict[str, Any]:
        """Chinese display format."""

        # Confidence icon and description
        confidence_display = {
            "high": {"icon": "🟢", "desc": "高可信度 - 基于充分的证据和验证"},
            "medium": {"icon": "🟡", "desc": "中等可信度 - 建议与原始资料核对"},
            "low": {"icon": "🔴", "desc": "低可信度 - 强烈建议核实"},
            "very_low": {"icon": "⚫", "desc": "极低可信度 - 请谨慎使用"},
        }

        conf_info = confidence_display[self.confidence_level]

        # Quality level translation
        quality_display = {
            "excellent": "优秀",
            "good": "良好",
            "fair": "一般",
            "poor": "较差",
        }

        completeness_display = {
            "complete": "完整",
            "partial": "部分",
            "incomplete": "可能不完整",
        }

        return {
            "score": f"{self.confidence_score:.0f}/100",
            "icon": conf_info["icon"],
            "description": conf_info["desc"],
            "details": {
                "证据来源": f"{self.evidence_count} 份文档",
                "检索质量": quality_display[self.retrieval_quality],
                "完整性": completeness_display[self.completeness],
                "引用覆盖率": f"{self.citation_coverage * 100:.0f}%",
            },
            "suggestions": list(self.suggestions),
            "limitations": list(self.limitations),
            "next_questions": list(self.next_questions),
        }

    def _to_english_display(self) -> dict[str, Any]:
        """English display format."""

        confidence_display = {
            "high": {"icon": "🟢", "desc": "High confidence - Based on solid evidence"},
            "medium": {"icon": "🟡", "desc": "Medium confidence - Consider verifying"},
            "low": {"icon": "🔴", "desc": "Low confidence - Verification strongly recommended"},
            "very_low": {"icon": "⚫", "desc": "Very low confidence - Use with caution"},
        }

        conf_info = confidence_display[self.confidence_level]

        return {
            "score": f"{self.confidence_score:.0f}/100",
            "icon": conf_info["icon"],
            "description": conf_info["desc"],
            "details": {
                "Evidence sources": f"{self.evidence_count} documents",
                "Retrieval quality": self.retrieval_quality.title(),
                "Completeness": self.completeness.title(),
                "Citation coverage": f"{self.citation_coverage * 100:.0f}%",
            },
            "suggestions": list(self.suggestions),
            "limitations": list(self.limitations),
            "next_questions": list(self.next_questions),
        }

    def format_as_text(self, language: str = "zh") -> str:
        """Format quality card as text for terminal display."""

        display = self.to_user_display(language)

        lines = ["", "─" * 40]
        lines.append(f"{display['icon']} 答案可信度: {display['score']}")
        lines.append(f"💡 {display['description']}")
        lines.append("")

        lines.append("📊 质量详情:")
        for key, value in display["details"].items():
            lines.append(f"  • {key}: {value}")

        if display.get("limitations"):
            lines.append("")
            lines.append("⚠️ 注意事项:")
            for limitation in display["limitations"]:
                lines.append(f"  • {limitation}")

        if display.get("suggestions"):
            lines.append("")
            lines.append("💬 建议:")
            for suggestion in display["suggestions"]:
                lines.append(f"  • {suggestion}")

        if display.get("next_questions"):
            lines.append("")
            lines.append("🔍 您可以进一步询问:")
            for question in display["next_questions"]:
                lines.append(f"  • {question}")

        lines.append("─" * 40)

        return "\n".join(lines)


@dataclass
class QualityCardBuilder:
    """Builder for creating answer quality cards."""

    def build_from_answer(
        self,
        validation_score: float,
        evidence_count: int,
        citation_completeness: float,
        retrieval_scores: list[float] | None = None,
        has_validation_issues: bool = False,
    ) -> AnswerQualityCard:
        """Build quality card from answer validation results."""

        # Calculate confidence score (0-100)
        confidence_score = validation_score * 100

        # Determine confidence level
        if confidence_score >= 80:
            confidence_level = "high"
        elif confidence_score >= 60:
            confidence_level = "medium"
        elif confidence_score >= 40:
            confidence_level = "low"
        else:
            confidence_level = "very_low"

        # Determine retrieval quality
        if retrieval_scores and len(retrieval_scores) > 0:
            avg_retrieval_score = sum(retrieval_scores) / len(retrieval_scores)
            if avg_retrieval_score >= 0.8:
                retrieval_quality = "excellent"
            elif avg_retrieval_score >= 0.6:
                retrieval_quality = "good"
            elif avg_retrieval_score >= 0.4:
                retrieval_quality = "fair"
            else:
                retrieval_quality = "poor"
        else:
            retrieval_quality = "fair"  # Default

        # Determine completeness
        if citation_completeness >= 0.8 and evidence_count >= 3:
            completeness = "complete"
        elif citation_completeness >= 0.5 and evidence_count >= 2:
            completeness = "partial"
        else:
            completeness = "incomplete"

        # Generate suggestions and limitations
        suggestions, limitations = self._generate_guidance(
            confidence_level=confidence_level,
            evidence_count=evidence_count,
            completeness=completeness,
            has_validation_issues=has_validation_issues,
        )

        return AnswerQualityCard(
            confidence_score=round(confidence_score, 1),
            confidence_level=confidence_level,
            evidence_count=evidence_count,
            retrieval_quality=retrieval_quality,
            completeness=completeness,
            citation_coverage=citation_completeness,
            suggestions=tuple(suggestions),
            limitations=tuple(limitations),
        )

    def _generate_guidance(
        self,
        confidence_level: ConfidenceLevel,
        evidence_count: int,
        completeness: Literal["complete", "partial", "incomplete"],
        has_validation_issues: bool,
    ) -> tuple[list[str], list[str]]:
        """Generate user guidance based on quality metrics."""

        suggestions = []
        limitations = []

        # Low confidence suggestions
        if confidence_level in ("low", "very_low"):
            suggestions.append("建议与原始文档核对关键信息")
            suggestions.append("可以尝试将问题拆分成更具体的小问题")

        # Few evidence limitations
        if evidence_count < 3:
            limitations.append(f"仅基于 {evidence_count} 份文档，可能不够全面")
            suggestions.append("如需更全面的答案，可以尝试不同的关键词重新提问")

        # Incomplete coverage
        if completeness != "complete":
            limitations.append("答案可能不完整，建议进一步核实")

        # Validation issues
        if has_validation_issues:
            limitations.append("答案在验证过程中发现潜在问题")
            suggestions.append("强烈建议核实答案中的关键数据和结论")

        return suggestions, limitations


# ============================================================================
# User-Friendly Error Messages
# ============================================================================

ErrorSeverity = Literal["info", "warning", "error", "critical"]


@dataclass
class UserFriendlyError:
    """User-friendly error message with recovery guidance."""

    error_type: str
    user_title: str
    user_message: str
    severity: ErrorSeverity

    # Recovery guidance
    immediate_actions: list[str] = field(default_factory=list)
    technical_details: str | None = None
    contact_support: bool = False

    def format_for_display(self, language: str = "zh", show_technical: bool = False) -> str:
        """Format error for user display."""

        severity_icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨",
        }

        icon = severity_icons[self.severity]

        lines = [
            "",
            f"{icon} {self.user_title}",
            "",
            self.user_message,
        ]

        if self.immediate_actions:
            lines.append("")
            if language == "zh":
                lines.append("您可以尝试:")
            else:
                lines.append("You can try:")

            for action in self.immediate_actions:
                lines.append(f"  ✓ {action}")

        if show_technical and self.technical_details:
            lines.append("")
            if language == "zh":
                lines.append("技术详情:")
            else:
                lines.append("Technical details:")
            lines.append(f"  {self.technical_details}")

        if self.contact_support:
            lines.append("")
            if language == "zh":
                lines.append("💬 如果问题持续，请联系技术支持")
            else:
                lines.append("💬 If the issue persists, please contact support")

        return "\n".join(lines)


# Error mapping for common failures
ERROR_MAPPING = {
    "AllRetrieversFailedError": UserFriendlyError(
        error_type="AllRetrieversFailedError",
        user_title="暂时无法搜索文档",
        user_message="抱歉，我们的文档搜索服务暂时遇到了问题。这可能是由于网络波动或系统正在维护。",
        severity="error",
        immediate_actions=[
            "请稍等 1-2 分钟后重试",
            "尝试简化您的问题后再问",
        ],
        technical_details="All retrieval services (vector, BM25, graph) failed to respond",
        contact_support=False,
    ),
    "NoEvidenceFoundError": UserFriendlyError(
        error_type="NoEvidenceFoundError",
        user_title="未找到相关信息",
        user_message="很抱歉，我在知识库中没有找到与您问题相关的信息。",
        severity="info",
        immediate_actions=[
            "尝试用不同的关键词重新提问",
            "将问题拆分成更具体的小问题",
            "确认问题是否在系统的知识范围内",
        ],
        technical_details=None,
        contact_support=False,
    ),
    "LowQualityAnswerError": UserFriendlyError(
        error_type="LowQualityAnswerError",
        user_title="答案质量不足",
        user_message="我生成的答案未能通过质量检查。为了确保准确性，我建议您重新提问或联系专家获取帮助。",
        severity="warning",
        immediate_actions=[
            "尝试提供更多上下文信息",
            "将复杂问题拆分成多个简单问题",
            "指定您需要的信息类型（如：数据、分析、建议等）",
        ],
        technical_details="Answer validation score below threshold",
        contact_support=False,
    ),
    "TimeoutError": UserFriendlyError(
        error_type="TimeoutError",
        user_title="处理超时",
        user_message="抱歉，您的问题处理时间超过了预期。这可能是因为问题比较复杂。",
        severity="warning",
        immediate_actions=[
            "尝试将问题拆分成更简单的子问题",
            "稍后重试",
        ],
        technical_details="Request exceeded timeout budget",
        contact_support=False,
    ),
}


def convert_to_user_friendly_error(
    exception: Exception,
    language: str = "zh",
) -> UserFriendlyError:
    """Convert internal exception to user-friendly error."""

    error_name = type(exception).__name__

    if error_name in ERROR_MAPPING:
        return ERROR_MAPPING[error_name]

    # Default generic error
    if language == "zh":
        return UserFriendlyError(
            error_type=error_name,
            user_title="处理请求时遇到问题",
            user_message="抱歉，处理您的请求时遇到了意外问题。请稍后重试。",
            severity="error",
            immediate_actions=[
                "请稍后重试",
                "如果问题持续，请联系技术支持",
            ],
            technical_details=str(exception),
            contact_support=True,
        )
    else:
        return UserFriendlyError(
            error_type=error_name,
            user_title="Error Processing Request",
            user_message="Sorry, an unexpected error occurred while processing your request. Please try again later.",
            severity="error",
            immediate_actions=[
                "Please try again later",
                "Contact support if the issue persists",
            ],
            technical_details=str(exception),
            contact_support=True,
        )
