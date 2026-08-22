"""
Retrieval Quality Agent - Async parallel evaluation of retrieval results quality.

Evaluates 5 metrics in parallel:
- Coverage: Query keyword coverage in results
- Relevance: Average score of Top-K results (basic)
- LLM Relevance: LLM-based relevance scoring for top results
- Diversity: Source diversity (avoid single-source bias)
- Completeness: Context completeness check

Target: <200ms execution time with async/await and optional LLM scoring.
"""

import asyncio
import logging
import re
import time

from app.agents.shared.config import (
    RETRIEVAL_QUALITY_TIMEOUT_MS,
    RETRIEVAL_SAMPLE_TOP_K,
    RETRIEVAL_WEIGHT_COMPLETENESS,
    RETRIEVAL_WEIGHT_COVERAGE,
    RETRIEVAL_WEIGHT_DIVERSITY,
    RETRIEVAL_WEIGHT_RELEVANCE,
)
from app.agents.shared.quality_models import RetrievalQualityMetrics, RetrievalQualityResult

logger = logging.getLogger(__name__)

# Optional: Import LLM relevance scoring (Task 11)
try:
    from app.agents.rag.relevance import batch_score_relevance

    LLM_SCORING_AVAILABLE = True
except ImportError:
    LLM_SCORING_AVAILABLE = False


def _is_chinese(text: str) -> bool:
    """Check if text contains Chinese characters"""
    return bool(re.search(r"[一-鿿]", text))


def _tokenize_query(query: str) -> list[str]:
    """
    Tokenize query into keywords.
    Uses simple segmentation for Chinese, word splitting for English.
    """
    if _is_chinese(query):
        # For Chinese, use character-level + simple word detection
        # Extract 2-3 character sequences as potential words
        keywords = []
        # Add individual meaningful characters (length > 1)
        text = re.sub(r"[^一-鿿a-zA-Z0-9]", "", query)
        keywords.extend(list(text))

        # Add 2-char and 3-char combinations
        for i in range(len(text) - 1):
            keywords.append(text[i : i + 2])
        for i in range(len(text) - 2):
            keywords.append(text[i : i + 3])

        return list(set(keywords))  # Remove duplicates
    else:
        # For English, simple word splitting
        words = re.findall(r"\b\w+\b", query.lower())
        # Filter out stop words and short words
        stop_words = {"a", "an", "the", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or"}
        return [w for w in words if w not in stop_words and len(w) > 2]


async def _calculate_coverage_score(query: str, chunks: list[dict]) -> float:
    """
    Calculate how well chunks cover query keywords.

    Returns 0.0-1.0 based on keyword coverage ratio.
    """
    if not chunks or not query:
        return 0.0

    keywords = _tokenize_query(query)
    if not keywords:
        return 0.5  # Neutral score if no keywords extracted

    # Combine all chunk content
    all_content = " ".join(chunk.get("content", "") for chunk in chunks)
    all_content_lower = all_content.lower()

    # Count how many keywords are covered
    covered_keywords = sum(1 for kw in keywords if kw.lower() in all_content_lower)

    coverage_ratio = covered_keywords / len(keywords)
    return min(1.0, coverage_ratio)


async def _calculate_relevance_score(chunks: list[dict], metadata: dict) -> float:
    """
    Calculate average relevance from scores.

    Uses Top-K chunks' scores and averages them.
    Returns 0.0-1.0.
    """
    if not chunks:
        return 0.0

    # Extract scores from chunks
    scores = [chunk.get("score", 0.5) for chunk in chunks]

    if not scores:
        return 0.5  # Neutral if no scores available

    # Calculate average of top-K
    top_k = metadata.get("top_k", RETRIEVAL_SAMPLE_TOP_K)
    top_scores = sorted(scores, reverse=True)[:top_k]

    avg_score = sum(top_scores) / len(top_scores)
    return min(1.0, max(0.0, avg_score))


async def _calculate_diversity_score(chunks: list[dict]) -> float:
    """
    Calculate source diversity.

    Measures how well results are distributed across different sources.
    Returns 0.0-1.0, where 1.0 means all chunks from different sources.
    """
    if not chunks:
        return 0.0

    # Extract sources
    sources = [chunk.get("source", "unknown") for chunk in chunks]

    # Count unique sources
    unique_sources = len(set(sources))
    total_chunks = len(chunks)

    # Diversity ratio
    diversity_ratio = unique_sources / total_chunks

    # Apply sigmoid-like scaling to amplify differences
    # High diversity (0.8-1.0) -> good score
    # Medium diversity (0.5-0.8) -> medium score
    # Low diversity (<0.5) -> poor score
    if diversity_ratio >= 0.8:
        return min(1.0, diversity_ratio)
    elif diversity_ratio >= 0.5:
        return diversity_ratio * 0.9
    else:
        return diversity_ratio * 0.7


async def _calculate_completeness_score(chunks: list[dict]) -> float:
    """
    Check if chunks have complete context.

    Evaluates average chunk length and checks for truncation indicators.
    Returns 0.0-1.0.
    """
    if not chunks:
        return 0.0

    # Calculate average chunk length
    lengths = [len(chunk.get("content", "")) for chunk in chunks]
    avg_length = sum(lengths) / len(lengths)

    # Scoring based on length thresholds
    # Very short (<50 chars) -> incomplete
    # Short (50-150 chars) -> partially complete
    # Medium (150-300 chars) -> reasonably complete
    # Long (>300 chars) -> complete
    if avg_length >= 300:
        length_score = 1.0
    elif avg_length >= 150:
        length_score = 0.6 + (avg_length - 150) / 150 * 0.4
    elif avg_length >= 50:
        length_score = 0.3 + (avg_length - 50) / 100 * 0.3
    else:
        length_score = avg_length / 50 * 0.3

    # Check for truncation indicators
    truncation_indicators = ["...", "…", "[truncated]", "[...]"]
    truncated_count = sum(
        1 for chunk in chunks if any(indicator in chunk.get("content", "") for indicator in truncation_indicators)
    )

    truncation_penalty = (truncated_count / len(chunks)) * 0.2

    final_score = max(0.0, length_score - truncation_penalty)
    return min(1.0, final_score)


async def _calculate_llm_relevance_score(query: str, chunks: list[dict], metadata: dict) -> float:
    """
    Calculate LLM-based relevance score for top-K chunks.

    Uses lightweight LLM to score query-document relevance.
    Falls back to basic relevance score if LLM scoring unavailable.

    Returns 0.0-1.0.
    """
    if not LLM_SCORING_AVAILABLE:
        # Fallback to basic relevance scoring
        return await _calculate_relevance_score(chunks, metadata)

    if not chunks or not query:
        return 0.0

    # Score only top-K chunks for performance
    top_k = min(metadata.get("top_k", RETRIEVAL_SAMPLE_TOP_K), 5)
    top_chunks = chunks[:top_k]

    try:
        # Use batch LLM scoring with timeout
        result = await asyncio.wait_for(
            batch_score_relevance(query, top_chunks),
            timeout=10.0,  # 10s timeout for LLM scoring
        )
        return result.average_score
    except TimeoutError:
        # Fallback to basic scoring on timeout
        logger.warning("LLM relevance scoring timed out, using basic scoring")
        return await _calculate_relevance_score(chunks, metadata)
    except Exception as e:
        # Fallback to basic scoring on any error
        logger.error(f"LLM relevance scoring failed: {e}", exc_info=True)
        return await _calculate_relevance_score(chunks, metadata)


async def evaluate_retrieval_quality(
    query: str, chunks: list[dict], metadata: dict, use_llm_scoring: bool = False
) -> RetrievalQualityResult:
    """
    Evaluate retrieval quality with 4 metrics (async, non-blocking).

    Runs all metrics in parallel for maximum performance.
    Target execution time: <50ms (basic), <200ms (with LLM scoring).

    Args:
        query: Original query text
        chunks: Retrieved document chunks
        metadata: Retrieval metadata (scores, strategy, etc)
        use_llm_scoring: Whether to use LLM-based relevance scoring (slower but more accurate)

    Returns:
        RetrievalQualityResult with quality assessment
    """
    start_time = time.time()

    # Handle empty chunks case
    if not chunks:
        return RetrievalQualityResult(
            overall_quality=0.0,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.0, relevance_score=0.0, diversity_score=0.0, completeness_score=0.0
            ),
            execution_time_ms=int((time.time() - start_time) * 1000),
            issues=["no_chunks_retrieved"],
            suggestions=["Check retrieval configuration or query"],
        )

    try:
        # Choose relevance scoring method
        if use_llm_scoring and LLM_SCORING_AVAILABLE:
            relevance_task = _calculate_llm_relevance_score(query, chunks, metadata)
        else:
            relevance_task = _calculate_relevance_score(chunks, metadata)

        # Run all metrics in parallel
        tasks = [
            _calculate_coverage_score(query, chunks),
            relevance_task,
            _calculate_diversity_score(chunks),
            _calculate_completeness_score(chunks),
        ]

        coverage, relevance, diversity, completeness = await asyncio.wait_for(
            asyncio.gather(*tasks), timeout=RETRIEVAL_QUALITY_TIMEOUT_MS / 1000.0
        )

        # Calculate overall quality (weighted)
        overall = (
            coverage * RETRIEVAL_WEIGHT_COVERAGE
            + relevance * RETRIEVAL_WEIGHT_RELEVANCE
            + diversity * RETRIEVAL_WEIGHT_DIVERSITY
            + completeness * RETRIEVAL_WEIGHT_COMPLETENESS
        )

        # Identify issues and suggestions
        issues = []
        suggestions = []

        if diversity < 0.5:
            issues.append(f"Low source diversity (score: {diversity:.2f})")
            suggestions.append("Consider expanding retrieval scope to include more sources")

        if coverage < 0.6:
            issues.append(f"Poor keyword coverage (score: {coverage:.2f})")
            suggestions.append("Try synonym expansion or query rewriting")

        if relevance < 0.6:
            issues.append(f"Low relevance scores (score: {relevance:.2f})")
            suggestions.append("Review retrieval strategy or increase Top-K threshold")

        if completeness < 0.5:
            issues.append(f"Incomplete context (score: {completeness:.2f})")
            suggestions.append("Increase chunk size or review chunking strategy")

        execution_time = int((time.time() - start_time) * 1000)

        return RetrievalQualityResult(
            overall_quality=round(overall, 3),
            metrics=RetrievalQualityMetrics(
                coverage_score=round(coverage, 3),
                relevance_score=round(relevance, 3),
                diversity_score=round(diversity, 3),
                completeness_score=round(completeness, 3),
            ),
            execution_time_ms=execution_time,
            issues=issues,
            suggestions=suggestions,
        )

    except TimeoutError:
        # Graceful degradation on timeout
        return RetrievalQualityResult(
            overall_quality=0.5,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.5, relevance_score=0.5, diversity_score=0.5, completeness_score=0.5
            ),
            execution_time_ms=RETRIEVAL_QUALITY_TIMEOUT_MS,
            issues=["evaluation_timeout"],
            suggestions=["Reduce chunk count or simplify metrics"],
        )
    except Exception as e:
        # Graceful error handling
        logger.error(f"Retrieval quality evaluation failed: {e}", exc_info=True)
        execution_time = int((time.time() - start_time) * 1000)
        return RetrievalQualityResult(
            overall_quality=0.5,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.5, relevance_score=0.5, diversity_score=0.5, completeness_score=0.5
            ),
            execution_time_ms=execution_time,
            issues=[f"evaluation_error: {str(e)}"],
            suggestions=["Check input data format"],
        )
