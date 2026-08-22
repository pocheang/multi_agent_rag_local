"""
Comprehensive tests for Phase 1 user experience improvements.
"""

import pytest
from datetime import datetime
from app.domain.user_experience import (
    ProgressTranslator,
    QualityCardBuilder,
    UserFriendlyError,
    convert_to_user_friendly_error,
    UserFriendlyProgress,
    AnswerQualityCard,
)


class TestProgressTranslator:
    """Test user-friendly progress translation."""

    def test_translate_route_stage(self):
        translator = ProgressTranslator()
        progress = translator.translate("route", "in_progress", "", "zh")

        assert "理解" in progress.user_message
        assert progress.icon == "🎯"
        assert progress.stage == "route"
        assert progress.status == "in_progress"

    def test_translate_rag_stage_with_count(self):
        translator = ProgressTranslator()
        progress = translator.translate(
            "rag", "in_progress", "retrieved 15 evidence items", "zh"
        )

        assert "15" in progress.user_message
        assert "文档" in progress.user_message
        assert progress.icon == "📚"

    def test_progress_percentage_estimation(self):
        translator = ProgressTranslator()

        # Test completed stages
        rag_completed = translator.translate("rag", "completed", "", "zh")
        assert rag_completed.progress_percent == 60

        synthesize_completed = translator.translate("synthesize", "completed", "", "zh")
        assert synthesize_completed.progress_percent == 90

        # Test in-progress stages
        rag_in_progress = translator.translate("rag", "in_progress", "", "zh")
        assert rag_in_progress.progress_percent == 50

    def test_time_estimation(self):
        translator = ProgressTranslator()

        route_progress = translator.translate("route", "in_progress", "", "zh")
        assert route_progress.estimated_seconds == 2

        synthesize_progress = translator.translate("synthesize", "in_progress", "", "zh")
        assert synthesize_progress.estimated_seconds == 6

        # Completed stages should have no time estimate
        completed = translator.translate("rag", "completed", "", "zh")
        assert completed.estimated_seconds is None

    def test_english_translation(self):
        translator = ProgressTranslator()
        progress = translator.translate("route", "in_progress", "", "en")

        assert "Understanding" in progress.user_message
        assert progress.icon == "🎯"

    def test_unknown_stage_fallback(self):
        translator = ProgressTranslator()
        progress = translator.translate("unknown_stage", "in_progress", "", "zh")

        assert progress.stage == "unknown_stage"
        assert progress.icon == "🔍"  # Default icon


class TestQualityCardBuilder:
    """Test answer quality card building."""

    def test_build_high_quality_card(self):
        builder = QualityCardBuilder()
        card = builder.build_from_answer(
            validation_score=0.87,
            evidence_count=8,
            citation_completeness=0.85,
            retrieval_scores=[0.9, 0.85, 0.88],
        )

        assert card.confidence_level == "high"
        assert card.confidence_score == 87.0
        assert card.retrieval_quality == "excellent"
        assert card.completeness == "complete"
        assert card.evidence_count == 8

    def test_build_medium_quality_card(self):
        builder = QualityCardBuilder()
        card = builder.build_from_answer(
            validation_score=0.65,
            evidence_count=3,
            citation_completeness=0.60,
            retrieval_scores=[0.7, 0.65],
        )

        assert card.confidence_level == "medium"
        assert card.confidence_score == 65.0
        assert card.retrieval_quality == "good"
        assert card.completeness == "partial"

    def test_build_low_quality_card(self):
        builder = QualityCardBuilder()
        card = builder.build_from_answer(
            validation_score=0.35,
            evidence_count=1,
            citation_completeness=0.30,
            retrieval_scores=[0.4],
            has_validation_issues=True,
        )

        assert card.confidence_level == "very_low"  # 35 < 40, so very_low
        assert card.confidence_score == 35.0
        assert card.completeness == "incomplete"
        assert len(card.suggestions) > 0
        assert len(card.limitations) > 0

    def test_quality_card_guidance_generation(self):
        builder = QualityCardBuilder()
        card = builder.build_from_answer(
            validation_score=0.40,
            evidence_count=2,
            citation_completeness=0.30,
            has_validation_issues=True,
        )

        # Should have suggestions for low quality
        assert any("建议" in s or "核对" in s for s in card.suggestions)

        # Should have limitations
        assert any("文档" in l for l in card.limitations)

    def test_quality_card_display_chinese(self):
        builder = QualityCardBuilder()
        card = builder.build_from_answer(
            validation_score=0.87,
            evidence_count=5,
            citation_completeness=0.85,
        )

        display = card.to_user_display("zh")

        assert "score" in display
        assert "icon" in display
        assert "🟢" in display["icon"]
        assert "details" in display
        assert "证据来源" in display["details"]

    def test_quality_card_display_english(self):
        builder = QualityCardBuilder()
        card = builder.build_from_answer(
            validation_score=0.87,
            evidence_count=5,
            citation_completeness=0.85,
        )

        display = card.to_user_display("en")

        assert "Evidence sources" in display["details"]
        assert "High confidence" in display["description"]

    def test_quality_card_text_format(self):
        builder = QualityCardBuilder()
        card = builder.build_from_answer(
            validation_score=0.87,
            evidence_count=5,
            citation_completeness=0.85,
        )

        text = card.format_as_text("zh")

        assert "答案可信度" in text
        assert "87/100" in text
        assert "质量详情" in text


class TestUserFriendlyError:
    """Test user-friendly error messages."""

    def test_create_error_message(self):
        error = UserFriendlyError(
            error_type="TestError",
            user_title="测试错误",
            user_message="这是一个测试错误消息",
            severity="error",
            immediate_actions=["操作1", "操作2"],
            technical_details="Technical details here",
        )

        assert error.user_title == "测试错误"
        assert error.severity == "error"
        assert len(error.immediate_actions) == 2

    def test_format_error_display(self):
        error = UserFriendlyError(
            error_type="TestError",
            user_title="测试错误",
            user_message="错误消息",
            severity="error",
            immediate_actions=["尝试重试"],
        )

        display = error.format_for_display("zh", show_technical=False)

        assert "测试错误" in display
        assert "错误消息" in display
        assert "尝试重试" in display
        assert "❌" in display  # Error icon

    def test_format_with_technical_details(self):
        error = UserFriendlyError(
            error_type="TestError",
            user_title="测试错误",
            user_message="错误消息",
            severity="error",
            technical_details="RuntimeError: Something failed",
        )

        display = error.format_for_display("zh", show_technical=True)

        assert "技术详情" in display
        assert "RuntimeError" in display

    def test_convert_runtime_error(self):
        exception = RuntimeError("All retrievers failed")
        user_error = convert_to_user_friendly_error(exception, "zh")

        assert user_error.severity == "error"
        assert user_error.user_title
        assert len(user_error.immediate_actions) > 0

    def test_convert_timeout_error(self):
        exception = TimeoutError("Request timeout")
        user_error = convert_to_user_friendly_error(exception, "zh")

        assert user_error.severity in ("error", "warning")
        assert user_error.user_title
        assert user_error.user_message

    def test_error_severity_icons(self):
        severities = ["info", "warning", "error", "critical"]
        expected_icons = ["ℹ️", "⚠️", "❌", "🚨"]

        for severity, expected_icon in zip(severities, expected_icons):
            error = UserFriendlyError(
                error_type="Test",
                user_title="Test",
                user_message="Test",
                severity=severity,
            )
            display = error.format_for_display("zh")
            assert expected_icon in display


class TestUserFriendlyProgress:
    """Test UserFriendlyProgress model."""

    def test_from_execution_event(self):
        progress = UserFriendlyProgress.from_execution_event(
            stage="route",
            status="in_progress",
            message="",
            language="zh",
        )

        assert progress.stage == "route"
        assert progress.status == "in_progress"
        assert progress.user_message
        assert progress.icon == "🎯"

    def test_progress_model_immutability(self):
        progress = UserFriendlyProgress(
            stage="route",
            status="in_progress",
            user_message="测试消息",
            icon="🎯",
        )

        # Should be frozen (immutable)
        with pytest.raises(Exception):  # Pydantic validation error
            progress.stage = "new_stage"


class TestAnswerQualityCard:
    """Test AnswerQualityCard model."""

    def test_quality_card_immutability(self):
        card = AnswerQualityCard(
            confidence_score=87.0,
            confidence_level="high",
            evidence_count=5,
            retrieval_quality="excellent",
            completeness="complete",
            citation_coverage=0.85,
        )

        # Should be frozen (immutable)
        with pytest.raises(Exception):
            card.confidence_score = 90.0

    def test_quality_card_validation(self):
        # Score should be 0-100
        with pytest.raises(Exception):
            AnswerQualityCard(
                confidence_score=150.0,  # Invalid: > 100
                confidence_level="high",
                evidence_count=5,
                retrieval_quality="excellent",
                completeness="complete",
                citation_coverage=0.85,
            )

    def test_citation_coverage_validation(self):
        # Citation coverage should be 0-1
        with pytest.raises(Exception):
            AnswerQualityCard(
                confidence_score=87.0,
                confidence_level="high",
                evidence_count=5,
                retrieval_quality="excellent",
                completeness="complete",
                citation_coverage=1.5,  # Invalid: > 1
            )


class TestIntegration:
    """Integration tests for user experience components."""

    def test_complete_progress_flow(self):
        """Test complete progress tracking flow."""
        translator = ProgressTranslator()

        stages = [
            ("route", "in_progress"),
            ("route", "completed"),
            ("rag", "in_progress"),
            ("rag", "completed"),
            ("synthesize", "in_progress"),
            ("synthesize", "completed"),
            ("finalize", "in_progress"),
            ("complete", "completed"),
        ]

        progress_events = []
        for stage, status in stages:
            progress = translator.translate(stage, status, "", "zh")
            progress_events.append(progress)

        # Verify progression
        assert len(progress_events) == 8
        assert progress_events[0].progress_percent < progress_events[-1].progress_percent
        assert progress_events[-1].progress_percent == 100

    def test_quality_card_with_real_data(self):
        """Test quality card building with realistic data."""
        builder = QualityCardBuilder()

        # Simulate a real answer scenario
        card = builder.build_from_answer(
            validation_score=0.82,
            evidence_count=6,
            citation_completeness=0.75,
            retrieval_scores=[0.88, 0.85, 0.82, 0.79, 0.76, 0.73],
            has_validation_issues=False,
        )

        # Verify quality card is reasonable
        assert card.confidence_level in ("high", "medium")
        assert card.retrieval_quality in ("excellent", "good")
        assert card.completeness in ("complete", "partial")

        # Display should work
        display = card.to_user_display("zh")
        text = card.format_as_text("zh")

        assert display
        assert text
        assert "可信度" in text

    def test_error_handling_flow(self):
        """Test error conversion and display flow."""
        # Simulate various errors
        errors = [
            RuntimeError("All retrievers failed"),
            ValueError("Invalid input"),
            TimeoutError("Request timeout"),
        ]

        for error in errors:
            user_error = convert_to_user_friendly_error(error, "zh")

            # Verify conversion
            assert user_error.user_title
            assert user_error.user_message
            assert user_error.severity in ("info", "warning", "error", "critical")

            # Verify display
            display = user_error.format_for_display("zh")
            assert display
            assert user_error.user_title in display


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
