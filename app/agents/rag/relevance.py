"""
LLM-based relevance scoring for retrieval quality assessment (Task 11).

Uses a fast local LLM (Haiku equivalent) to score query-document relevance.
Optimized for batch processing with <100ms target for top-5 results.

Scoring Scale:
- Highly Relevant (1.0): Document directly answers or addresses the query
- Somewhat Relevant (0.5): Document partially related or provides context
- Not Relevant (0.0): Document unrelated to the query
"""

import asyncio
import time
from typing import List, Dict, Literal
from pydantic import BaseModel, Field, field_validator
import ollama

from app.core.config import get_settings


# ============================================================================
# Data Models
# ============================================================================

class RelevanceScore(BaseModel):
    """Individual relevance score for a query-document pair"""
    score: float = Field(ge=0.0, le=1.0, description="Relevance score between 0.0 and 1.0")
    label: Literal["highly_relevant", "somewhat_relevant", "not_relevant"]
    reasoning: str = Field(min_length=1, description="Brief explanation of the score")

    @field_validator('label')
    @classmethod
    def validate_label(cls, v: str) -> str:
        """Validate label is one of the allowed values"""
        valid_labels = {"highly_relevant", "somewhat_relevant", "not_relevant"}
        if v not in valid_labels:
            raise ValueError(f"Label must be one of {valid_labels}, got {v}")
        return v


class BatchRelevanceResult(BaseModel):
    """Batch relevance scoring result"""
    scores: List[RelevanceScore]
    average_score: float = Field(ge=0.0, le=1.0)
    execution_time_ms: int
    model_used: str


# ============================================================================
# Scoring Functions
# ============================================================================

def _get_fast_model() -> str:
    """Get the fast model for relevance scoring"""
    settings = get_settings()
    # Use the main chat model - typically fast enough for scoring
    return settings.ollama_chat_model


def _parse_llm_response(response: str) -> tuple[float, str, str]:
    """
    Parse LLM response to extract score, label, and reasoning.

    Expected format:
    SCORE: <0.0-1.0>
    LABEL: <highly_relevant|somewhat_relevant|not_relevant>
    REASONING: <explanation>

    Returns:
        tuple of (score, label, reasoning)
    """
    lines = response.strip().split('\n')
    score = 0.0
    label = "not_relevant"
    reasoning = "Unable to parse response"

    for line in lines:
        line = line.strip()
        if line.startswith("SCORE:"):
            try:
                score_str = line.split(":", 1)[1].strip()
                score = float(score_str)
                score = max(0.0, min(1.0, score))  # Clamp to [0.0, 1.0]
            except (ValueError, IndexError):
                score = 0.0
        elif line.startswith("LABEL:"):
            try:
                label = line.split(":", 1)[1].strip().lower()
                if label not in {"highly_relevant", "somewhat_relevant", "not_relevant"}:
                    label = "not_relevant"
            except IndexError:
                label = "not_relevant"
        elif line.startswith("REASONING:"):
            try:
                reasoning = line.split(":", 1)[1].strip()
            except IndexError:
                reasoning = "No reasoning provided"

    return score, label, reasoning


def _parse_batch_llm_response(response: str, num_documents: int) -> List[tuple[float, str, str]]:
    """
    Parse batch LLM response for multiple documents.

    Expected format:
    Document 1:
    SCORE: <0.0-1.0>
    LABEL: <highly_relevant|somewhat_relevant|not_relevant>
    REASONING: <explanation>

    Document 2:
    ...

    Returns:
        List of (score, label, reasoning) tuples
    """
    results = []
    sections = response.strip().split("Document ")

    for section in sections:
        if not section.strip():
            continue

        # Skip the document number line
        lines = section.strip().split('\n')
        if len(lines) < 3:
            # Incomplete response, use default
            results.append((0.0, "not_relevant", "Incomplete response"))
            continue

        # Parse the score/label/reasoning from this section
        score = 0.0
        label = "not_relevant"
        reasoning = "Unable to parse response"

        for line in lines[1:]:  # Skip first line (document number)
            line = line.strip()
            if line.startswith("SCORE:"):
                try:
                    score_str = line.split(":", 1)[1].strip()
                    score = float(score_str)
                    score = max(0.0, min(1.0, score))
                except (ValueError, IndexError):
                    score = 0.0
            elif line.startswith("LABEL:"):
                try:
                    label = line.split(":", 1)[1].strip().lower()
                    if label not in {"highly_relevant", "somewhat_relevant", "not_relevant"}:
                        label = "not_relevant"
                except IndexError:
                    label = "not_relevant"
            elif line.startswith("REASONING:"):
                try:
                    reasoning = line.split(":", 1)[1].strip()
                except IndexError:
                    reasoning = "No reasoning provided"

        results.append((score, label, reasoning))

    # Ensure we have exactly num_documents results
    while len(results) < num_documents:
        results.append((0.0, "not_relevant", "Missing response"))

    return results[:num_documents]


def _create_scoring_prompt(query: str, document: str) -> str:
    """Create a prompt for relevance scoring"""
    return f"""You are a relevance scoring assistant. Evaluate how relevant the document is to the query.

Query: {query}

Document: {document}

Score the relevance on a 3-point scale:
- 1.0 = Highly Relevant: Document directly answers or addresses the query
- 0.5 = Somewhat Relevant: Document partially related or provides context
- 0.0 = Not Relevant: Document unrelated to the query

Respond ONLY in this exact format:
SCORE: <0.0, 0.5, or 1.0>
LABEL: <highly_relevant, somewhat_relevant, or not_relevant>
REASONING: <one sentence explaining your score>"""


def _create_batch_scoring_prompt(query: str, documents: List[str]) -> str:
    """Create a batch prompt for scoring multiple documents at once"""
    doc_texts = []
    for i, doc in enumerate(documents, 1):
        # Truncate very long documents to keep prompt manageable
        doc_truncated = doc[:500] if len(doc) > 500 else doc
        doc_texts.append(f"Document {i}:\n{doc_truncated}")

    docs_combined = "\n\n".join(doc_texts)

    return f"""You are a relevance scoring assistant. Evaluate how relevant each document is to the query.

Query: {query}

{docs_combined}

Score each document's relevance on a 3-point scale:
- 1.0 = Highly Relevant: Document directly answers or addresses the query
- 0.5 = Somewhat Relevant: Document partially related or provides context
- 0.0 = Not Relevant: Document unrelated to the query

Respond for EACH document in this exact format:

Document 1:
SCORE: <0.0, 0.5, or 1.0>
LABEL: <highly_relevant, somewhat_relevant, or not_relevant>
REASONING: <one sentence>

Document 2:
SCORE: <0.0, 0.5, or 1.0>
LABEL: <highly_relevant, somewhat_relevant, or not_relevant>
REASONING: <one sentence>

Continue for all {len(documents)} documents."""


async def score_relevance(query: str, document: str, model: str = None) -> RelevanceScore:
    """
    Score the relevance of a document to a query using LLM.

    Args:
        query: User query text
        document: Document content to score
        model: Optional model override (defaults to fast model from config)

    Returns:
        RelevanceScore with score, label, and reasoning
    """
    # Handle empty inputs
    if not query or not query.strip():
        return RelevanceScore(
            score=0.0,
            label="not_relevant",
            reasoning="Empty query provided"
        )

    if not document or not document.strip():
        return RelevanceScore(
            score=0.0,
            label="not_relevant",
            reasoning="Empty document provided"
        )

    # Get model
    if model is None:
        model = _get_fast_model()

    # Create prompt
    prompt = _create_scoring_prompt(query, document)

    try:
        # Call LLM asynchronously
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: ollama.generate(model=model, prompt=prompt)
        )

        # Parse response
        response_text = response.get('response', '')
        score, label, reasoning = _parse_llm_response(response_text)

        return RelevanceScore(
            score=score,
            label=label,
            reasoning=reasoning
        )

    except Exception as e:
        # Graceful fallback
        return RelevanceScore(
            score=0.5,
            label="somewhat_relevant",
            reasoning=f"Error during scoring: {str(e)}"
        )


async def batch_score_relevance(
    query: str,
    documents: List[Dict],
    model: str = None,
    max_concurrent: int = 5
) -> BatchRelevanceResult:
    """
    Batch score multiple documents for relevance to a query.

    Optimized for performance with a SINGLE LLM call for all documents.
    Target: <100ms for top-5 documents.

    Args:
        query: User query text
        documents: List of document dicts with 'content' key
        model: Optional model override
        max_concurrent: Maximum concurrent scoring requests (unused in optimized version)

    Returns:
        BatchRelevanceResult with all scores and statistics
    """
    start_time = time.time()

    # Get model
    if model is None:
        model = _get_fast_model()

    # Handle empty documents
    if not documents:
        return BatchRelevanceResult(
            scores=[],
            average_score=0.0,
            execution_time_ms=0,
            model_used=model
        )

    # Extract content from documents
    contents = [doc.get('content', '') for doc in documents]

    # For small batches (<=5), use optimized single LLM call
    if len(contents) <= 5:
        try:
            # Create batch prompt
            prompt = _create_batch_scoring_prompt(query, contents)

            # Call LLM once for all documents
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: ollama.generate(model=model, prompt=prompt, options={"temperature": 0})
            )

            # Parse batch response
            response_text = response.get('response', '')
            parsed_results = _parse_batch_llm_response(response_text, len(contents))

            # Convert to RelevanceScore objects
            scores = [
                RelevanceScore(score=score, label=label, reasoning=reasoning)
                for score, label, reasoning in parsed_results
            ]

        except Exception as e:
            # Fallback to neutral scores on error
            scores = [
                RelevanceScore(
                    score=0.5,
                    label="somewhat_relevant",
                    reasoning=f"Error during batch scoring: {str(e)}"
                )
                for _ in contents
            ]
    else:
        # For larger batches, fall back to concurrent individual scoring
        semaphore = asyncio.Semaphore(max_concurrent)

        async def score_with_semaphore(content: str) -> RelevanceScore:
            async with semaphore:
                return await score_relevance(query, content, model)

        tasks = [score_with_semaphore(content) for content in contents]
        scores = await asyncio.gather(*tasks)

    # Calculate average score
    if scores:
        average_score = sum(s.score for s in scores) / len(scores)
    else:
        average_score = 0.0

    execution_time_ms = int((time.time() - start_time) * 1000)

    return BatchRelevanceResult(
        scores=scores,
        average_score=round(average_score, 3),
        execution_time_ms=execution_time_ms,
        model_used=model
    )
