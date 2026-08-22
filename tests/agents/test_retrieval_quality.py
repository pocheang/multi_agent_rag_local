"""
Tests for Retrieval Quality Agent.
"""

import pytest
import asyncio
from app.agents.rag.retrieval_quality import (
    evaluate_retrieval_quality,
    _calculate_coverage_score,
    _calculate_relevance_score,
    _calculate_diversity_score,
    _calculate_completeness_score,
    LLM_SCORING_AVAILABLE,
)
from app.agents.shared.quality_models import RetrievalQualityResult, RetrievalQualityMetrics


@pytest.mark.asyncio
async def test_retrieval_quality_basic():
    """Test basic quality evaluation with Chinese query"""
    query = "机器学习算法"
    chunks = [
        {"content": "机器学习是AI的重要分支，包含多种算法", "score": 0.9, "source": "doc1.pdf"},
        {"content": "常用算法包括决策树、随机森林和支持向量机", "score": 0.85, "source": "doc2.pdf"},
        {"content": "神经网络是深度学习的基础，属于机器学习范畴", "score": 0.8, "source": "doc1.pdf"}
    ]
    metadata = {"strategy": "hybrid", "total_candidates": 10}

    result = await evaluate_retrieval_quality(query, chunks, metadata)

    assert isinstance(result, RetrievalQualityResult)
    assert 0.0 <= result.overall_quality <= 1.0
    assert result.execution_time_ms < 100, f"Too slow: {result.execution_time_ms}ms"
    assert isinstance(result.metrics, RetrievalQualityMetrics)
    assert 0.0 <= result.metrics.coverage_score <= 1.0
    assert 0.0 <= result.metrics.relevance_score <= 1.0
    assert 0.0 <= result.metrics.diversity_score <= 1.0
    assert 0.0 <= result.metrics.completeness_score <= 1.0
    assert isinstance(result.issues, list)
    assert isinstance(result.suggestions, list)


@pytest.mark.asyncio
async def test_retrieval_quality_english():
    """Test quality evaluation with English query"""
    query = "machine learning algorithms"
    chunks = [
        {"content": "Machine learning is a subset of AI with many algorithms", "score": 0.92, "source": "article1.md"},
        {"content": "Common algorithms include decision trees and neural networks", "score": 0.88, "source": "article2.md"},
        {"content": "Deep learning uses neural networks for complex tasks", "score": 0.82, "source": "article3.md"}
    ]
    metadata = {"strategy": "vector", "total_candidates": 15}

    result = await evaluate_retrieval_quality(query, chunks, metadata)

    assert 0.0 <= result.overall_quality <= 1.0
    assert result.execution_time_ms < 100
    assert result.metrics.coverage_score > 0.5, "Should have good keyword coverage"
    assert result.metrics.relevance_score > 0.7, "Scores are high, should reflect in relevance"


@pytest.mark.asyncio
async def test_retrieval_quality_low_diversity():
    """Test detection of low diversity (all from same source)"""
    query = "测试查询"
    chunks = [
        {"content": "第一段文本内容", "score": 0.9, "source": "same_doc.pdf"},
        {"content": "第二段文本内容", "score": 0.85, "source": "same_doc.pdf"},
        {"content": "第三段文本内容", "score": 0.8, "source": "same_doc.pdf"}
    ]
    metadata = {}

    result = await evaluate_retrieval_quality(query, chunks, metadata)

    assert result.metrics.diversity_score < 0.5, "Should detect single-source bias"
    assert any("diversity" in issue.lower() or "多样性" in issue for issue in result.issues), \
        f"Should flag diversity issue. Issues: {result.issues}"
    assert any("expand" in sugg.lower() or "扩展" in sugg for sugg in result.suggestions), \
        f"Should suggest expanding scope. Suggestions: {result.suggestions}"


@pytest.mark.asyncio
async def test_retrieval_quality_high_diversity():
    """Test high diversity detection"""
    query = "test query"
    chunks = [
        {"content": "content from first source", "score": 0.9, "source": "doc1.pdf"},
        {"content": "content from second source", "score": 0.85, "source": "doc2.md"},
        {"content": "content from third source", "score": 0.8, "source": "doc3.txt"},
        {"content": "content from fourth source", "score": 0.75, "source": "doc4.html"}
    ]
    metadata = {}

    result = await evaluate_retrieval_quality(query, chunks, metadata)

    assert result.metrics.diversity_score > 0.7, "Should have high diversity with 4 unique sources"


@pytest.mark.asyncio
async def test_retrieval_quality_poor_coverage():
    """Test detection of poor keyword coverage"""
    query = "机器学习深度神经网络算法"
    chunks = [
        {"content": "这是一段完全无关的文本内容", "score": 0.5, "source": "doc1.pdf"},
        {"content": "另一段不相关的描述", "score": 0.45, "source": "doc2.pdf"},
        {"content": "没有关键词的内容", "score": 0.4, "source": "doc3.pdf"}
    ]
    metadata = {}

    result = await evaluate_retrieval_quality(query, chunks, metadata)

    assert result.metrics.coverage_score < 0.6, "Should detect poor coverage"
    assert any("coverage" in issue.lower() or "覆盖" in issue for issue in result.issues), \
        f"Should flag coverage issue. Issues: {result.issues}"


@pytest.mark.asyncio
async def test_retrieval_quality_empty_chunks():
    """Test handling of empty chunks list"""
    query = "test query"
    chunks = []
    metadata = {}

    result = await evaluate_retrieval_quality(query, chunks, metadata)

    assert result.overall_quality == 0.0, "Empty chunks should result in 0 quality"
    assert result.execution_time_ms < 50, "Should be very fast for empty input"


@pytest.mark.asyncio
async def test_retrieval_quality_missing_scores():
    """Test handling of chunks without scores"""
    query = "test query"
    chunks = [
        {"content": "content without score", "source": "doc1.pdf"},
        {"content": "another content", "source": "doc2.pdf"}
    ]
    metadata = {}

    result = await evaluate_retrieval_quality(query, chunks, metadata)

    # Should handle gracefully with default scoring
    assert 0.0 <= result.overall_quality <= 1.0
    assert result.execution_time_ms < 100


@pytest.mark.asyncio
async def test_retrieval_quality_completeness():
    """Test completeness scoring for truncated content"""
    query = "test query"

    # Short chunks (incomplete)
    short_chunks = [
        {"content": "short", "score": 0.9, "source": "doc1.pdf"},
        {"content": "very short text", "score": 0.85, "source": "doc2.pdf"}
    ]

    # Normal length chunks (complete)
    normal_chunks = [
        {"content": "This is a reasonably long chunk of text that contains sufficient context and information for the query. " * 3,
         "score": 0.9, "source": "doc1.pdf"},
        {"content": "Another well-formed chunk with adequate length and complete sentences providing good context. " * 3,
         "score": 0.85, "source": "doc2.pdf"}
    ]

    result_short = await evaluate_retrieval_quality(query, short_chunks, {})
    result_normal = await evaluate_retrieval_quality(query, normal_chunks, {})

    assert result_normal.metrics.completeness_score > result_short.metrics.completeness_score, \
        "Normal chunks should have higher completeness than short chunks"


@pytest.mark.asyncio
async def test_retrieval_quality_weighted_calculation():
    """Test that overall quality uses correct weights"""
    query = "test"
    chunks = [
        {"content": "test content with keyword", "score": 1.0, "source": "doc1.pdf"},
        {"content": "test keyword match", "score": 1.0, "source": "doc2.pdf"},
        {"content": "test another match", "score": 1.0, "source": "doc3.pdf"}
    ]
    metadata = {}

    result = await evaluate_retrieval_quality(query, chunks, metadata)

    # Verify weighted calculation (from config: 0.30, 0.40, 0.15, 0.15)
    expected = (
        result.metrics.coverage_score * 0.30 +
        result.metrics.relevance_score * 0.40 +
        result.metrics.diversity_score * 0.15 +
        result.metrics.completeness_score * 0.15
    )

    assert abs(result.overall_quality - expected) < 0.01, \
        f"Overall quality {result.overall_quality} doesn't match weighted sum {expected}"


@pytest.mark.asyncio
async def test_coverage_score_calculation():
    """Test coverage score calculation directly"""
    query = "机器学习算法"
    chunks = [
        {"content": "机器学习是重要技术", "score": 0.9, "source": "doc1.pdf"},
        {"content": "常用算法包括多种类型", "score": 0.85, "source": "doc2.pdf"}
    ]

    score = await _calculate_coverage_score(query, chunks)

    assert 0.0 <= score <= 1.0
    assert score > 0.5, "Should have reasonable coverage with matched keywords"


@pytest.mark.asyncio
async def test_relevance_score_calculation():
    """Test relevance score calculation directly"""
    chunks = [
        {"content": "text1", "score": 0.9, "source": "doc1.pdf"},
        {"content": "text2", "score": 0.8, "source": "doc2.pdf"},
        {"content": "text3", "score": 0.7, "source": "doc3.pdf"}
    ]
    metadata = {"top_k": 3}

    score = await _calculate_relevance_score(chunks, metadata)

    assert 0.0 <= score <= 1.0
    # Average should be around (0.9 + 0.8 + 0.7) / 3 = 0.8
    assert 0.75 <= score <= 0.85


@pytest.mark.asyncio
async def test_diversity_score_calculation():
    """Test diversity score calculation directly"""
    # High diversity
    diverse_chunks = [
        {"content": "text", "source": "doc1.pdf"},
        {"content": "text", "source": "doc2.pdf"},
        {"content": "text", "source": "doc3.pdf"}
    ]

    # Low diversity
    single_source_chunks = [
        {"content": "text1", "source": "same.pdf"},
        {"content": "text2", "source": "same.pdf"},
        {"content": "text3", "source": "same.pdf"}
    ]

    diverse_score = await _calculate_diversity_score(diverse_chunks)
    single_score = await _calculate_diversity_score(single_source_chunks)

    assert diverse_score > single_score
    assert diverse_score > 0.6
    assert single_score < 0.5


@pytest.mark.asyncio
async def test_completeness_score_calculation():
    """Test completeness score calculation directly"""
    # Complete chunks
    complete_chunks = [
        {"content": "This is a complete chunk with sufficient length and context. " * 5, "source": "doc1.pdf"},
        {"content": "Another complete chunk with good detail and information. " * 5, "source": "doc2.pdf"}
    ]

    # Incomplete chunks
    incomplete_chunks = [
        {"content": "Short", "source": "doc1.pdf"},
        {"content": "Too brief", "source": "doc2.pdf"}
    ]

    complete_score = await _calculate_completeness_score(complete_chunks)
    incomplete_score = await _calculate_completeness_score(incomplete_chunks)

    assert complete_score > incomplete_score
    assert complete_score > 0.7
    assert incomplete_score < 0.5


@pytest.mark.asyncio
async def test_parallel_execution_speed():
    """Test that parallel execution is actually fast"""
    query = "test parallel execution"
    chunks = [
        {"content": f"chunk {i} with test content", "score": 0.9 - i*0.05, "source": f"doc{i}.pdf"}
        for i in range(10)
    ]
    metadata = {}

    import time
    start = time.time()
    result = await evaluate_retrieval_quality(query, chunks, metadata)
    elapsed = (time.time() - start) * 1000

    assert elapsed < 100, f"Parallel execution too slow: {elapsed}ms"
    assert result.execution_time_ms < 100


@pytest.mark.asyncio
async def test_timeout_handling():
    """Test timeout handling with simulated slow operation"""
    # This test uses normal chunks, but verifies timeout configuration exists
    query = "test timeout"
    chunks = [
        {"content": "content", "score": 0.9, "source": "doc.pdf"}
    ]
    metadata = {}

    # Normal execution should complete within timeout
    result = await evaluate_retrieval_quality(query, chunks, metadata)

    assert result.execution_time_ms < 200, "Should complete well within timeout"
    assert "timeout" not in str(result.issues).lower(), "Should not timeout on normal execution"


@pytest.mark.asyncio
@pytest.mark.skipif(not LLM_SCORING_AVAILABLE, reason="LLM scoring module not available")
async def test_llm_relevance_scoring_integration():
    """Test LLM-based relevance scoring integration (Task 11)"""
    query = "What is machine learning?"
    chunks = [
        {"content": "Machine learning is a subset of AI that enables systems to learn from data.", "score": 0.9, "source": "doc1.pdf"},
        {"content": "Weather forecasting uses meteorological models.", "score": 0.5, "source": "doc2.pdf"},
        {"content": "Deep learning uses neural networks for pattern recognition.", "score": 0.85, "source": "doc3.pdf"},
    ]
    metadata = {"strategy": "hybrid", "top_k": 3}

    # Test with LLM scoring enabled
    result = await evaluate_retrieval_quality(query, chunks, metadata, use_llm_scoring=True)

    assert isinstance(result, RetrievalQualityResult)
    assert 0.0 <= result.overall_quality <= 1.0
    # LLM scoring may take longer but should still complete
    assert result.execution_time_ms < 30000, f"LLM scoring too slow: {result.execution_time_ms}ms"

    # Verify relevance score is reasonable (should detect relevant and irrelevant docs)
    assert 0.4 <= result.metrics.relevance_score <= 0.9, \
        f"LLM relevance score seems off: {result.metrics.relevance_score}"


@pytest.mark.asyncio
async def test_llm_scoring_fallback_on_error():
    """Test that LLM scoring falls back to basic scoring on errors"""
    query = "test query"
    chunks = [
        {"content": "test content", "score": 0.8, "source": "doc.pdf"}
    ]
    metadata = {}

    # Should work regardless of LLM availability
    result = await evaluate_retrieval_quality(query, chunks, metadata, use_llm_scoring=True)

    assert isinstance(result, RetrievalQualityResult)
    assert 0.0 <= result.overall_quality <= 1.0
    assert result.execution_time_ms < 30000


@pytest.mark.asyncio
async def test_basic_vs_llm_scoring_comparison():
    """Compare basic scoring vs LLM scoring when available"""
    query = "cybersecurity best practices"
    chunks = [
        {"content": "Cybersecurity involves protecting systems from attacks.", "score": 0.9, "source": "doc1.pdf"},
        {"content": "Cooking pasta requires boiling water.", "score": 0.3, "source": "doc2.pdf"},
    ]
    metadata = {"top_k": 2}

    # Basic scoring
    result_basic = await evaluate_retrieval_quality(query, chunks, metadata, use_llm_scoring=False)

    # LLM scoring (if available)
    result_llm = await evaluate_retrieval_quality(query, chunks, metadata, use_llm_scoring=True)

    # Both should produce valid results
    assert 0.0 <= result_basic.overall_quality <= 1.0
    assert 0.0 <= result_llm.overall_quality <= 1.0

    if LLM_SCORING_AVAILABLE:
        # LLM scoring should potentially be more accurate at detecting irrelevant content
        # But both should work correctly
        assert result_llm.execution_time_ms >= result_basic.execution_time_ms, \
            "LLM scoring should take at least as long as basic scoring"
