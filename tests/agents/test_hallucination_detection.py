"""
Tests for hallucination pattern detection module (Task 9).

Tests rule-based pattern detection for:
- Date validation
- Number validation
- Entity validation
- Negation detection

Target: <5ms per check
"""

import pytest
import time
from app.agents.validation.hallucination_patterns import (
    detect_date_hallucinations,
    detect_number_hallucinations,
    detect_entity_hallucinations,
    detect_negation_hallucinations,
    detect_all_patterns,
    HallucinationPattern
)


# ============================================================================
# Date Pattern Detection Tests
# ============================================================================

def test_detect_date_hallucinations_exact_match():
    """Test that dates present in source are not flagged"""
    answer = "The company was founded in 2020 and raised $10M in 2021."
    source_text = "Founded in 2020, the company raised $10M in 2021."

    issues = detect_date_hallucinations(answer, source_text)

    assert len(issues) == 0


def test_detect_date_hallucinations_mismatch():
    """Test that dates not in source are flagged"""
    answer = "The company was founded in 2020."
    source_text = "Founded in 2019, the company has grown rapidly."

    issues = detect_date_hallucinations(answer, source_text)

    assert len(issues) == 1
    assert issues[0].pattern_type == "date_mismatch"
    assert "2020" in issues[0].content
    assert issues[0].severity == "high"


def test_detect_date_hallucinations_chinese_dates():
    """Test Chinese date format detection"""
    answer = "公司成立于2020年3月15日"
    source_text = "2020年3月15日成立"

    issues = detect_date_hallucinations(answer, source_text)

    assert len(issues) == 0


def test_detect_date_hallucinations_chinese_mismatch():
    """Test Chinese date mismatch detection"""
    answer = "公司成立于2020年"
    source_text = "2019年成立的公司"

    issues = detect_date_hallucinations(answer, source_text)

    assert len(issues) == 1
    assert "2020" in issues[0].content


def test_detect_date_hallucinations_multiple_dates():
    """Test multiple date validation"""
    answer = "Founded in 2019, expanded in 2020, IPO in 2021."
    source_text = "Founded in 2019, expanded in 2020."

    issues = detect_date_hallucinations(answer, source_text)

    assert len(issues) == 1
    assert "2021" in issues[0].content


def test_detect_date_hallucinations_empty_source():
    """Test with empty source text"""
    answer = "Founded in 2020."
    source_text = ""

    issues = detect_date_hallucinations(answer, source_text)

    # Empty source should not flag dates (conservative)
    assert len(issues) == 0


def test_detect_date_hallucinations_quarter_format():
    """Test quarter date format (Q1 2020)"""
    answer = "Revenue grew in Q1 2020 and Q2 2020."
    source_text = "Q1 2020 and Q2 2020 showed growth."

    issues = detect_date_hallucinations(answer, source_text)

    assert len(issues) == 0


# ============================================================================
# Number Pattern Detection Tests
# ============================================================================

def test_detect_number_hallucinations_exact_match():
    """Test that exact numbers in source are not flagged"""
    answer = "The company raised $10 million in funding."
    source_text = "Raised $10 million."

    issues = detect_number_hallucinations(answer, source_text)

    assert len(issues) == 0


def test_detect_number_hallucinations_tolerance():
    """Test that numbers within 15% tolerance are not flagged"""
    answer = "Revenue reached $100 million."
    source_text = "Revenue was $105 million."

    issues = detect_number_hallucinations(answer, source_text)

    # Within 15% tolerance
    assert len(issues) == 0


def test_detect_number_hallucinations_outside_tolerance():
    """Test that numbers outside 15% tolerance are flagged"""
    answer = "Revenue reached $100 million."
    source_text = "Revenue was $150 million."

    issues = detect_number_hallucinations(answer, source_text)

    assert len(issues) == 1
    assert issues[0].pattern_type == "number_mismatch"
    assert "100" in issues[0].content or "million" in issues[0].content


def test_detect_number_hallucinations_chinese_numbers():
    """Test Chinese number detection"""
    answer = "公司收入达到100万美元"
    source_text = "收入100万美元"

    issues = detect_number_hallucinations(answer, source_text)

    assert len(issues) == 0


def test_detect_number_hallucinations_percentage():
    """Test percentage validation"""
    answer = "Growth rate was 25% year over year."
    source_text = "YoY growth: 25%"

    issues = detect_number_hallucinations(answer, source_text)

    assert len(issues) == 0


def test_detect_number_hallucinations_percentage_mismatch():
    """Test percentage mismatch detection"""
    answer = "Growth rate was 50%."
    source_text = "Growth rate: 25%"

    issues = detect_number_hallucinations(answer, source_text)

    assert len(issues) == 1


def test_detect_number_hallucinations_decimal():
    """Test decimal number validation"""
    answer = "The rate is 3.5%."
    source_text = "Rate: 3.5%"

    issues = detect_number_hallucinations(answer, source_text)

    assert len(issues) == 0


def test_detect_number_hallucinations_units():
    """Test number with units (million, billion)"""
    answer = "Valuation is $5 billion."
    source_text = "Company valued at $5B"

    issues = detect_number_hallucinations(answer, source_text)

    assert len(issues) == 0


# ============================================================================
# Entity Pattern Detection Tests
# ============================================================================

def test_detect_entity_hallucinations_match():
    """Test that entities in source are not flagged"""
    answer = "CEO John Smith announced the merger with Acme Corp."
    source_text = "John Smith, CEO, announced merger with Acme Corp."

    issues = detect_entity_hallucinations(answer, source_text)

    assert len(issues) == 0


def test_detect_entity_hallucinations_mismatch():
    """Test that entities not in source are flagged"""
    answer = "CEO Jane Doe announced the results."
    source_text = "CEO John Smith announced the results."

    issues = detect_entity_hallucinations(answer, source_text)

    assert len(issues) >= 1
    assert any("Jane Doe" in issue.content for issue in issues)


def test_detect_entity_hallucinations_chinese_entities():
    """Test Chinese entity detection"""
    answer = "李明担任首席执行官"
    source_text = "CEO李明"

    issues = detect_entity_hallucinations(answer, source_text)

    assert len(issues) == 0


def test_detect_entity_hallucinations_chinese_mismatch():
    """Test Chinese entity mismatch"""
    answer = "王伟担任CEO"
    source_text = "李明担任CEO"

    issues = detect_entity_hallucinations(answer, source_text)

    assert len(issues) >= 1


def test_detect_entity_hallucinations_ignore_common_words():
    """Test that common capitalized words are not flagged as entities"""
    answer = "The company announced results."
    source_text = "Results were announced."

    issues = detect_entity_hallucinations(answer, source_text)

    # "The" should be ignored as common word
    assert len(issues) == 0


def test_detect_entity_hallucinations_multi_word_names():
    """Test multi-word entity names"""
    answer = "John David Smith was appointed."
    source_text = "Appointed John David Smith as director."

    issues = detect_entity_hallucinations(answer, source_text)

    assert len(issues) == 0


# ============================================================================
# Negation Pattern Detection Tests
# ============================================================================

def test_detect_negation_hallucinations_no_negation():
    """Test that positive answer matching source is not flagged"""
    answer = "The company is profitable."
    source_text = "Company achieved profitability."

    issues = detect_negation_hallucinations(answer, source_text)

    assert len(issues) == 0


def test_detect_negation_hallucinations_answer_negates_source():
    """Test that answer negating source is flagged"""
    answer = "The company is not profitable."
    source_text = "Company achieved profitability."

    issues = detect_negation_hallucinations(answer, source_text)

    assert len(issues) >= 1
    assert issues[0].pattern_type == "negation_conflict"
    assert issues[0].severity == "high"


def test_detect_negation_hallucinations_chinese_negation():
    """Test Chinese negation detection"""
    answer = "公司没有盈利"
    source_text = "公司实现盈利"

    issues = detect_negation_hallucinations(answer, source_text)

    assert len(issues) >= 1


def test_detect_negation_hallucinations_source_negates_answer():
    """Test that positive answer contradicting negative source is flagged"""
    answer = "The company is growing."
    source_text = "Company is not growing."

    issues = detect_negation_hallucinations(answer, source_text)

    assert len(issues) >= 1


def test_detect_negation_hallucinations_both_negative():
    """Test that matching negations are not flagged"""
    answer = "The company did not meet targets."
    source_text = "Company failed to meet targets."

    issues = detect_negation_hallucinations(answer, source_text)

    # Both negative, should not flag
    assert len(issues) == 0


def test_detect_negation_hallucinations_multiple_negations():
    """Test multiple negation patterns"""
    answer = "The product is not available and has never been released."
    source_text = "Product is available and was released."

    issues = detect_negation_hallucinations(answer, source_text)

    assert len(issues) >= 1


# ============================================================================
# Combined Pattern Detection Tests
# ============================================================================

def test_detect_all_patterns_clean():
    """Test that clean answer with no hallucinations passes all checks"""
    answer = "Founded in 2020, the company raised $10M from Acme Ventures."
    source_text = "Company founded in 2020 raised $10M from Acme Ventures."

    all_issues = detect_all_patterns(answer, source_text)

    assert len(all_issues) == 0


def test_detect_all_patterns_multiple_issues():
    """Test that multiple hallucination types are detected"""
    answer = "Founded in 2020, raised $50M from XYZ Corp, and is not profitable."
    source_text = "Founded in 2019, raised $10M from ABC Inc, and is profitable."

    all_issues = detect_all_patterns(answer, source_text)

    # Should detect: date mismatch, number mismatch, entity mismatch, negation
    assert len(all_issues) >= 3
    pattern_types = {issue.pattern_type for issue in all_issues}
    assert "date_mismatch" in pattern_types
    assert "number_mismatch" in pattern_types


def test_detect_all_patterns_returns_hallucination_pattern():
    """Test that detect_all_patterns returns HallucinationPattern objects"""
    answer = "Founded in 2020."
    source_text = "Founded in 2019."

    all_issues = detect_all_patterns(answer, source_text)

    assert len(all_issues) >= 1
    assert all(isinstance(issue, HallucinationPattern) for issue in all_issues)
    assert all(hasattr(issue, 'pattern_type') for issue in all_issues)
    assert all(hasattr(issue, 'severity') for issue in all_issues)
    assert all(hasattr(issue, 'content') for issue in all_issues)
    assert all(hasattr(issue, 'suggestion') for issue in all_issues)


# ============================================================================
# Performance Tests
# ============================================================================

def test_date_detection_performance():
    """Test that date detection completes in <5ms"""
    answer = "Founded in 2019, expanded in 2020, IPO in 2021, acquired in 2022."
    source_text = "Founded 2019, expanded 2020, IPO 2021, acquired 2022."

    start = time.time()
    for _ in range(100):
        detect_date_hallucinations(answer, source_text)
    elapsed = (time.time() - start) * 1000

    avg_time = elapsed / 100
    assert avg_time < 5.0, f"Date detection too slow: {avg_time:.2f}ms"


def test_number_detection_performance():
    """Test that number detection completes in <5ms"""
    answer = "Revenue $100M, profit $20M, growth 25%, valuation $1B."
    source_text = "Revenue $100M profit $20M growth 25% valuation $1B."

    start = time.time()
    for _ in range(100):
        detect_number_hallucinations(answer, source_text)
    elapsed = (time.time() - start) * 1000

    avg_time = elapsed / 100
    assert avg_time < 5.0, f"Number detection too slow: {avg_time:.2f}ms"


def test_entity_detection_performance():
    """Test that entity detection completes in <5ms"""
    answer = "CEO John Smith and CFO Jane Doe announced results with Acme Corp."
    source_text = "John Smith CEO and Jane Doe CFO announced with Acme Corp."

    start = time.time()
    for _ in range(100):
        detect_entity_hallucinations(answer, source_text)
    elapsed = (time.time() - start) * 1000

    avg_time = elapsed / 100
    assert avg_time < 5.0, f"Entity detection too slow: {avg_time:.2f}ms"


def test_negation_detection_performance():
    """Test that negation detection completes in <5ms"""
    answer = "The company is not profitable and has never achieved positive cash flow."
    source_text = "Company is profitable with positive cash flow."

    start = time.time()
    for _ in range(100):
        detect_negation_hallucinations(answer, source_text)
    elapsed = (time.time() - start) * 1000

    avg_time = elapsed / 100
    assert avg_time < 5.0, f"Negation detection too slow: {avg_time:.2f}ms"


def test_all_patterns_performance():
    """Test that combined detection completes in <5ms"""
    answer = "Founded in 2020 by John Smith, raised $50M, and is not profitable."
    source_text = "Founded in 2020 by John Smith, raised $50M, and is profitable."

    start = time.time()
    for _ in range(100):
        detect_all_patterns(answer, source_text)
    elapsed = (time.time() - start) * 1000

    avg_time = elapsed / 100
    assert avg_time < 5.0, f"Combined detection too slow: {avg_time:.2f}ms"


# ============================================================================
# Edge Cases
# ============================================================================

def test_empty_answer():
    """Test with empty answer"""
    issues = detect_all_patterns("", "Some source text")
    assert len(issues) == 0


def test_empty_source():
    """Test with empty source"""
    issues = detect_all_patterns("Some answer", "")
    # Should not flag when source is empty (conservative)
    assert len(issues) == 0


def test_both_empty():
    """Test with both empty"""
    issues = detect_all_patterns("", "")
    assert len(issues) == 0


def test_special_characters():
    """Test handling of special characters"""
    answer = "Revenue: $1.5M (Q4 2020) - 25% growth!"
    source_text = "Q4 2020: $1.5M revenue, 25% growth"

    issues = detect_all_patterns(answer, source_text)
    assert len(issues) == 0


def test_unicode_chinese():
    """Test full Chinese text"""
    answer = "公司2020年成立，融资100万美元，李明担任CEO"
    source_text = "2020年成立公司，融资100万美元，CEO李明"

    issues = detect_all_patterns(answer, source_text)
    assert len(issues) == 0
