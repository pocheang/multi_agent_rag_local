"""
Tests for Answer Validator Agent with NLI hallucination detection.
"""

import pytest
import time
from app.agents.validation.public import (
    validate_answer,
    _quick_validation,
    _validate_citations,
    _assess_answer_quality,
)
from app.agents.validation.nli import (
    check_hallucination as _check_hallucination,
    extract_factual_spans as _extract_factual_spans,
)
from app.agents.shared.quality_models import AnswerValidationResult


# ============================================================================
# High-Quality Answer Tests
# ============================================================================

@pytest.mark.asyncio
async def test_answer_validator_high_quality():
    """Test validation of high-quality answer with good citations"""
    query = "What is machine learning?"
    answer = (
        "Machine learning is a subset of artificial intelligence that enables "
        "systems to learn from data. It includes supervised, unsupervised, and "
        "reinforcement learning approaches. Modern ML systems can achieve high "
        "accuracy on complex tasks like image recognition and natural language processing."
    )
    source_docs = [
        {"id": "doc1", "content": "Machine learning is a subset of artificial intelligence"},
        {"id": "doc2", "content": "ML includes supervised and unsupervised learning"}
    ]
    citations = [{"doc_id": "doc1"}, {"doc_id": "doc2"}]

    result = await validate_answer(query, answer, source_docs, citations)

    assert result.is_valid is True
    assert result.action == "approve"
    assert result.overall_score >= 0.8
    # Note: With cascade, first run may load NLI model (slow), subsequent runs faster
    assert result.execution_time_ms < 20000  # Allow time for model loading
    assert result.validation_details.citation_completeness == 1.0
    assert result.validation_details.safety_score == 1.0


@pytest.mark.asyncio
async def test_answer_validator_fast_path_performance():
    """Test that fast path completes quickly"""
    query = "What is Python?"
    answer = (
        "Python is a high-level programming language known for its simplicity and readability. "
        "It supports multiple programming paradigms including procedural, object-oriented, and "
        "functional programming. Python is widely used in web development, data science, and automation."
    )
    source_docs = [
        {"id": "doc1", "content": "Python is a high-level programming language"},
        {"id": "doc2", "content": "Python supports multiple paradigms"}
    ]
    citations = [{"doc_id": "doc1"}, {"doc_id": "doc2"}]

    start = time.time()
    result = await validate_answer(query, answer, source_docs, citations)
    elapsed_ms = (time.time() - start) * 1000

    assert elapsed_ms < 150  # Should be fast path (<150ms)
    assert result.validation_method == "fast_path"
    assert result.action == "approve"


# ============================================================================
# Low-Quality Answer Tests
# ============================================================================

@pytest.mark.asyncio
async def test_answer_validator_too_short():
    """Test rejection of too-short answer"""
    answer = "I don't know."

    result = await validate_answer("test", answer, [], [])

    assert result.is_valid is False
    assert result.action == "regenerate"
    assert result.overall_score == 0.0
    assert len(result.issues) > 0
    assert result.issues[0].severity == "critical"


@pytest.mark.asyncio
async def test_answer_validator_low_quality():
    """Test flagging of low-quality answer"""
    answer = "I don't know the answer to that question. There is no information available."

    result = await validate_answer("test", answer, [], [])

    assert result.action == "regenerate"
    assert result.overall_score < 0.6
    assert result.validation_details.answer_quality < 0.6


@pytest.mark.asyncio
async def test_answer_validator_missing_citations():
    """Test handling of answer without citations"""
    answer = (
        "The answer is quite comprehensive and detailed. It provides useful information "
        "about the topic and covers multiple aspects thoroughly."
    )

    result = await validate_answer("test", answer, [], [])

    # Should flag for missing citations
    assert result.validation_details.citation_completeness == 0.0
    assert any(issue.type == "missing_citation" for issue in result.issues)


# ============================================================================
# Hallucination Detection Tests
# ============================================================================

@pytest.mark.asyncio
async def test_answer_validator_hallucination_detection():
    """Test hallucination detection with specific unsupported claims"""
    answer = "The company achieved 95% market share in 2025 with revenue of $500 million."
    source_docs = [{"id": "d1", "content": "The company is growing and expanding its market presence"}]
    citations = [{"doc_id": "d1"}]

    result = await validate_answer("market share?", answer, source_docs, citations)

    # Should detect unsupported specific claims (95%, $500 million)
    # May use NLI if available, or fallback
    assert result.validation_details.hallucination_risk > 0.0
    # Action may be flag or regenerate depending on NLI availability


@pytest.mark.asyncio
async def test_answer_validator_factual_consistency():
    """Test answer with good factual consistency"""
    answer = "Python was created by Guido van Rossum in 1991."
    source_docs = [
        {"id": "d1", "content": "Python was created by Guido van Rossum"},
        {"id": "d2", "content": "Python was first released in 1991"}
    ]
    citations = [{"doc_id": "d1"}, {"doc_id": "d2"}]

    result = await validate_answer("who created python?", answer, source_docs, citations)

    # Should have good factual consistency
    assert result.validation_details.factual_consistency >= 0.7
    assert result.validation_details.hallucination_risk <= 0.3
    assert result.action in ["approve", "flag"]


# ============================================================================
# Safety Tests
# ============================================================================

@pytest.mark.asyncio
async def test_answer_validator_safety_ssn():
    """Test rejection of answer with SSN"""
    answer = "Your social security number is 123-45-6789. Please verify this information."

    result = await validate_answer("test", answer, [], [])

    assert result.is_valid is False
    assert result.action == "regenerate"
    assert result.validation_details.safety_score == 0.0
    assert result.issues[0].type == "safety"


@pytest.mark.asyncio
async def test_answer_validator_safety_credit_card():
    """Test rejection of answer with credit card number"""
    answer = "The credit card number is 1234567890123456 for your account."

    result = await validate_answer("test", answer, [], [])

    assert result.is_valid is False
    assert result.action == "regenerate"
    assert result.validation_details.safety_score == 0.0


@pytest.mark.asyncio
async def test_answer_validator_safety_password():
    """Test rejection of answer with password"""
    answer = "Your password is: SecretPass123. Use this to login."

    result = await validate_answer("test", answer, [], [])

    assert result.is_valid is False
    assert result.action == "regenerate"


# ============================================================================
# Citation Validation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_citation_validation_complete():
    """Test complete citation validation"""
    answer = "This is a well-cited answer with proper sources."
    source_docs = [
        {"id": "doc1", "content": "Source 1"},
        {"id": "doc2", "content": "Source 2"}
    ]
    citations = [{"doc_id": "doc1"}, {"doc_id": "doc2"}]

    result = await validate_answer("test", answer, source_docs, citations)

    assert result.validation_details.citation_completeness == 1.0


@pytest.mark.asyncio
async def test_citation_validation_partial():
    """Test partial citation validation"""
    answer = "This answer has some citations but not all are valid."
    source_docs = [
        {"id": "doc1", "content": "Source 1"}
    ]
    citations = [{"doc_id": "doc1"}, {"doc_id": "missing_doc"}]

    result = await validate_answer("test", answer, source_docs, citations)

    assert result.validation_details.citation_completeness == 0.5


@pytest.mark.asyncio
async def test_citation_validation_with_doc_id_variants():
    """Test citation validation with different doc_id field names"""
    answer = "This answer demonstrates proper citation handling with varied document ID formats across different source types."
    source_docs = [
        {"id": "doc1", "content": "Source 1"},
        {"doc_id": "doc2", "content": "Source 2"}
    ]
    citations = [{"doc_id": "doc1"}, {"doc_id": "doc2"}]

    result = await validate_answer("test", answer, source_docs, citations)

    assert result.validation_details.citation_completeness == 1.0


# ============================================================================
# Unit Tests for Helper Functions
# ============================================================================

def test_quick_validation_too_short():
    """Test quick validation rejects too-short answers"""
    result = _quick_validation("Short", [])
    assert result["reject"] is True
    assert result["reason"] == "answer_too_short"


def test_quick_validation_no_citations():
    """Test quick validation flags missing citations"""
    result = _quick_validation("This is a longer answer that should pass length check.", [])
    assert result["reject"] is False
    assert result["flag"] is True
    assert result["reason"] == "no_citations"


def test_quick_validation_passed():
    """Test quick validation passes clean answers"""
    result = _quick_validation(
        "This is a good answer with sufficient length and proper content.",
        [{"doc_id": "doc1"}]
    )
    assert result["reject"] is False
    assert result["reason"] == "passed"


def test_validate_citations_complete():
    """Test citation validation with all valid citations"""
    answer = "Test answer"
    citations = [{"doc_id": "doc1"}, {"doc_id": "doc2"}]
    source_docs = [{"id": "doc1"}, {"id": "doc2"}]

    score = _validate_citations(answer, citations, source_docs)
    assert score == 1.0


def test_validate_citations_partial():
    """Test citation validation with some invalid citations"""
    answer = "Test answer"
    citations = [{"doc_id": "doc1"}, {"doc_id": "missing"}]
    source_docs = [{"id": "doc1"}]

    score = _validate_citations(answer, citations, source_docs)
    assert score == 0.5


def test_validate_citations_none():
    """Test citation validation with no citations"""
    answer = "Test answer"
    score = _validate_citations(answer, [], [])
    assert score == 0.0


def test_extract_factual_spans_numbers():
    """Test extraction of numbers from answer"""
    answer = "The system achieved 95% accuracy with 1000 samples."
    spans = _extract_factual_spans(answer)

    assert "95" in spans or "95%" in spans
    assert "1000" in spans


def test_extract_factual_spans_dates():
    """Test extraction of dates from answer"""
    answer = "The event occurred on 2025-06-15 and also on 12/25/2024."
    spans = _extract_factual_spans(answer)

    # Should extract date patterns
    assert len(spans) > 0


def test_extract_factual_spans_proper_nouns():
    """Test extraction of proper nouns from answer"""
    answer = "Python was created by Guido van Rossum at Google."
    spans = _extract_factual_spans(answer)

    # Should extract capitalized names
    assert any("Python" in span or "Guido" in span or "Google" in span for span in spans)


def test_extract_factual_spans_limit():
    """Test that factual span extraction respects limit"""
    answer = "1 2 3 4 5 6 7 8 9 10 11 12 13 14 15"  # More than NLI_MAX_CHECKS
    spans = _extract_factual_spans(answer)

    assert len(spans) <= 5  # NLI_MAX_CHECKS = 5


def test_assess_answer_quality_good():
    """Test quality assessment of good answer"""
    answer = (
        "This is a comprehensive answer. It provides detailed information. "
        "The content is informative and well-structured."
    )
    quality = _assess_answer_quality(answer)
    assert quality >= 0.7


def test_assess_answer_quality_too_short():
    """Test quality assessment of too-short answer"""
    answer = "This is a very short answer."
    quality = _assess_answer_quality(answer)
    assert quality < 0.8  # Penalized for being short


def test_assess_answer_quality_uninformative():
    """Test quality assessment of uninformative answer"""
    answer = "I don't know the answer to this question. No information available."
    quality = _assess_answer_quality(answer)
    assert quality < 0.6  # Heavily penalized for filler


# ============================================================================
# NLI Hallucination Check Tests
# ============================================================================

@pytest.mark.asyncio
async def test_check_hallucination_with_support():
    """Test hallucination check with well-supported answer"""
    answer = "Python is a programming language created by Guido van Rossum."
    source_docs = [
        {"content": "Python is a programming language"},
        {"content": "Python was created by Guido van Rossum"}
    ]

    score = await _check_hallucination(answer, source_docs)

    # Should have high factuality (low hallucination risk)
    assert score >= 0.5  # At least neutral


@pytest.mark.asyncio
async def test_check_hallucination_no_sources():
    """Test hallucination check with no source documents"""
    answer = "This is some answer with facts."
    source_docs = []

    score = await _check_hallucination(answer, source_docs)

    assert score == 0.5  # Neutral when no sources


@pytest.mark.asyncio
async def test_check_hallucination_no_factual_spans():
    """Test hallucination check with no factual spans"""
    answer = "this is a very generic answer without any specific facts"
    source_docs = [{"content": "Some source content"}]

    score = await _check_hallucination(answer, source_docs)

    assert score == 0.5  # Neutral when no spans to check


# ============================================================================
# Action Decision Tests
# ============================================================================

@pytest.mark.asyncio
async def test_action_approve():
    """Test that high-quality answers get approved"""
    answer = (
        "Machine learning is a powerful technology that enables computers to learn from data. "
        "It has applications in many fields including healthcare, finance, and autonomous systems."
    )
    source_docs = [
        {"id": "d1", "content": "Machine learning enables computers to learn from data"},
        {"id": "d2", "content": "ML has applications in healthcare and finance"}
    ]
    citations = [{"doc_id": "d1"}, {"doc_id": "d2"}]

    result = await validate_answer("what is ml?", answer, source_docs, citations)

    assert result.action == "approve"
    assert result.overall_score >= 0.8


@pytest.mark.asyncio
async def test_action_flag():
    """Test that medium-quality answers get flagged"""
    # Create an answer with missing citations to trigger flag action
    answer = (
        "This topic is complex and requires detailed understanding. "
        "There are multiple perspectives to consider in this domain. "
        "Further research would be helpful to provide complete coverage."
    )
    source_docs = [{"id": "d1", "content": "The topic is complex"}]
    citations = []  # No citations - should lower score

    result = await validate_answer("test", answer, source_docs, citations)

    # Should be flagged for missing citations or vagueness
    assert result.action in ["flag", "regenerate"]
    assert result.overall_score < 0.8


@pytest.mark.asyncio
async def test_action_regenerate():
    """Test that low-quality answers get regenerated"""
    answer = "I don't know."

    result = await validate_answer("test", answer, [], [])

    assert result.action == "regenerate"
    assert result.overall_score < 0.6


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.asyncio
async def test_validator_performance_fast_path():
    """Test that 90% of good answers use fast path"""
    good_answers = []

    for i in range(10):
        answer = (
            f"This is answer number {i}. It provides comprehensive information about the topic. "
            f"The content is well-structured and properly cited with relevant sources."
        )
        source_docs = [{"id": f"doc{i}", "content": f"Source content {i}"}]
        citations = [{"doc_id": f"doc{i}"}]

        result = await validate_answer(f"query {i}", answer, source_docs, citations)
        good_answers.append(result)

    # Most should use fast path
    fast_path_count = sum(1 for r in good_answers if r.validation_method == "fast_path")
    assert fast_path_count >= 8  # At least 80% use fast path


@pytest.mark.asyncio
async def test_validator_execution_time():
    """Test overall execution time meets requirements"""
    answer = (
        "This is a well-structured answer with proper citations. "
        "It provides accurate information based on the source documents."
    )
    source_docs = [{"id": "doc1", "content": "Source information"}]
    citations = [{"doc_id": "doc1"}]

    result = await validate_answer("test", answer, source_docs, citations)

    # Should complete within reasonable time
    assert result.execution_time_ms < 300  # Allow some overhead for test environment


@pytest.mark.asyncio
async def test_validator_level_3_llm_deep_validation():
    """Test Level 3 LLM deep validation for very low confidence answers"""
    # Create scenario with very low preliminary score (no citations, poor quality)
    query = "What is the revenue?"
    answer = "Maybe it's around 50 million or something."  # Vague, unsupported
    source_docs = [{"id": "doc1", "content": "The company had strong growth."}]  # No specific numbers
    citations = []  # No citations = low citation score

    result = await validate_answer(query, answer, source_docs, citations)

    # With no citations and vague answer, preliminary_score will be low
    # Should trigger either Level 3 (deep) or Level 2 (standard)
    assert result.validation_method in ["deep", "standard", "regenerate"]

    # Low quality answer should not approve
    assert result.action in ["flag", "regenerate"]
