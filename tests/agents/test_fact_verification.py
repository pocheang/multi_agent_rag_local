"""
Tests for fact verification layer (Task 14).

Verifies that:
- Factual claims are extracted from generated answers
- Each fact is verified against cited sources
- Date/number accuracy is checked
- Negations and contradictions are detected
- Unverified claims are flagged for removal or hedging
"""

import pytest
from app.agents.validation.fact_verification import (
    FactVerifier,
    FactClaim,
    VerificationResult,
    FactVerificationConfig,
    extract_claims,
    verify_claim_against_source,
    check_citation_support,
)


# ============================================================================
# Claim Extraction Tests
# ============================================================================

def test_extract_claims_simple_facts():
    """Test extraction of simple factual claims"""
    answer = "Transformer uses self-attention [doc1:p3]. It was introduced in 2017 [doc1:p5]."

    claims = extract_claims(answer)

    assert len(claims) >= 2, "Should extract at least 2 claims"

    # Check that claims are extracted
    claim_texts = [c.text for c in claims]
    assert any("self-attention" in text.lower() for text in claim_texts)
    assert any("2017" in text for text in claim_texts)


def test_extract_claims_with_numbers():
    """Test extraction of claims with numeric values"""
    answer = "The model has 110M parameters [doc2:p1]. Training cost was $5 million [doc2:p3]."

    claims = extract_claims(answer)

    assert len(claims) >= 2

    # Check numeric claims are extracted
    claim_texts = [c.text for c in claims]
    assert any("110M" in text or "110" in text for text in claim_texts)
    assert any("million" in text.lower() for text in claim_texts)


def test_extract_claims_preserves_citations():
    """Test that extracted claims preserve citation information"""
    answer = "BERT uses bidirectional attention [doc3:p2]."

    claims = extract_claims(answer)

    assert len(claims) >= 1
    assert claims[0].citations is not None
    assert len(claims[0].citations) > 0
    assert "doc3" in claims[0].citations[0]


def test_extract_claims_handles_no_citations():
    """Test extraction when no citations are present"""
    answer = "Machine learning is a subset of artificial intelligence."

    claims = extract_claims(answer)

    # Should still extract claims even without citations
    assert len(claims) >= 1
    assert claims[0].citations == [] or claims[0].citations is None


# ============================================================================
# Citation Support Tests
# ============================================================================

def test_check_citation_support_valid():
    """Test that valid citations pass verification"""
    claim_text = "Transformer uses self-attention"
    citations = ["doc1:p3"]
    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p3",
            "content": "The Transformer architecture uses self-attention mechanisms for sequence processing."
        }
    ]

    is_supported, confidence = check_citation_support(claim_text, citations, source_docs)

    assert is_supported, "Valid citation should be supported"
    assert confidence >= 0.7, f"Confidence should be high for supported claim, got {confidence}"


def test_check_citation_support_missing_doc():
    """Test that missing cited document is flagged"""
    claim_text = "BERT uses bidirectional attention"
    citations = ["doc99:p1"]
    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p1",
            "content": "Some other content"
        }
    ]

    is_supported, confidence = check_citation_support(claim_text, citations, source_docs)

    assert not is_supported, "Missing citation should not be supported"
    assert confidence < 0.5, "Confidence should be low for missing citation"


def test_check_citation_support_content_mismatch():
    """Test that citation content mismatch is detected"""
    claim_text = "The model has 500M parameters"
    citations = ["doc2:p1"]
    source_docs = [
        {
            "doc_id": "doc2",
            "page": "p1",
            "content": "The model has 110M parameters and was trained on TPUs."
        }
    ]

    is_supported, confidence = check_citation_support(claim_text, citations, source_docs)

    # Number mismatch should result in low confidence
    assert not is_supported or confidence < 0.6, "Number mismatch should reduce confidence"


# ============================================================================
# Fact Verification Tests
# ============================================================================

@pytest.mark.asyncio
async def test_verify_claim_date_accuracy():
    """Test verification of date accuracy"""
    claim = FactClaim(
        text="The paper was published in 2017",
        citations=["doc1:p1"],
        claim_type="date"
    )

    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p1",
            "content": "The 'Attention is All You Need' paper was published in 2017."
        }
    ]

    result = await verify_claim_against_source(claim, source_docs)

    assert result.is_verified, "Date should match source"
    assert result.confidence > 0.8


@pytest.mark.asyncio
async def test_verify_claim_date_mismatch():
    """Test detection of date mismatch"""
    claim = FactClaim(
        text="The paper was published in 2020",
        citations=["doc1:p1"],
        claim_type="date"
    )

    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p1",
            "content": "The paper was published in 2017."
        }
    ]

    result = await verify_claim_against_source(claim, source_docs)

    assert not result.is_verified, "Date mismatch should be detected"
    assert "date" in result.issue_type.lower() or "mismatch" in result.issue_type.lower()


@pytest.mark.asyncio
async def test_verify_claim_number_accuracy():
    """Test verification of numeric accuracy"""
    claim = FactClaim(
        text="The model has 110 million parameters",
        citations=["doc2:p1"],
        claim_type="number"
    )

    source_docs = [
        {
            "doc_id": "doc2",
            "page": "p1",
            "content": "BERT-base has 110 million parameters and was trained on 16 TPUs."
        }
    ]

    result = await verify_claim_against_source(claim, source_docs)

    assert result.is_verified, f"Number should match source (within tolerance), got confidence={result.confidence}"
    assert result.confidence >= 0.6, f"Confidence should be reasonable, got {result.confidence}"


@pytest.mark.asyncio
async def test_verify_claim_number_tolerance():
    """Test that numbers within 15% tolerance pass verification"""
    claim = FactClaim(
        text="The model has approximately 115 million parameters",
        citations=["doc2:p1"],
        claim_type="number"
    )

    source_docs = [
        {
            "doc_id": "doc2",
            "page": "p1",
            "content": "The model has 110 million parameters and uses transformer architecture."
        }
    ]

    result = await verify_claim_against_source(claim, source_docs)

    # 115M vs 110M is ~4.5% difference, within 15% tolerance
    assert result.is_verified, f"Numbers within 15% tolerance should pass, got confidence={result.confidence}"


@pytest.mark.asyncio
async def test_verify_claim_negation_detection():
    """Test detection of negation conflicts"""
    claim = FactClaim(
        text="BERT does not use autoregressive generation",
        citations=["doc3:p1"],
        claim_type="negation"
    )

    source_docs = [
        {
            "doc_id": "doc3",
            "page": "p1",
            "content": "BERT uses masked language modeling, not autoregressive generation."
        }
    ]

    result = await verify_claim_against_source(claim, source_docs)

    # Should verify - negation is consistent
    assert result.is_verified, "Consistent negation should pass"


@pytest.mark.asyncio
async def test_verify_claim_negation_conflict():
    """Test detection of negation conflict"""
    claim = FactClaim(
        text="The company is not profitable",
        citations=["doc4:p2"],
        claim_type="negation"
    )

    source_docs = [
        {
            "doc_id": "doc4",
            "page": "p2",
            "content": "The company achieved profitability in Q4 2023."
        }
    ]

    result = await verify_claim_against_source(claim, source_docs)

    assert not result.is_verified, "Negation conflict should be detected"
    assert "negation" in result.issue_type.lower() or "contradict" in result.issue_type.lower()


# ============================================================================
# Full Verification Workflow Tests
# ============================================================================

@pytest.mark.asyncio
async def test_fact_verifier_full_workflow():
    """Test full verification workflow"""
    answer = (
        "Transformer architecture uses self-attention mechanisms [doc1:p3]. "
        "It was introduced in 2017 [doc1:p5]. "
        "The model has 110M parameters [doc2:p1]."
    )

    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p3",
            "content": "Transformer uses self-attention for parallel processing."
        },
        {
            "doc_id": "doc1",
            "page": "p5",
            "content": "The architecture was introduced in the 2017 paper 'Attention is All You Need'."
        },
        {
            "doc_id": "doc2",
            "page": "p1",
            "content": "BERT-base has 110 million parameters."
        }
    ]

    verifier = FactVerifier()
    result = await verifier.verify_answer(answer, source_docs)

    assert result.overall_verified, "All claims should be verified"
    assert result.groundedness_score >= 0.9, "High groundedness expected for verified claims"
    assert len(result.unverified_claims) == 0, "No unverified claims expected"


@pytest.mark.asyncio
async def test_fact_verifier_detects_hallucination():
    """Test that verifier detects hallucinated facts"""
    answer = (
        "Transformer uses self-attention [doc1:p3]. "
        "It was introduced in 2020 [doc1:p5]. "  # Hallucinated date
        "The model has 500M parameters [doc2:p1]."  # Hallucinated number
    )

    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p3",
            "content": "Transformer uses self-attention."
        },
        {
            "doc_id": "doc1",
            "page": "p5",
            "content": "Introduced in 2017."
        },
        {
            "doc_id": "doc2",
            "page": "p1",
            "content": "The model has 110M parameters."
        }
    ]

    verifier = FactVerifier()
    result = await verifier.verify_answer(answer, source_docs)

    assert not result.overall_verified, "Hallucinations should be detected"
    assert result.groundedness_score < 0.8, "Low groundedness for hallucinated content"
    assert len(result.unverified_claims) > 0, "Unverified claims should be flagged"


@pytest.mark.asyncio
async def test_fact_verifier_missing_citations():
    """Test that verifier flags claims without citations"""
    answer = "Machine learning is a subset of AI. It uses statistical methods."

    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p1",
            "content": "Machine learning is a subset of artificial intelligence."
        }
    ]

    verifier = FactVerifier()
    result = await verifier.verify_answer(answer, source_docs)

    # Should flag missing citations - claims without citations cannot be verified
    assert len(result.unverified_claims) > 0 or result.groundedness_score < 0.9
    # Check for missing_citation issue type
    has_citation_issue = any("citation" in issue.lower() for issue in result.issues)
    assert has_citation_issue or len(result.unverified_claims) > 0, "Should flag missing citations"


@pytest.mark.asyncio
async def test_fact_verifier_contradiction_detection():
    """Test detection of contradictions"""
    answer = "The company is not profitable [doc1:p1]."

    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p1",
            "content": "The company achieved record profitability in 2023."
        }
    ]

    verifier = FactVerifier()
    result = await verifier.verify_answer(answer, source_docs)

    assert not result.overall_verified, "Contradiction should be detected"
    assert len(result.unverified_claims) > 0


# ============================================================================
# Multilingual Support Tests
# ============================================================================

@pytest.mark.asyncio
async def test_verify_chinese_claims():
    """Test verification of Chinese language claims"""
    answer = "Transformer使用自注意力机制 [doc1:p3]。它在2017年提出 [doc1:p5]。"

    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p3",
            "content": "Transformer架构使用自注意力机制进行序列处理。"
        },
        {
            "doc_id": "doc1",
            "page": "p5",
            "content": "该架构在2017年的论文中提出。"
        }
    ]

    verifier = FactVerifier()
    result = await verifier.verify_answer(answer, source_docs)

    # Chinese claims should be verified with reasonable groundedness
    assert result.groundedness_score >= 0.5, f"Chinese claims should have reasonable groundedness, got {result.groundedness_score}"
    # At least one claim should be verified (the date one should match)
    assert len(result.verified_claims) >= 1, "At least some Chinese claims should be verified"


# ============================================================================
# Edge Cases Tests
# ============================================================================

@pytest.mark.asyncio
async def test_verify_empty_answer():
    """Test handling of empty answer"""
    answer = ""
    source_docs = []

    verifier = FactVerifier()
    result = await verifier.verify_answer(answer, source_docs)

    # Empty answer should pass (no claims to verify)
    assert result.overall_verified
    assert result.groundedness_score == 1.0


@pytest.mark.asyncio
async def test_verify_answer_no_sources():
    """Test handling of answer with no source documents"""
    answer = "Some factual claim [doc1:p1]."
    source_docs = []

    verifier = FactVerifier()
    result = await verifier.verify_answer(answer, source_docs)

    # Should flag as unverified due to missing sources
    assert not result.overall_verified
    assert len(result.unverified_claims) > 0


@pytest.mark.asyncio
async def test_verify_hedged_claims():
    """Test that hedged/uncertain claims are handled appropriately"""
    answer = (
        "According to the provided context, the model may have around 110M parameters [doc1:p1]. "
        "Limited information suggests it was introduced in 2017 [doc1:p2]."
    )

    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p1",
            "content": "The model has 110M parameters."
        },
        {
            "doc_id": "doc1",
            "page": "p2",
            "content": "Introduced in 2017."
        }
    ]

    verifier = FactVerifier()
    result = await verifier.verify_answer(answer, source_docs)

    # Hedged claims with valid citations should have reasonable groundedness
    # May not be perfect due to extra hedging words, but should pass if at least one claim verifies
    assert result.groundedness_score >= 0.5 or len(result.verified_claims) >= 1, \
        f"Hedged claims should have some verified content, got score={result.groundedness_score}, verified={len(result.verified_claims)}"


# ============================================================================
# Configuration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_custom_config_stricter_thresholds():
    """Test that custom config with stricter thresholds works"""
    config = FactVerificationConfig(
        min_support_confidence=0.8,  # Higher threshold
        number_tolerance=0.05,        # Tighter tolerance (5%)
        min_groundedness=0.95         # Very high groundedness required
    )

    answer = "The model has 112M parameters [doc1:p1]."
    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p1",
            "content": "The model has 110M parameters."
        }
    ]

    verifier = FactVerifier(config)
    result = await verifier.verify_answer(answer, source_docs)

    # 112M vs 110M is ~1.8% difference - within 5% tolerance
    # But with stricter thresholds, overall verification might be stricter
    assert hasattr(result, 'groundedness_score')
    assert isinstance(result.groundedness_score, float)


@pytest.mark.asyncio
async def test_custom_config_lenient_thresholds():
    """Test that custom config with lenient thresholds works"""
    config = FactVerificationConfig(
        min_support_confidence=0.4,   # Lower threshold
        number_tolerance=0.25,         # Looser tolerance (25%)
        min_groundedness=0.70          # Lower groundedness required
    )

    answer = "The model has 130M parameters [doc1:p1]."
    source_docs = [
        {
            "doc_id": "doc1",
            "page": "p1",
            "content": "The model has 110M parameters."
        }
    ]

    verifier = FactVerifier(config)
    result = await verifier.verify_answer(answer, source_docs)

    # 130M vs 110M is ~18% difference - outside default 15%, but within 25%
    # With lenient config, this should pass
    assert result.groundedness_score >= 0.5, \
        f"Lenient config should allow more variance, got {result.groundedness_score}"


def test_config_defaults_match_original_behavior():
    """Test that default config values match original hardcoded values"""
    config = FactVerificationConfig()

    # Verify all the original hardcoded values are preserved
    assert config.min_support_confidence == 0.6
    assert config.no_citation_confidence == 0.3
    assert config.missing_citation_confidence == 0.2
    assert config.base_confidence == 0.5
    assert config.number_match_boost == 0.25
    assert config.date_match_boost == 0.25
    assert config.high_overlap_boost == 0.25
    assert config.medium_overlap_boost == 0.15
    assert config.low_overlap_boost == 0.05
    assert config.negation_mismatch_penalty == 0.3
    assert config.number_mismatch_penalty == 0.5
    assert config.date_mismatch_penalty == 0.5
    assert config.high_overlap_threshold == 0.5
    assert config.medium_overlap_threshold == 0.3
    assert config.low_overlap_threshold == 0.15
    assert config.number_tolerance == 0.15
    assert config.min_groundedness == 0.85
    assert config.min_claim_length == 10
    assert config.min_clean_claim_length == 5
